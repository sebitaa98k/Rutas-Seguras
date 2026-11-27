from django.db.models import Q
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.models import AceptacionTerminos, CambioBiometria, ConsentimientoBiometrico, Usuario
from usuarios.permissions import IsAdministrador
from autenticacion.serializers import UsuarioResponseSerializer
from usuarios.terminos import (
    TITULO,
    VERSION_VIGENTE,
    debe_aceptar_terminos,
    registrar_aceptacion,
    texto_terminos,
)
from usuarios.view_common import get_colegio_id_for_request, queryset_usuarios_por_colegio

LIMITE_REGISTROS = 200


class TerminosVigentesView(APIView):
    """Público: el apoderado los lee antes de tener una cuenta."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'version': VERSION_VIGENTE, 'titulo': TITULO, 'contenido': texto_terminos()})


class AceptarTerminosView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        usuario = request.user
        if not debe_aceptar_terminos(usuario):
            return Response({
                'message': 'No tienes términos pendientes.',
                'usuario': UsuarioResponseSerializer(usuario).data,
            })
        if request.data.get('version') != VERSION_VIGENTE:
            return Response(
                {'message': 'Los términos cambiaron. Vuelve a leerlos y acéptalos.'},
                status=409,
            )
        if request.data.get('acepta_terminos') is not True:
            return Response(
                {'message': 'Debes aceptar los términos y condiciones para continuar.'},
                status=400,
            )

        # Desde la versión 1.2 los términos no incluyen la biometría: se autoriza por cada hijo.
        registrar_aceptacion(usuario, 'ingreso', request)
        return Response({
            'message': 'Términos aceptados.',
            'usuario': UsuarioResponseSerializer(usuario).data,
        })


def _hijos_de(usuario, colegio_id):
    """Los hijos del apoderado con su colegio. El admin de un colegio ve solo los suyos con nombre;
    los de otros colegios aparecen solo como cantidad (no son datos de su colegio)."""
    perfil = getattr(usuario, 'perfil_apoderado', None) if usuario else None
    if not perfil:
        return [], 0
    hijos, otros = [], 0
    for estudiante in perfil.estudiantes.all():
        if colegio_id and estudiante.colegio_id != colegio_id:
            otros += 1
            continue
        hijos.append({
            'id': estudiante.id,
            'nombre': f'{estudiante.nombre} {estudiante.apellido}'.strip(),
            'colegio_id': estudiante.colegio_id,
            'colegio_nombre': estudiante.colegio.nombre if estudiante.colegio_id else '',
            # Consentimiento biométrico de este hijo (términos 1.2): lo que rige hoy.
            'autoriza_biometria': bool(estudiante.autoriza_biometria),
            'autoriza_biometria_en': estudiante.autoriza_biometria_en,
        })
    return hijos, otros


def _datos_aceptacion(item, colegio_id=None):
    hijos, hijos_otros_colegios = _hijos_de(item.usuario, colegio_id)
    return {
        'id': item.id,
        'nombre': item.nombre,
        'rut': item.rut,
        'email': item.email,
        'colegio_nombre': item.colegio_nombre,
        'version': item.version,
        'huella_texto': item.huella_texto,
        # Solo en las versiones 1.0 y 1.1, cuando era una casilla general al aceptar.
        'acepta_biometria': item.acepta_biometria,
        'origen': item.origen,
        'origen_nombre': item.get_origen_display(),
        'ip': item.ip,
        'dispositivo': item.dispositivo,
        'aceptado_en': item.aceptado_en,
        # Una aceptación vale para todos sus hijos, aunque estén en colegios distintos.
        'hijos': hijos,
        'hijos_otros_colegios': hijos_otros_colegios,
    }


def _datos_cambio_biometria(item):
    return {
        'id': item.id,
        'nombre': item.nombre,
        'rut': item.rut,
        'email': item.email,
        'colegio_nombre': item.colegio_nombre,
        'autoriza': item.autoriza,
        'origen': item.origen,
        'origen_nombre': item.get_origen_display(),
        'fotos_eliminadas': item.fotos_eliminadas,
        'ip': item.ip,
        'dispositivo': item.dispositivo,
        'creado_en': item.creado_en,
    }


def _datos_consentimiento(item):
    return {
        'id': item.id,
        'estudiante_id': item.estudiante_id,
        'estudiante_nombre': item.estudiante_nombre,
        'estudiante_rut': item.estudiante_rut,
        'apoderado_nombre': item.apoderado_nombre,
        'apoderado_rut': item.apoderado_rut,
        'apoderado_email': item.apoderado_email,
        'colegio_nombre': item.colegio_nombre,
        'evento': item.evento,
        'evento_nombre': item.get_evento_display(),
        'origen': item.origen,
        'origen_nombre': item.get_origen_display(),
        'version_terminos': item.version_terminos,
        'datos_eliminados': item.datos_eliminados,
        'ip': item.ip,
        'dispositivo': item.dispositivo,
        'creado_en': item.creado_en,
    }


def _datos_pendiente(usuario):
    perfil = getattr(usuario, 'perfil_apoderado', None)
    return {
        'id': usuario.id,
        'nombre': usuario.get_full_name(),
        'rut': (perfil.rut or '') if perfil else '',
        'email': usuario.email,
        'colegio_nombre': usuario.colegio.nombre if usuario.colegio_id else '',
        'debe_cambiar_password': usuario.debe_cambiar_password,
    }


class AuditoriaTerminosView(APIView):
    """Quiénes aceptaron y quiénes siguen pendientes. Es solo de lectura."""

    permission_classes = [IsAdministrador]

    def get(self, request):
        colegio_id = get_colegio_id_for_request(request)
        aceptaciones = AceptacionTerminos.objects.select_related('usuario').prefetch_related(
            'usuario__perfil_apoderado__estudiantes__colegio',
        )
        cambios_biometria = CambioBiometria.objects.all()
        consentimientos = ConsentimientoBiometrico.objects.all()
        pendientes = Usuario.objects.select_related('perfil_apoderado', 'colegio').filter(
            rol='apoderado', is_active=True, is_superuser=False, is_staff=False,
        ).exclude(terminos_version_aceptada=VERSION_VIGENTE)

        if colegio_id:
            # También la ve el colegio donde tiene un hijo o está habilitado (apoderado en varios colegios).
            aceptaciones = aceptaciones.filter(
                Q(colegio_id=colegio_id)
                | Q(usuario__perfil_apoderado__estudiantes__colegio_id=colegio_id)
                | Q(
                    usuario__perfil_apoderado__ruts_habilitados__colegio_id=colegio_id,
                    usuario__perfil_apoderado__ruts_habilitados__activo=True,
                )
            ).distinct()
            cambios_biometria = cambios_biometria.filter(colegio_id=colegio_id)
            consentimientos = consentimientos.filter(colegio_id=colegio_id)
            pendientes = queryset_usuarios_por_colegio(pendientes, colegio_id, 'apoderado')

        buscar = (request.query_params.get('buscar') or '').strip()
        if buscar:
            aceptaciones = aceptaciones.filter(
                Q(nombre__icontains=buscar) | Q(rut__icontains=buscar) | Q(email__icontains=buscar)
            )
            cambios_biometria = cambios_biometria.filter(
                Q(nombre__icontains=buscar) | Q(rut__icontains=buscar) | Q(email__icontains=buscar)
            )
            consentimientos = consentimientos.filter(
                Q(estudiante_nombre__icontains=buscar) | Q(estudiante_rut__icontains=buscar)
                | Q(apoderado_nombre__icontains=buscar) | Q(apoderado_rut__icontains=buscar)
                | Q(apoderado_email__icontains=buscar)
            )
            pendientes = pendientes.filter(
                Q(first_name__icontains=buscar) | Q(last_name__icontains=buscar)
                | Q(email__icontains=buscar) | Q(perfil_apoderado__rut__icontains=buscar)
            )

        return Response({
            'version_vigente': VERSION_VIGENTE,
            'limite': LIMITE_REGISTROS,
            'aceptaciones': [_datos_aceptacion(item, colegio_id) for item in aceptaciones[:LIMITE_REGISTROS]],
            'pendientes': [_datos_pendiente(item) for item in pendientes.order_by('-id')[:LIMITE_REGISTROS]],
            # Consentimiento por hijo (términos 1.2): constancias inmutables.
            'consentimientos_biometria': [_datos_consentimiento(item) for item in consentimientos[:LIMITE_REGISTROS]],
            # Historial antiguo: autorización general del apoderado (términos 1.0 y 1.1).
            'cambios_biometria': [_datos_cambio_biometria(item) for item in cambios_biometria[:LIMITE_REGISTROS]],
        })
