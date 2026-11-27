from usuarios.papelera import desactivar_ruta
from usuarios.papelera_views import respuesta_desactivar
from django.conf import settings
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.asignaciones import sincronizar_conductor_de_estudiantes
from usuarios.inasistencias import fecha_local, hoy_chile, ids_no_asisten
from usuarios.models import Notificacion, RecorridoRuta, Ruta
from usuarios.push_service import (
    crear_y_despachar_notificacion,
    notificar_inicio_ruta_agrupado,
)
from rutas.serializers import RutaSerializer
from usuarios.view_common import get_colegio_id_for_request

from usuarios.autorizaciones import contactos_para_llamar

from .abordaje import (
    corregir_abordaje,
    iniciar_reparto,
    marcar_apoderado_disponible,
    marcar_no_recibido,
    nombre_estudiante,
    paradas_pendientes,
    registrar_ausencia,
    registrar_llamada,
)
from .auditoria import registrar_evento, registrar_fin, registrar_inicio
from .donde_esta import donde_esta_hoy, resumen_de_fin
from .ubicacion import punto_de_la_casa, unir_detalle, verificar_en_el_punto


def es_administrador_rutas(user):
    return user.is_authenticated and (
        user.is_superuser or user.rol in ('admin_plataforma', 'admin_colegio')
    )


def obtener_ruta_operativa(request):
    ruta_id = request.data.get('ruta_id')
    rutas = Ruta.objects.select_related(
        'colegio', 'sede', 'furgon', 'conductor_perfil__usuario'
    ).prefetch_related(
        'estudiantes__apoderado__usuario', 'paradas_completadas',
        'estudiantes_abordados', 'estudiantes_entregados', 'estudiantes_ausentes',
    )

    if request.user.rol == 'conductor':
        perfil = getattr(request.user, 'perfil_conductor', None)
        if not perfil:
            return None
        rutas = rutas.filter(conductor_perfil=perfil)
    elif es_administrador_rutas(request.user):
        colegio_id = get_colegio_id_for_request(request)
        if colegio_id:
            rutas = rutas.filter(colegio_id=colegio_id)
    else:
        return None

    if ruta_id:
        return rutas.filter(pk=ruta_id).first()
    return rutas.filter(estado__in=('activa', 'en_ruta')).order_by('id').first()


def preparar_ruta_siguiente(rutas):
    """
    Rotación diaria del conductor: el día parte con la ida y, al finalizarla, sigue la vuelta.
    Una ruta finalizada se reabre al volver a ser la siguiente, con sus paradas limpias.
    Devuelve la ruta, o None si hay más de una activa para el mismo tramo.
    """
    ultima = rutas.filter(estado='finalizada', finalizada_en__isnull=False).order_by('-finalizada_en', '-id').first()
    hoy = hoy_chile()
    ultima_es_de_hoy = bool(ultima) and fecha_local(ultima.finalizada_en) == hoy
    sentido = 'desde_colegio' if ultima_es_de_hoy and ultima.sentido == 'hacia_colegio' else 'hacia_colegio'

    # Un conductor con un solo tramo sigue operando con ese tramo.
    candidatas = rutas.filter(sentido=sentido)
    if not candidatas.exists():
        candidatas = rutas

    activas = list(candidatas.filter(estado='activa')[:2])
    if len(activas) > 1:
        return None
    if activas:
        return activas[0]

    ruta = candidatas.filter(estado='finalizada').order_by('-finalizada_en', '-id').first()
    if ruta and (not ultima_es_de_hoy or ruta.pk != ultima.pk):
        ruta.paradas_completadas.clear()
        ruta.estudiantes_ausentes.clear()
        ruta.estudiantes_abordados.clear()
        ruta.estudiantes_entregados.clear()
        ruta.estado = 'activa'
        ruta.save(update_fields=['estado', 'updated_at'])
        return rutas.get(pk=ruta.pk)
    return ruta


class RutaConductorActualView(APIView):
    """Devuelve la ruta concreta asignada al conductor autenticado."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.rol != 'conductor':
            return Response(
                {'message': 'Este endpoint es exclusivo para conductores.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        perfil = getattr(request.user, 'perfil_conductor', None)
        if not perfil:
            return Response(
                {'message': 'El conductor autenticado no tiene un perfil asociado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        rutas = (
            Ruta.objects.select_related(
                'colegio', 'sede', 'furgon', 'conductor_perfil__usuario'
            )
            .prefetch_related(
                'estudiantes__apoderado__usuario', 'paradas_completadas',
                'estudiantes_abordados', 'estudiantes_entregados', 'estudiantes_ausentes',
            )
            .filter(
                conductor_perfil=perfil,
                estado__in=('activa', 'en_ruta', 'finalizada'),
            )
            .order_by('id')
        )

        en_ruta = list(rutas.filter(estado='en_ruta')[:2])
        if len(en_ruta) == 1:
            return Response(RutaSerializer(en_ruta[0]).data)
        if len(en_ruta) > 1:
            return Response(
                {'message': 'El conductor tiene más de una ruta marcada como en recorrido.'},
                status=status.HTTP_409_CONFLICT,
            )

        ruta = preparar_ruta_siguiente(rutas)
        if ruta is None and rutas.exists():
            return Response(
                {
                    'message': (
                        'Tienes más de una ruta activa para el mismo tramo. El administrador debe dejar '
                        'una sola para evitar iniciar el recorrido incorrecto.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        if ruta:
            return Response(RutaSerializer(ruta).data)

        if not rutas.exists():
            return Response(
                {'message': 'No tienes una ruta asignada actualmente.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {'message': 'No tienes una ruta activa disponible.'},
            status=status.HTTP_404_NOT_FOUND,
        )


class RutaActualizarUbicacionView(APIView):
    """Recibe la posición GPS del conductor durante una ruta en curso."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.rol != 'conductor':
            return Response(
                {'message': 'Solo el conductor puede actualizar la ubicación de la ruta.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        perfil = getattr(request.user, 'perfil_conductor', None)
        if not perfil:
            return Response(
                {'message': 'El conductor autenticado no tiene un perfil asociado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            latitud = float(request.data.get('latitud'))
            longitud = float(request.data.get('longitud'))
            precision = request.data.get('precision_metros')
            precision = float(precision) if precision not in (None, '') else None
        except (TypeError, ValueError):
            return Response(
                {'message': 'La latitud, longitud o precisión no tienen un formato válido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not -90 <= latitud <= 90 or not -180 <= longitud <= 180:
            return Response(
                {'message': 'Las coordenadas se encuentran fuera del rango permitido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if precision is not None and (precision < 0 or precision > 100000):
            return Response(
                {'message': 'La precisión GPS no tiene un valor válido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rutas = Ruta.objects.filter(conductor_perfil=perfil, estado='en_ruta')
        ruta_id = request.data.get('ruta_id')
        if ruta_id:
            rutas = rutas.filter(pk=ruta_id)
        ruta = rutas.order_by('id').first()
        if not ruta:
            return Response(
                {'message': 'No existe una ruta en recorrido asignada al conductor.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        ruta.ultima_latitud = latitud
        ruta.ultima_longitud = longitud
        ruta.precision_gps_metros = precision
        ruta.ubicacion_actualizada_en = timezone.now()
        ruta.save(update_fields=[
            'ultima_latitud', 'ultima_longitud',
            'precision_gps_metros', 'ubicacion_actualizada_en',
        ])

        return Response({
            'message': 'Ubicación actualizada.',
            'ruta_id': ruta.id,
            'ubicacion_actualizada_en': ruta.ubicacion_actualizada_en,
        })


class RutaListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not es_administrador_rutas(request.user):
            return Response({'message': 'No tiene permisos para administrar rutas.'}, status=status.HTTP_403_FORBIDDEN)
        colegio_id = get_colegio_id_for_request(request)
        rutas = Ruta.objects.select_related(
            'colegio', 'sede', 'furgon', 'conductor_perfil__usuario'
        ).prefetch_related('estudiantes', 'paradas_completadas')
        if colegio_id:
            rutas = rutas.filter(colegio_id=colegio_id)
        return Response(RutaSerializer(rutas.order_by('-id'), many=True).data)

    def post(self, request):
        if not es_administrador_rutas(request.user):
            return Response({'message': 'No tiene permisos para crear rutas.'}, status=status.HTTP_403_FORBIDDEN)
        data = request.data.copy()
        colegio_id = get_colegio_id_for_request(request) or data.get('colegio') or data.get('colegio_id')
        if colegio_id:
            data['colegio'] = colegio_id
        serializer = RutaSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


MENSAJE_RUTA_EN_CURSO = (
    'No se puede editar la ruta mientras está en curso. Espera a que el conductor la finalice.'
)


class RutaDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        colegio_id = get_colegio_id_for_request(request)
        rutas = Ruta.objects.select_related(
            'colegio', 'sede', 'furgon', 'conductor_perfil__usuario'
        ).prefetch_related('estudiantes', 'paradas_completadas').filter(pk=pk)
        if colegio_id:
            rutas = rutas.filter(colegio_id=colegio_id)
        try:
            return rutas.get()
        except Ruta.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        if not es_administrador_rutas(request.user):
            return Response({'message': 'No tiene permisos para administrar rutas.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(RutaSerializer(self.get_object(request, pk)).data)

    def put(self, request, pk):
        if not es_administrador_rutas(request.user):
            return Response({'message': 'No tiene permisos para editar rutas.'}, status=status.HTTP_403_FORBIDDEN)
        ruta = self.get_object(request, pk)
        if ruta.estado == 'en_ruta':
            # Cambiar estudiantes, furgón o conductor a mitad de un recorrido rompe el seguimiento.
            return Response({'message': MENSAJE_RUTA_EN_CURSO}, status=status.HTTP_409_CONFLICT)
        data = request.data.copy()
        colegio_id = get_colegio_id_for_request(request) or data.get('colegio') or data.get('colegio_id')
        if colegio_id:
            data['colegio'] = colegio_id
        serializer = RutaSerializer(ruta, data=data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    patch = put

    def delete(self, request, pk):
        if not es_administrador_rutas(request.user):
            return Response({'message': 'No tiene permisos para eliminar rutas.'}, status=status.HTTP_403_FORBIDDEN)
        return respuesta_desactivar(desactivar_ruta, self.get_object(request, pk))


class RutaSimulacionView(APIView):
    """Activa o desactiva el simulador de una ruta. Solo existe en modo demostración."""

    permission_classes = [IsAuthenticated]
    # Misma búsqueda que el detalle: respeta el colegio del administrador.
    get_object = RutaDetailView.get_object

    def post(self, request, pk):
        if not settings.MODO_DEMOSTRACION:
            return Response(
                {'message': 'El simulador solo está disponible en modo demostración.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not es_administrador_rutas(request.user):
            return Response({'message': 'No tiene permisos para administrar rutas.'}, status=status.HTTP_403_FORBIDDEN)
        ruta = self.get_object(request, pk)
        activa = request.data.get('activa') is True
        if activa and ruta.estado == 'finalizada':
            return Response(
                {'message': 'La ruta ya finalizó hoy. Reiníciala antes de simular un nuevo recorrido.'},
                status=status.HTTP_409_CONFLICT,
            )
        ruta.simulacion_activa = activa
        ruta.save(update_fields=['simulacion_activa', 'updated_at'])
        recorrido = RecorridoRuta.objects.filter(ruta=ruta, finalizado_en__isnull=True).order_by('-id').first()
        if recorrido and activa:
            # Un recorrido en curso que pasa a simularse no cuenta como real.
            recorrido.simulado = True
            recorrido.save(update_fields=['simulado'])
        return Response({
            'message': 'Simulación activada.' if activa else 'Simulación desactivada.',
            'ruta': RutaSerializer(ruta).data,
        })


class RutaIniciarView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ruta = obtener_ruta_operativa(request)
        if not ruta:
            return Response({'message': 'No existe una ruta autorizada para iniciar.'}, status=status.HTTP_404_NOT_FOUND)
        if ruta.estado == 'en_ruta':
            return Response({'message': 'La ruta ya se encuentra en recorrido.'}, status=status.HTTP_400_BAD_REQUEST)
        if ruta.estado == 'inactiva':
            return Response({'message': 'No se puede iniciar una ruta inactiva.'}, status=status.HTTP_400_BAD_REQUEST)
        if not ruta.conductor_perfil_id or not ruta.furgon_id:
            falta = 'furgón' if ruta.conductor_perfil_id else 'conductor'
            return Response(
                {'message': f'Esta ruta no tiene {falta} asignado. Pide al colegio que se lo asigne para poder iniciarla.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        establecimiento = ruta.sede if ruta.sede_id else ruta.colegio
        if (establecimiento is None
                or establecimiento.latitud is None
                or establecimiento.longitud is None
                or not (establecimiento.direccion or '').strip()):
            return Response({'message': 'El colegio o sede de destino debe tener dirección y coordenadas.'}, status=status.HTTP_400_BAD_REQUEST)

        estudiantes = list(ruta.estudiantes.select_related('apoderado__usuario'))
        if not estudiantes:
            return Response({'message': 'La ruta debe tener al menos un estudiante asignado.'}, status=status.HTTP_400_BAD_REQUEST)
        if any(
            not estudiante.ubicacion_confirmada
            or estudiante.latitud is None
            or estudiante.longitud is None
            for estudiante in estudiantes
        ):
            return Response(
                {'message': 'Todos los estudiantes deben tener una ubicación confirmada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(estudiantes) > ruta.furgon.capacidad:
            return Response({'message': 'La ruta supera la capacidad del furgón.'}, status=status.HTTP_400_BAD_REQUEST)

        # Posición del conductor al iniciar: con ella se ordena el recorrido desde el primer momento.
        try:
            latitud_inicio = float(request.data.get('latitud'))
            longitud_inicio = float(request.data.get('longitud'))
        except (TypeError, ValueError):
            latitud_inicio = longitud_inicio = None
        if latitud_inicio is not None and not (-90 <= latitud_inicio <= 90 and -180 <= longitud_inicio <= 180):
            latitud_inicio = longitud_inicio = None

        ruta.paradas_completadas.clear()
        ruta.estudiantes_ausentes.clear()
        ruta.estudiantes_entregados.clear()
        ruta.estudiantes_llamados.clear()
        ruta.estudiantes_no_recibidos.clear()
        if ruta.sentido == 'hacia_colegio':
            # Quien ya subió antes de iniciar no necesita parada en su domicilio.
            ruta.paradas_completadas.add(
                *ruta.estudiantes_abordados.filter(id__in=[est.id for est in estudiantes])
            )
        ruta.estado = 'en_ruta'
        ruta.iniciada_en = timezone.now()
        ruta.finalizada_en = None
        ruta.reparto_iniciado_en = None
        ruta.origen_recalculo_latitud = None
        ruta.origen_recalculo_longitud = None
        ruta.ultima_latitud = latitud_inicio
        ruta.ultima_longitud = longitud_inicio
        ruta.precision_gps_metros = None
        ruta.ubicacion_actualizada_en = timezone.now() if latitud_inicio is not None else None
        ruta.save(update_fields=[
            'estado', 'iniciada_en', 'finalizada_en', 'reparto_iniciado_en',
            'origen_recalculo_latitud', 'origen_recalculo_longitud',
            'ultima_latitud', 'ultima_longitud',
            'precision_gps_metros', 'ubicacion_actualizada_en', 'updated_at',
        ])
        ruta.furgon.estado = 'en_ruta'
        ruta.furgon.save(update_fields=['estado', 'updated_at'])
        registrar_inicio(ruta)

        # Ida y vuelta: todos los apoderados de la ruta, salvo los hijos con aviso "no asiste hoy".
        # En la vuelta nadie ha subido todavía al iniciar, así que no se filtra por abordados.
        no_asisten = ids_no_asisten(ruta)
        a_notificar = [est for est in estudiantes if est.id not in no_asisten]
        notificados = notificar_inicio_ruta_agrupado(ruta, a_notificar)
        return Response({
            'message': 'Ruta iniciada exitosamente.',
            'ruta': RutaSerializer(ruta).data,
            'notificados': notificados,
        })


class RutaAvisarLlegadaView(APIView):
    """
    Avisa SOLO al apoderado de ese niño que el furgón llegó a su casa. Es solo un aviso.
    Ida: llegó a buscarlo (la parada se completa al subir). Vuelta: llegó a dejarlo
    (se completa cuando la entrega se valida con rostro o QR).
    """

    permission_classes = [IsAuthenticated]
    TITULO = 'El furgón llegó al domicilio'
    TITULO_IDA = 'El furgón llegó a buscarlo'

    def post(self, request):
        ruta = obtener_ruta_operativa(request)
        if not ruta:
            return Response({'message': 'No existe una ruta autorizada.'}, status=status.HTTP_404_NOT_FOUND)
        if ruta.estado != 'en_ruta':
            return Response({'message': 'La ruta no se encuentra en recorrido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            estudiante_id = int(request.data.get('estudiante_id'))
        except (TypeError, ValueError):
            return Response({'message': 'Debes indicar un estudiante válido.'}, status=status.HTTP_400_BAD_REQUEST)

        es_ida = ruta.sentido == 'hacia_colegio'
        if es_ida:
            # Ida: el furgón llegó a buscarlo; todavía no sube.
            estudiante = ruta.estudiantes.select_related('apoderado__usuario').filter(pk=estudiante_id).first()
            if not estudiante:
                return Response({'message': 'El estudiante no pertenece a esta ruta.'}, status=status.HTTP_400_BAD_REQUEST)
            if ruta.estudiantes_abordados.filter(pk=estudiante.pk).exists():
                return Response({'message': 'El estudiante ya está a bordo del furgón.'}, status=status.HTTP_400_BAD_REQUEST)
            if ruta.paradas_completadas.filter(pk=estudiante.pk).exists() or estudiante.pk in ids_no_asisten(ruta):
                return Response({'message': 'Esta parada ya no está pendiente.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            estudiante = ruta.estudiantes_abordados.select_related('apoderado__usuario').filter(pk=estudiante_id).first()
            if not estudiante:
                return Response({'message': 'El estudiante no está a bordo del furgón.'}, status=status.HTTP_400_BAD_REQUEST)
            if ruta.estudiantes_entregados.filter(pk=estudiante.pk).exists():
                return Response({'message': 'El estudiante ya fue entregado.'}, status=status.HTTP_400_BAD_REQUEST)

        nombre = f'{estudiante.nombre} {estudiante.apellido}'.strip()
        titulo = self.TITULO_IDA if es_ida else self.TITULO
        ya_avisado = Notificacion.objects.filter(
            estudiante=estudiante, apoderado=estudiante.apoderado, titulo=titulo,
            creado_en__gte=ruta.iniciada_en,
        ).exists()
        if ya_avisado:
            return Response({'message': f'Ya se había avisado la llegada de {nombre}.', 'ya_avisado': True})
        # Solo se avisa la llegada estando en la casa del niño.
        try:
            nota_ubicacion = verificar_en_el_punto(ruta, punto_de_la_casa(estudiante))
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        crear_y_despachar_notificacion(
            apoderado=estudiante.apoderado,
            titulo=titulo,
            mensaje=(
                f'El furgón llegó a buscar a {nombre} a su domicilio ({estudiante.direccion_completa}). '
                'Que salga para subir al furgón.'
                if es_ida else
                f'El furgón llegó al domicilio de {nombre} ({estudiante.direccion_completa}). Prepárate para recibirlo.'
            ),
            tipo='estudiante_llego',
            estudiante=estudiante,
            ruta=ruta,
        )
        registrar_evento(
            ruta, 'aviso_llegada', estudiante,
            detalle=unir_detalle(estudiante.direccion_completa or '', nota_ubicacion),
        )
        falta = 'su subida' if es_ida else 'su entrega'
        return Response({'message': f'Se avisó la llegada a {nombre}. Falta registrar {falta}.', 'ya_avisado': False})


class RutaMarcarAusenteView(APIView):
    """Salta a un estudiante que no se presentó (ida) o que no subió en el colegio (vuelta) y avisa a su apoderado."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ruta = obtener_ruta_operativa(request)
        if not ruta:
            return Response({'message': 'No existe una ruta autorizada.'}, status=status.HTTP_404_NOT_FOUND)
        if ruta.estado != 'en_ruta':
            return Response({'message': 'La ruta no se encuentra en recorrido.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            estudiante_id = int(request.data.get('estudiante_id'))
        except (TypeError, ValueError):
            return Response({'message': 'Debes indicar un estudiante válido.'}, status=status.HTTP_400_BAD_REQUEST)

        estudiante = ruta.estudiantes.select_related('apoderado__usuario').filter(pk=estudiante_id).first()
        if not estudiante:
            return Response({'message': 'El estudiante no pertenece a esta ruta.'}, status=status.HTTP_400_BAD_REQUEST)
        if ruta.estudiantes_abordados.filter(pk=estudiante.pk).exists():
            return Response(
                {'message': 'El estudiante ya está a bordo del furgón.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ruta.paradas_completadas.filter(pk=estudiante.pk).exists():
            return Response(
                {'message': 'La parada de este estudiante ya fue completada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resultado = registrar_ausencia(ruta, estudiante)
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        notificacion = resultado.pop('notificacion', None)
        resultado['message'] = resultado['mensaje']
        resultado['notificado'] = notificacion is not None
        return Response(resultado)


class RutaIniciarRepartoView(APIView):
    """Vuelta: termina la subida en el colegio y habilita las entregas en las casas."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ruta = obtener_ruta_operativa(request)
        if not ruta:
            return Response({'message': 'No existe una ruta autorizada.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            resultado = iniciar_reparto(ruta)
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': resultado['mensaje']})


class RutaCorregirAbordajeView(APIView):
    """Vuelta: deja como "No subió" a un estudiante que quedó a bordo por error."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ruta = obtener_ruta_operativa(request)
        if not ruta:
            return Response({'message': 'No existe una ruta autorizada.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            estudiante_id = int(request.data.get('estudiante_id'))
        except (TypeError, ValueError):
            return Response({'message': 'Debes indicar un estudiante válido.'}, status=status.HTTP_400_BAD_REQUEST)
        estudiante = ruta.estudiantes.select_related('apoderado__usuario').filter(pk=estudiante_id).first()
        if not estudiante:
            return Response({'message': 'El estudiante no pertenece a esta ruta.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resultado = corregir_abordaje(ruta, estudiante)
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': resultado['mensaje']})


def _ruta_y_estudiante(request):
    """Ruta autorizada y estudiante indicado, o la respuesta de error."""
    ruta = obtener_ruta_operativa(request)
    if not ruta:
        return None, None, Response({'message': 'No existe una ruta autorizada.'}, status=status.HTTP_404_NOT_FOUND)
    try:
        estudiante_id = int(request.data.get('estudiante_id'))
    except (TypeError, ValueError):
        return None, None, Response({'message': 'Debes indicar un estudiante válido.'}, status=status.HTTP_400_BAD_REQUEST)
    estudiante = ruta.estudiantes.select_related('apoderado__usuario').filter(pk=estudiante_id).first()
    if not estudiante:
        return None, None, Response(
            {'message': 'El estudiante no pertenece a esta ruta.'}, status=status.HTTP_400_BAD_REQUEST,
        )
    return ruta, estudiante, None


class RutaContactosEstudianteView(APIView):
    """Teléfonos para llamar: se piden al tocar "Llamar", no viajan con la ruta."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _, estudiante, error = _ruta_y_estudiante(request)
        if error:
            return error
        return Response({'contactos': contactos_para_llamar(estudiante)})


class RutaRegistrarLlamadaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ruta, estudiante, error = _ruta_y_estudiante(request)
        if error:
            return error
        try:
            return Response(registrar_llamada(ruta, estudiante, request.data.get('contacto_id')))
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class RutaNoRecibidoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ruta, estudiante, error = _ruta_y_estudiante(request)
        if error:
            return error
        try:
            resultado = marcar_no_recibido(ruta, estudiante)
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': resultado['mensaje']})


class RutaApoderadoDisponibleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ruta, estudiante, error = _ruta_y_estudiante(request)
        if error:
            return error
        try:
            resultado = marcar_apoderado_disponible(ruta, estudiante)
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': resultado['mensaje']})


class RutaFinalizarView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ruta = obtener_ruta_operativa(request)
        if not ruta:
            return Response({'message': 'No existe una ruta autorizada para finalizar.'}, status=status.HTTP_404_NOT_FOUND)
        if ruta.estado != 'en_ruta':
            return Response({'message': 'La ruta no se encuentra en recorrido.'}, status=status.HTTP_400_BAD_REQUEST)

        # Quien va a bordo en la vuelta tiene su propio mensaje más abajo.
        sin_resolver = [
            estudiante for estudiante in paradas_pendientes(ruta)
            if ruta.sentido == 'hacia_colegio'
            or not ruta.estudiantes_abordados.filter(pk=estudiante.pk).exists()
        ]
        if sin_resolver:
            nombres = ', '.join(nombre_estudiante(estudiante) for estudiante in sin_resolver)
            accion = 'súbelos o márcalos como ausentes' if ruta.sentido == 'hacia_colegio' else 'súbelos o márcalos como "No subió"'
            return Response({
                'message': f'No puedes finalizar: faltan {nombres}. Primero {accion}.',
                'estudiantes_pendientes': len(sin_resolver),
            }, status=status.HTTP_409_CONFLICT)

        if ruta.sentido == 'hacia_colegio':
            pendientes = ruta.estudiantes_abordados.exclude(
                pk__in=ruta.estudiantes_entregados.values('pk')
            )
            cantidad_pendientes = pendientes.count()
            if cantidad_pendientes:
                return Response({
                    'message': (
                        'Antes de finalizar, escanea el QR del delegado o inspector '
                        'del colegio para registrar la recepción de los estudiantes.'
                    ),
                    'requiere_recepcion_institucional': True,
                    'ruta_id': ruta.id,
                    'estudiantes_pendientes': cantidad_pendientes,
                }, status=status.HTTP_409_CONFLICT)
        else:
            a_bordo = ruta.estudiantes_abordados.exclude(pk__in=ruta.estudiantes_entregados.values('pk'))
            vuelven = a_bordo.filter(pk__in=ruta.estudiantes_no_recibidos.values('pk'))
            en_casas = a_bordo.exclude(pk__in=vuelven.values('pk'))
            if en_casas.exists():
                nombres = ', '.join(f'{est.nombre} {est.apellido}'.strip() for est in en_casas)
                return Response({
                    'message': f'No puedes finalizar: aún van a bordo {nombres}. Regístralos como entregados con rostro o QR.',
                    'estudiantes_pendientes': en_casas.count(),
                }, status=status.HTTP_409_CONFLICT)
            if vuelven.exists():
                return Response({
                    'message': 'Antes de finalizar, escanea el QR del inspector para registrar a quienes vuelven al colegio.',
                    'requiere_recepcion_institucional': True,
                    'ruta_id': ruta.id,
                    'estudiantes_pendientes': vuelven.count(),
                }, status=status.HTTP_409_CONFLICT)

        ruta.estado = 'finalizada'
        ruta.finalizada_en = timezone.now()
        # La simulación vale para un recorrido: se apaga al terminarlo.
        ruta.simulacion_activa = False
        registrar_fin(ruta, ids_no_asisten(ruta))
        ruta.save(update_fields=['estado', 'finalizada_en', 'simulacion_activa', 'updated_at'])
        sincronizar_conductor_de_estudiantes(
            ruta.estudiantes.values_list('id', flat=True)
        )
        if ruta.furgon and ruta.furgon.estado == 'en_ruta':
            ruta.furgon.estado = 'disponible'
            ruta.furgon.save(update_fields=['estado', 'updated_at'])

        estudiantes_abordados = list(
            ruta.estudiantes_abordados.select_related('apoderado__usuario')
        )
        # Cada apoderado recibe dónde quedó su hijo, no solo que la ruta terminó.
        apoderados_notificados = set()
        for estudiante in estudiantes_abordados:
            crear_y_despachar_notificacion(
                apoderado=estudiante.apoderado,
                titulo='Ruta de ida terminada' if ruta.sentido == 'hacia_colegio' else 'Ruta de vuelta terminada',
                mensaje=f'{estudiante.nombre}: {donde_esta_hoy(estudiante)["detalle"]}',
                tipo='ruta_finalizada',
                estudiante=estudiante,
                ruta=ruta,
            )
            apoderados_notificados.add(estudiante.apoderado_id)
        notificados = len(apoderados_notificados)
        ruta.estudiantes_abordados.clear()
        return Response({
            'message': resumen_de_fin(ruta),
            'ruta': RutaSerializer(ruta).data,
            'notificados': notificados,
        })
