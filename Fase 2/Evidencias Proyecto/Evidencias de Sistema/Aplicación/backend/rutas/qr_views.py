"""Códigos QR de entrega: generación, escaneo y confirmación de entregas con QR."""
import json
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notificaciones.serializers import NotificacionSerializer

from usuarios.autorizaciones import autorizado_para_estudiante, estudiantes_autorizados_de
from usuarios.models import CodigoQREntrega, Estudiante, PerfilDelegado, Ruta

from .abordaje import (
    faltan_paradas_antes_del_colegio,
    ordenar_entrega_vuelta,
    registrar_abordaje,
    registrar_entrega,
    ruta_iniciada_del_estudiante,
)
from .comun import obtener_conductor_autenticado
from .ubicacion import lugar_de_entrega, lugar_de_subida, verificar_en_el_punto


QR_SALT = 'rutas-seguras-entrega-v1'
QR_DURACION_SEGUNDOS = 300
QR_TIPOS = {
    'abordaje': 'RUTAS_SEGURAS_ABORDAJE',
    'entrega': 'RUTAS_SEGURAS_ENTREGA',
}
MENSAJE_QR_GENERAL_SOLO_IDA = (
    'El QR general de la persona autorizada solo sirve para subir en la ida. '
    'Para entregar, debe mostrar el QR de cada estudiante.'
)
MENSAJE_QR_DEMO_FUERA_DE_DEMO = 'Este QR fijo es solo para demostraciones y no sirve en uso real.'
QR_ESTATICO_DIAS = 365
MENSAJE_FALTAN_PARADAS = 'Aún faltan casas por pasar. El inspector recibe a los estudiantes al terminar el recorrido.'


def _vuelven_al_colegio(ruta):
    """En la vuelta, el inspector solo recibe a quienes nadie recibió en su casa."""
    return (
        ruta.sentido == 'desde_colegio'
        and ruta.estudiantes_no_recibidos.exclude(pk__in=ruta.estudiantes_entregados.values('pk')).exists()
    )


def qr_general_no_sirve_en_vuelta(codigo, persona):
    """Con más de un estudiante a su nombre, en la vuelta se entrega con el QR de cada uno."""
    return (
        not codigo.estudiante_id
        and isinstance(persona, PerfilDelegado)
        and persona.tipo_delegado != 'inspector'
        and len(estudiantes_autorizados_de(persona)) > 1
    )


def obtener_codigo_qr_firmado(qr_payload, bloquear=False, proposito_esperado=None):
    try:
        contenido = json.loads(qr_payload) if isinstance(qr_payload, str) else qr_payload
        token = contenido.get('token') if isinstance(contenido, dict) else None
        if (
            not isinstance(contenido, dict)
            or contenido.get('tipo') not in QR_TIPOS.values()
            or not token
        ):
            return None, 'El codigo QR no fue emitido por Rutas Seguras.'
        # Primero solo se comprueba la firma; el plazo de 5 minutos se revisa más abajo,
        # porque el QR fijo de demostración no vence.
        firmado = signing.loads(token, salt=QR_SALT)
        proposito = firmado.get('proposito', 'entrega')
        if proposito not in QR_TIPOS or contenido.get('tipo') != QR_TIPOS[proposito]:
            return None, 'El codigo QR no fue emitido por Rutas Seguras.'
        if proposito_esperado and proposito != proposito_esperado:
            return None, f'El codigo QR no es valido para {proposito_esperado}.'
        queryset = CodigoQREntrega.objects.select_related(
            'usuario', 'estudiante', 'usuario__perfil_apoderado', 'usuario__perfil_delegado'
        )
        if bloquear:
            queryset = queryset.select_for_update()
        codigo = queryset.filter(pk=firmado.get('codigo_id')).first()
    except (ValueError, TypeError, signing.BadSignature, signing.SignatureExpired):
        return None, 'El codigo QR es invalido o ha expirado.'
    if codigo and codigo.estatico:
        if not settings.MODO_DEMOSTRACION:
            return None, MENSAJE_QR_DEMO_FUERA_DE_DEMO
    else:
        try:
            signing.loads(token, salt=QR_SALT, max_age=QR_DURACION_SEGUNDOS)
        except (signing.BadSignature, signing.SignatureExpired):
            return None, 'El codigo QR es invalido o ha expirado.'
    if not codigo or codigo.usado_en:
        return None, 'El codigo QR ya fue utilizado o no existe.'
    if codigo.expira_en <= timezone.now():
        return None, 'El codigo QR ha expirado.'
    return codigo, None


def consumir_codigo(codigo):
    """Gasta el QR (un solo uso). El QR fijo de demostración no se gasta. Devuelve False si ya no sirve."""
    if codigo.estatico:
        return settings.MODO_DEMOSTRACION
    return CodigoQREntrega.objects.filter(
        pk=codigo.pk,
        usado_en__isnull=True,
        expira_en__gt=timezone.now(),
    ).update(usado_en=timezone.now()) == 1


class GenerarQREntregaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.rol not in ('apoderado', 'delegado'):
            return Response({'message': 'Solo apoderados y delegados pueden generar este QR.'}, status=403)

        proposito = request.data.get('proposito', 'entrega')
        if proposito not in QR_TIPOS:
            return Response({'message': 'El propósito solicitado para el QR no es válido.'}, status=400)

        estudiante = None
        estudiante_id = request.data.get('estudiante_id')
        if estudiante_id:
            delegado = getattr(request.user, 'perfil_delegado', None)
            if delegado and delegado.tipo_delegado != 'inspector' and proposito == 'entrega':
                estudiante = Estudiante.objects.filter(pk=estudiante_id).first()
                if not estudiante or not autorizado_para_estudiante(estudiante, delegado):
                    raise Http404
            elif not hasattr(request.user, 'perfil_apoderado'):
                return Response({'message': 'No puedes generar un QR individual.'}, status=403)
            else:
                estudiante = Estudiante.objects.filter(
                    pk=estudiante_id, apoderado=request.user.perfil_apoderado
                ).first()
                if not estudiante:
                    raise Http404
        if proposito == 'abordaje' and estudiante is None:
            return Response(
                {'message': 'El QR de abordaje debe identificar a un estudiante.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        estatico = settings.MODO_DEMOSTRACION and request.user.rol == 'delegado'
        if estatico:
            # Presentación: el delegado siempre recibe el mismo código, que no vence ni se gasta.
            codigo = CodigoQREntrega.objects.filter(
                usuario=request.user, estudiante=estudiante, estatico=True,
            ).first() or CodigoQREntrega.objects.create(
                usuario=request.user, estudiante=estudiante, estatico=True,
                expira_en=timezone.now() + timedelta(days=QR_ESTATICO_DIAS),
            )
            expira_en = codigo.expira_en
        else:
            expira_en = timezone.now() + timedelta(seconds=QR_DURACION_SEGUNDOS)
            codigo = CodigoQREntrega.objects.create(
                usuario=request.user, estudiante=estudiante, expira_en=expira_en
            )
        token = signing.dumps(
            {'codigo_id': str(codigo.id), 'proposito': proposito},
            salt=QR_SALT,
            compress=True,
        )
        return Response({
            'qr_payload': json.dumps({'tipo': QR_TIPOS[proposito], 'token': token}),
            'valido_hasta': int(expira_en.timestamp() * 1000),
            'duracion_segundos': QR_DURACION_SEGUNDOS,
            'proposito': proposito,
            'estatico': estatico,
        }, status=201)


class RutaEscanearQRView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        conductor_perfil = obtener_conductor_autenticado(request)
        if not conductor_perfil:
            return Response({'message': 'Solo un conductor autorizado puede registrar escaneos.'}, status=status.HTTP_403_FORBIDDEN)
        qr_payload = request.data.get('qr_payload')
        codigo, error = obtener_codigo_qr_firmado(
            qr_payload,
            bloquear=True,
            proposito_esperado='abordaje',
        )
        if error:
            return Response({'message': error}, status=status.HTTP_400_BAD_REQUEST)

        estudiante = codigo.estudiante
        if not estudiante or estudiante.apoderado.usuario_id != codigo.usuario_id:
            return Response({'message': 'El QR no identifica a un estudiante autorizado.'}, status=400)

        ruta = ruta_iniciada_del_estudiante(conductor_perfil, estudiante)
        if not ruta:
            return Response(
                {'message': 'El estudiante no pertenece a la ruta activa del conductor.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ruta.estudiantes_abordados.filter(pk=estudiante.pk).exists():
            # El QR no se consume: queda disponible si se escaneó por error.
            siguiente_paso = (
                'Para entregarlo, escanea el QR del apoderado o de la persona autorizada.'
                if ruta.sentido == 'desde_colegio'
                else 'Este QR ya no es necesario: escanea el del estudiante que falta.'
            )
            return Response(
                {
                    'message': f'{estudiante.nombre} {estudiante.apellido} ya subió al furgón. {siguiente_paso}',
                    'ya_registrado': True,
                },
                status=status.HTTP_409_CONFLICT,
            )
        if ruta.sentido == 'desde_colegio':
            return Response(
                {'message': 'En la vuelta, si falla la biometría, la subida se valida con el QR del inspector.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Antes de gastar el QR: una vez consumido no se puede volver a usar.
        try:
            verificar_en_el_punto(ruta, lugar_de_subida(ruta, estudiante))
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not consumir_codigo(codigo):
            return Response(
                {'message': 'El codigo QR ya fue utilizado o ha expirado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            abordaje = registrar_abordaje(ruta, estudiante, metodo='qr')
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        notificacion = abordaje.pop('notificacion', None)

        return Response({
            'message': abordaje['mensaje'],
            'estudiante': f"{estudiante.nombre} {estudiante.apellido}",
            'abordaje': abordaje,
            'notificacion': NotificacionSerializer(notificacion).data if notificacion else None
        }, status=status.HTTP_200_OK)


class RutaConsultarQREntregaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        conductor = obtener_conductor_autenticado(request)
        if not conductor:
            return Response({'message': 'Solo un conductor autorizado puede validar el QR.'}, status=403)
        qr_payload = request.data.get('qr_payload') or request.data.get('texto_qr')
        codigo, error = obtener_codigo_qr_firmado(
            qr_payload, proposito_esperado='entrega'
        )
        if error:
            return Response({'message': error, 'valido': False}, status=400)

        usuario = codigo.usuario
        persona = None
        rol = ''
        if hasattr(usuario, 'perfil_apoderado'):
            persona = usuario.perfil_apoderado
            rol = 'Apoderado Titular'
        elif hasattr(usuario, 'perfil_delegado'):
            persona = usuario.perfil_delegado
            rol = 'Inspector Institucional' if persona.tipo_delegado == 'inspector' else 'Delegado Autorizado'
        if not persona:
            return Response({'message': 'El propietario del QR no esta autorizado.'}, status=400)

        rut = persona.rut or ''
        ruta = Ruta.objects.filter(conductor_perfil=conductor, estado='en_ruta').first()
        es_institucional = isinstance(persona, PerfilDelegado) and persona.tipo_delegado == 'inspector'
        # En la ida, el QR del apoderado (o de la persona autorizada) sirve para que suban sus niños:
        # es un solo QR para subir y para recibir.
        abordaje_autorizado = not es_institucional and bool(ruta) and ruta.sentido == 'hacia_colegio'
        if ruta and ruta.sentido == 'desde_colegio' and qr_general_no_sirve_en_vuelta(codigo, persona):
            return Response({'message': MENSAJE_QR_GENERAL_SOLO_IDA, 'valido': False}, status=400)
        recibe_en_vuelta = es_institucional and bool(ruta) and _vuelven_al_colegio(ruta)
        if es_institucional and (
            not ruta or (ruta.sentido != 'hacia_colegio' and not recibe_en_vuelta)
            or persona.colegio_id != ruta.colegio_id
        ):
            return Response({'message': 'El QR institucional no corresponde a la ruta de ida de este colegio.'}, status=403)
        if es_institucional and faltan_paradas_antes_del_colegio(ruta):
            return Response({'message': MENSAJE_FALTAN_PARADAS, 'valido': False}, status=409)
        estudiantes = ruta.estudiantes.all() if ruta else Estudiante.objects.none()
        if abordaje_autorizado:
            estudiantes = estudiantes.exclude(rutas_abordadas=ruta)
        else:
            # Solo se puede entregar a quien está a bordo y aún no fue entregado.
            estudiantes = estudiantes.filter(rutas_abordadas=ruta).exclude(rutas_entregadas=ruta)
        if codigo.estudiante_id:
            estudiantes = estudiantes.filter(pk=codigo.estudiante_id)

        autorizados = []
        for estudiante in estudiantes.select_related('apoderado'):
            if autorizado_para_estudiante(estudiante, persona):
                autorizados.append({
                    'id': estudiante.id,
                    'rut': estudiante.rut,
                    'nombre': f'{estudiante.nombre} {estudiante.apellido}',
                    'colegio': estudiante.colegio_id,
                    'curso': estudiante.curso,
                    'direccion': estudiante.direccion_completa,
                    'seleccionado': True,
                })
        if not autorizados:
            return Response(
                {'message': (
                    'Ningún estudiante autorizado por este QR falta por subir al furgón.'
                    if abordaje_autorizado
                    else 'Ningún estudiante autorizado por este QR está a bordo del furgón para ser entregado.'
                )},
                status=400,
            )
        return Response({
            'valido': True,
            'persona': {'id': persona.id, 'rut': rut, 'nombre': usuario.get_full_name() or usuario.email, 'rol': rol},
            'estudiantes': autorizados,
            'entrega_institucional': es_institucional,
            'abordaje_autorizado': abordaje_autorizado,
            'cantidad_estudiantes': len(autorizados),
        })


class RutaConfirmarEntregaMultipleView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        estudiante_ids = request.data.get('estudiante_ids', [])
        qr_payload = request.data.get('qr_payload')

        if not estudiante_ids:
            return Response({'message': 'Debes seleccionar al menos un estudiante para confirmar la entrega.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            estudiante_ids = [int(estudiante_id) for estudiante_id in estudiante_ids]
        except (TypeError, ValueError):
            return Response({'message': 'La selección contiene estudiantes inválidos.'}, status=400)

        codigo, error = obtener_codigo_qr_firmado(
            qr_payload, bloquear=True, proposito_esperado='entrega'
        )
        if error:
            return Response({'message': error}, status=status.HTTP_400_BAD_REQUEST)

        persona_usuario = codigo.usuario
        persona_perfil = getattr(persona_usuario, 'perfil_apoderado', None) or getattr(persona_usuario, 'perfil_delegado', None)
        if not persona_perfil:
            return Response({'message': 'El propietario del QR no esta autorizado.'}, status=400)
        persona_nombre = persona_usuario.get_full_name() or persona_usuario.email

        conductor_perfil = obtener_conductor_autenticado(request)

        if not conductor_perfil:
            return Response({'message': 'Acceso denegado. No se encontro perfil de conductor.'}, status=status.HTTP_403_FORBIDDEN)

        ruta = (
            Ruta.objects.select_for_update()
            .filter(conductor_perfil=conductor_perfil, estado='en_ruta')
            .order_by('id')
            .first()
        )
        if not ruta:
            return Response({'message': 'El conductor no tiene una ruta en recorrido.'}, status=400)

        es_institucional = isinstance(persona_perfil, PerfilDelegado) and persona_perfil.tipo_delegado == 'inspector'
        if es_institucional and (
            (ruta.sentido != 'hacia_colegio' and not _vuelven_al_colegio(ruta))
            or persona_perfil.colegio_id != ruta.colegio_id
        ):
            return Response({'message': 'El inspector no corresponde a la ruta de ida de este colegio.'}, status=403)
        if es_institucional and faltan_paradas_antes_del_colegio(ruta):
            return Response({'message': MENSAJE_FALTAN_PARADAS}, status=409)
        abordaje_autorizado = not es_institucional and ruta.sentido == 'hacia_colegio'
        if ruta.sentido == 'desde_colegio' and qr_general_no_sirve_en_vuelta(codigo, persona_perfil):
            return Response({'message': MENSAJE_QR_GENERAL_SOLO_IDA}, status=400)

        if es_institucional:
            esperados_ids = set(
                ruta.estudiantes.filter(rutas_abordadas=ruta)
                .exclude(rutas_entregadas=ruta)
                .values_list('id', flat=True)
            )
            if not esperados_ids:
                return Response({'message': 'No hay estudiantes a bordo pendientes de recepción.'}, status=400)
            if set(estudiante_ids) != esperados_ids:
                return Response({'message': 'La recepción institucional debe incluir a todos los estudiantes pendientes.'}, status=400)

        seleccionados = ruta.estudiantes.filter(id__in=estudiante_ids)
        if codigo.estudiante_id:
            seleccionados = seleccionados.filter(pk=codigo.estudiante_id)
        autorizados_ids = []
        for estudiante in seleccionados.select_related('apoderado'):
            if autorizado_para_estudiante(estudiante, persona_perfil):
                autorizados_ids.append(estudiante.id)
        if set(estudiante_ids) != set(autorizados_ids):
            return Response({'message': 'La seleccion contiene estudiantes no autorizados por este QR.'}, status=403)

        if abordaje_autorizado:
            if ruta.estudiantes_abordados.filter(id__in=estudiante_ids).exists():
                return Response({'message': 'Uno o más estudiantes ya subieron al furgón.'}, status=409)
            # Antes de gastar el QR: una vez consumido no se puede volver a usar.
            try:
                for estudiante in seleccionados:
                    verificar_en_el_punto(ruta, lugar_de_subida(ruta, estudiante))
            except ValueError as exc:
                return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            if not consumir_codigo(codigo):
                return Response({'message': 'El codigo QR ya fue utilizado o ha expirado.'}, status=400)
            abordajes = []
            for estudiante in seleccionados:
                # Si lo mandó una persona autorizada queda registrada; si fue su apoderado, no hace falta.
                delegado = persona_perfil if isinstance(persona_perfil, PerfilDelegado) else None
                abordaje = registrar_abordaje(ruta, estudiante, metodo='qr', delegado=delegado)
                abordaje.pop('notificacion', None)
                abordajes.append(abordaje)
            return Response({
                'message': (
                    abordajes[0]['mensaje'] if len(abordajes) == 1
                    else f'{len(abordajes)} estudiantes subieron al furgón.'
                ),
                'abordajes': abordajes,
            }, status=status.HTTP_200_OK)

        # Antes de gastar el QR: una vez consumido no se puede volver a usar.
        if ruta.sentido == 'desde_colegio' and not ruta.reparto_iniciado_en:
            return Response({'message': 'Primero debes iniciar el reparto.'}, status=status.HTTP_400_BAD_REQUEST)

        abordados_ids = set(
            ruta.estudiantes_abordados.filter(id__in=estudiante_ids).values_list('id', flat=True)
        )
        if set(estudiante_ids) != abordados_ids:
            return Response(
                {'message': 'No se puede entregar un estudiante que no haya abordado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ruta.estudiantes_entregados.filter(id__in=estudiante_ids).exists():
            return Response({'message': 'Uno o más estudiantes ya fueron entregados.'}, status=400)
        try:
            for estudiante in seleccionados:
                verificar_en_el_punto(ruta, lugar_de_entrega(ruta, estudiante, es_institucional))
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if ruta.sentido == 'desde_colegio' and not es_institucional:
            try:
                estudiante_ids = ordenar_entrega_vuelta(ruta, estudiante_ids)
            except ValueError as exc:
                return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not consumir_codigo(codigo):
            return Response({'message': 'El codigo QR ya fue utilizado o ha expirado.'}, status=400)

        entregados_cnt = 0
        notificaciones_creadas = []

        seleccionados_por_id = {estudiante.id: estudiante for estudiante in seleccionados}
        entregas = []
        for est_id in estudiante_ids:
            estudiante = seleccionados_por_id[est_id]
            entrega = registrar_entrega(ruta, estudiante, persona_perfil, 'qr')
            notif = entrega.pop('notificacion', None)
            entregas.append(entrega)
            entregados_cnt += 1
            if notif:
                notificaciones_creadas.append(NotificacionSerializer(notif).data)

        if entregados_cnt == 0:
            return Response({'message': 'No se pudo registrar la entrega de ningún estudiante seleccionado.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': f"Recepción confirmada: {entregados_cnt} estudiante(s)",
            'estudiantes_entregados': entregados_cnt,
            'entregas': entregas,
            'notificaciones': notificaciones_creadas
        }, status=status.HTTP_200_OK)
