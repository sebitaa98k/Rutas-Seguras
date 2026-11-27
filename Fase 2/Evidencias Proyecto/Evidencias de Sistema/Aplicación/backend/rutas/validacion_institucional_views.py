"""Subida validada por un inspector con su QR."""
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notificaciones.serializers import NotificacionSerializer

from usuarios.autorizaciones import inspector_atiende
from usuarios.models import RegistroAbordaje, Ruta

from .abordaje import registrar_abordaje
from .comun import obtener_conductor_autenticado
from .ubicacion import lugar_de_subida, verificar_en_el_punto
from .qr_views import consumir_codigo, obtener_codigo_qr_firmado


def _contexto_validacion_institucional(request, bloquear=False):
    conductor = obtener_conductor_autenticado(request)
    if not conductor:
        return None, ('Solo un conductor autorizado puede validar el abordaje.', 403)

    try:
        ruta_id = int(request.data.get('ruta_id'))
        estudiante_id = int(request.data.get('estudiante_id'))
    except (TypeError, ValueError):
        return None, ('La ruta y el estudiante son obligatorios.', 400)

    codigo, error = obtener_codigo_qr_firmado(
        request.data.get('qr_payload'),
        bloquear=bloquear,
        proposito_esperado='entrega',
    )
    if error:
        return None, (error, 400)
    if codigo.estudiante_id:
        return None, ('El QR debe pertenecer a un delegado institucional.', 400)

    delegado = getattr(codigo.usuario, 'perfil_delegado', None)
    if (
        not codigo.usuario.is_active
        or not delegado
        or delegado.tipo_delegado != 'inspector'
    ):
        return None, ('El QR no pertenece a un delegado institucional activo.', 403)

    rutas = Ruta.objects.select_related('colegio', 'sede', 'conductor_perfil').filter(
        pk=ruta_id,
        conductor_perfil=conductor,
        sentido='desde_colegio',
        estado__in=('activa', 'en_ruta'),
    )
    if bloquear:
        rutas = rutas.select_for_update()
    ruta = rutas.first()
    if not ruta:
        return None, ('La ruta seleccionada no admite validacion institucional de abordaje.', 400)

    estudiante = ruta.estudiantes.select_related('colegio', 'sede', 'apoderado').filter(
        pk=estudiante_id,
        colegio_id=ruta.colegio_id,
    ).first()
    if not estudiante:
        return None, ('El estudiante no pertenece a la ruta y colegio seleccionados.', 403)
    if delegado.colegio_id != ruta.colegio_id:
        return None, ('El delegado no corresponde al colegio de la ruta.', 403)

    if not inspector_atiende(delegado, estudiante):
        return None, ('El inspector no corresponde a la sede del estudiante.', 403)

    if ruta.estudiantes_abordados.filter(pk=estudiante.pk).exists():
        return None, ('El estudiante ya tiene un abordaje registrado en esta ruta.', 409)
    if ruta.reparto_iniciado_en:
        return None, ('El reparto ya comenzó: no pueden subir más estudiantes.', 409)

    return {
        'codigo': codigo,
        'ruta': ruta,
        'estudiante': estudiante,
        'delegado': delegado,
        'conductor': conductor,
    }, None


def _respuesta_contexto_institucional(contexto):
    ruta = contexto['ruta']
    estudiante = contexto['estudiante']
    delegado = contexto['delegado']
    return {
        'valido': True,
        'ruta': {'id': ruta.id, 'nombre': ruta.nombre, 'estado': ruta.estado},
        'estudiante': {
            'id': estudiante.id,
            'nombre': f'{estudiante.nombre} {estudiante.apellido}'.strip(),
            'rut': estudiante.rut,
            'curso': estudiante.curso,
        },
        'delegado': {
            'id': delegado.id,
            'nombre': delegado.usuario.get_full_name() or delegado.usuario.email,
            'rut': delegado.rut or '',
            'colegio': ruta.colegio.nombre if ruta.colegio_id else '',
            'sede': ruta.sede.nombre if ruta.sede_id and not ruta.sede.oculta else '',
        },
        'metodo_validacion': 'validacion_institucional',
    }


class RutaConsultarValidacionInstitucionalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        contexto, error = _contexto_validacion_institucional(request)
        if error:
            mensaje, codigo_estado = error
            return Response({'valido': False, 'message': mensaje}, status=codigo_estado)
        return Response(_respuesta_contexto_institucional(contexto))


class RutaConfirmarAbordajeInstitucionalView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        contexto, error = _contexto_validacion_institucional(request, bloquear=True)
        if error:
            mensaje, codigo_estado = error
            return Response({'message': mensaje}, status=codigo_estado)

        codigo = contexto['codigo']
        # Antes de gastar el QR: una vez consumido no se puede volver a usar.
        try:
            verificar_en_el_punto(contexto['ruta'], lugar_de_subida(contexto['ruta'], contexto['estudiante']))
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not consumir_codigo(codigo):
            return Response(
                {'message': 'El codigo QR ya fue utilizado o ha expirado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        abordaje = registrar_abordaje(
            contexto['ruta'],
            contexto['estudiante'],
            metodo='validacion_institucional',
            delegado=contexto['delegado'],
        )
        notificacion = abordaje.pop('notificacion', None)
        registro = RegistroAbordaje.objects.filter(
            ruta=contexto['ruta'], estudiante=contexto['estudiante']
        ).first()
        return Response({
            'message': abordaje['mensaje'],
            'abordaje': abordaje,
            'registro_abordaje_id': registro.id,
            'metodo_validacion': registro.metodo_validacion,
            'delegado': _respuesta_contexto_institucional(contexto)['delegado'],
            'notificacion': NotificacionSerializer(notificacion).data if notificacion else None,
        })
