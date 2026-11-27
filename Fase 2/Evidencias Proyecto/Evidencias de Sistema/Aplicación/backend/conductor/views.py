from rest_framework.exceptions import ValidationError
from usuarios.models import PerfilConductor
from usuarios.rut import validar_rut
from usuarios.rut_unico import CONDUCTOR, rut_ocupado
from usuarios.papelera import desactivar_conductor
from usuarios.papelera_views import respuesta_desactivar
from usuarios.password_inicial import aplicar_password_inicial, password_provisoria
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from usuarios.models import Estudiante, PerfilConductor, Ruta, Usuario
from usuarios.permissions import IsAdministrador, es_admin_colegio, es_admin_plataforma
from usuarios.push_service import crear_y_despachar_notificacion
from conductor.serializers import ConductorSerializer, RegistroConductorSerializer
from estudiantes.serializers import EstudianteSerializer
from rutas.serializers import RutaSerializer
from usuarios.view_common import get_colegio_id_for_request
from usuarios.asignaciones import (
    ESTADOS_RUTA_VIGENTE,
    estudiantes_del_conductor,
    sincronizar_conductor_de_estudiantes,
)

def obtener_perfil_conductor(request, conductor_id):
    colegio_id = get_colegio_id_for_request(request)
    qs = Usuario.objects.filter(id=conductor_id, rol='conductor')
    if colegio_id:
        qs = qs.filter(colegio_id=colegio_id)
    try:
        conductor_user = qs.get()
        return conductor_user, conductor_user.perfil_conductor
    except (Usuario.DoesNotExist, PerfilConductor.DoesNotExist):
        raise Http404


def respuesta_estudiantes_conductor(perfil_conductor, mensaje):
    estudiantes = estudiantes_del_conductor(perfil_conductor)
    return Response({
        'message': mensaje,
        'estudiantes': EstudianteSerializer(estudiantes, many=True).data
    }, status=status.HTTP_200_OK)


class ConductorEstudiantesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conductor_id):
        es_conductor_propietario = (
            request.user.rol == 'conductor' and request.user.id == conductor_id
        )
        es_administrador = es_admin_plataforma(request.user) or es_admin_colegio(request.user)
        if not es_conductor_propietario and not es_administrador:
            return Response(
                {'message': 'No tiene permiso para consultar los estudiantes de este conductor.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        _, perfil_conductor = obtener_perfil_conductor(request, conductor_id)
        estudiantes = estudiantes_del_conductor(perfil_conductor)
        serializer = EstudianteSerializer(estudiantes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConductorAsignarEstudiantesView(APIView):
    """Agrega estudiantes a la ruta del conductor; la ruta es la fuente de verdad."""
    permission_classes = [IsAdministrador]

    def post(self, request, conductor_id):
        conductor_user, perfil_conductor = obtener_perfil_conductor(request, conductor_id)

        estudiante_ids = request.data.get('estudiante_ids', [])
        if not isinstance(estudiante_ids, list):
            return Response({'message': 'El formato de estudiante_ids debe ser una lista.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            estudiante_ids = {int(estudiante_id) for estudiante_id in estudiante_ids}
        except (TypeError, ValueError):
            return Response({'message': 'La lista de estudiantes no es válida.'}, status=status.HTTP_400_BAD_REQUEST)

        rutas = list(Ruta.objects.filter(conductor_perfil=perfil_conductor, estado__in=ESTADOS_RUTA_VIGENTE)[:2])
        if not rutas:
            return Response({
                'message': 'El conductor no tiene una ruta. Crea una ruta en el módulo Rutas para asignarle estudiantes.'
            }, status=status.HTTP_400_BAD_REQUEST)
        if len(rutas) > 1:
            return Response({
                'message': 'El conductor tiene más de una ruta. Agrega los estudiantes desde la ruta correspondiente en el módulo Rutas.'
            }, status=status.HTTP_400_BAD_REQUEST)
        ruta = rutas[0]
        if ruta.estado == 'en_ruta':
            return Response({'message': 'No se pueden modificar los estudiantes de una ruta en recorrido.'}, status=status.HTTP_400_BAD_REQUEST)

        actuales = set(ruta.estudiantes.values_list('id', flat=True))
        nuevos = estudiante_ids - actuales
        serializer = RutaSerializer(
            ruta,
            data={'estudiantes': sorted(actuales | estudiante_ids)},
            partial=True,
            context={'request': request},
        )
        if not serializer.is_valid():
            errores = serializer.errors
            mensaje = next(iter(errores.values()))
            mensaje = mensaje[0] if isinstance(mensaje, list) else mensaje
            return Response({'message': str(mensaje), 'errors': errores}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        nombre_conductor = conductor_user.get_full_name() or conductor_user.email
        for est in Estudiante.objects.filter(id__in=nuevos).select_related('apoderado__usuario'):
            if est.apoderado:
                nombre_estudiante = f"{est.nombre} {est.apellido}".strip()
                crear_y_despachar_notificacion(
                    apoderado=est.apoderado,
                    titulo="Conductor asignado",
                    mensaje=f"{nombre_conductor} será el conductor de transporte de {nombre_estudiante} en la ruta {ruta.nombre}.",
                    tipo="aviso_sistema",
                    estudiante=est
                )

        return respuesta_estudiantes_conductor(
            perfil_conductor, f'{len(nuevos)} estudiantes agregados a la ruta {ruta.nombre}.'
        )


class ConductorDesasignarEstudianteView(APIView):
    """Quita al estudiante de las rutas del conductor."""
    permission_classes = [IsAdministrador]

    def post(self, request, conductor_id):
        _, perfil_conductor = obtener_perfil_conductor(request, conductor_id)

        estudiante_id = request.data.get('estudiante_id')
        if not estudiante_id:
            return Response({'message': 'Debe especificar el estudiante_id.'}, status=status.HTTP_400_BAD_REQUEST)

        estudiante = Estudiante.objects.filter(id=estudiante_id).select_related('apoderado__usuario').first()
        if not estudiante:
            raise Http404
        rutas = list(Ruta.objects.filter(conductor_perfil=perfil_conductor, estudiantes=estudiante))
        if not rutas:
            return Response({'message': 'El estudiante no pertenece a una ruta de este conductor.'}, status=status.HTTP_400_BAD_REQUEST)
        if any(ruta.estado == 'en_ruta' for ruta in rutas):
            return Response({'message': 'No se pueden modificar los estudiantes de una ruta en recorrido.'}, status=status.HTTP_400_BAD_REQUEST)
        if any(ruta.estudiantes.count() <= 1 for ruta in rutas):
            return Response({
                'message': 'El estudiante es el único de la ruta. Edita o elimina la ruta desde el módulo Rutas.'
            }, status=status.HTTP_400_BAD_REQUEST)

        for ruta in rutas:
            ruta.estudiantes.remove(estudiante)
            ruta.estudiantes_count = ruta.estudiantes.count()
            ruta.save(update_fields=['estudiantes_count', 'updated_at'])
        sincronizar_conductor_de_estudiantes([estudiante.id])

        if estudiante.apoderado:
            nombre_estudiante = f"{estudiante.nombre} {estudiante.apellido}".strip()
            crear_y_despachar_notificacion(
                apoderado=estudiante.apoderado,
                titulo="Cambio en transporte escolar",
                mensaje=f"{nombre_estudiante} fue retirado de la ruta de su conductor de transporte.",
                tipo="aviso_sistema",
                estudiante=estudiante
            )

        return respuesta_estudiantes_conductor(perfil_conductor, 'Estudiante quitado de la ruta exitosamente.')

class ConductorListCreateView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request):
        colegio_id = get_colegio_id_for_request(request)
        # Los desactivados están en la papelera.
        conductores = Usuario.objects.filter(rol='conductor', is_active=True)
        if colegio_id:
            conductores = conductores.filter(colegio_id=colegio_id)
        conductores = conductores.order_by('-id')
        serializer = ConductorSerializer(conductores, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data.copy()
        colegio_solicitado = data.get('colegio_id')
        if es_admin_plataforma(request.user) and colegio_solicitado:
            target_colegio_id = colegio_solicitado
        else:
            target_colegio_id = get_colegio_id_for_request(request) or colegio_solicitado
        if target_colegio_id:
            data['colegio_id'] = target_colegio_id

        data['password'] = password_provisoria()
        serializer = RegistroConductorSerializer(data=data)
        if serializer.is_valid():
            usuario = serializer.save()
            password_inicial = aplicar_password_inicial(usuario, usuario.perfil_conductor.rut)
            user_data = ConductorSerializer(usuario).data
            return Response({
                'message': 'Conductor registrado exitosamente.',
                'conductor': user_data,
                'password_inicial': password_inicial,
            }, status=status.HTTP_201_CREATED)
        return Response({
            'message': 'Error al registrar el conductor.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ConductorDetailView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request, conductor_id):
        colegio_id = get_colegio_id_for_request(request)
        try:
            qs = Usuario.objects.filter(id=conductor_id, rol='conductor')
            if colegio_id:
                qs = qs.filter(colegio_id=colegio_id)
            conductor = qs.get()
        except Usuario.DoesNotExist:
            raise Http404
        return Response(ConductorSerializer(conductor).data, status=status.HTTP_200_OK)

    def patch(self, request, conductor_id):
        colegio_id = get_colegio_id_for_request(request)
        try:
            qs = Usuario.objects.filter(id=conductor_id, rol='conductor')
            if colegio_id:
                qs = qs.filter(colegio_id=colegio_id)
            conductor = qs.get()
        except Usuario.DoesNotExist:
            raise Http404

        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        if first_name is not None:
            conductor.first_name = first_name.strip()
        if last_name is not None:
            conductor.last_name = last_name.strip()

        nombre = request.data.get('nombre') or request.data.get('nombre_completo')
        if nombre and first_name is None:
            parts = nombre.strip().split(' ', 1)
            conductor.first_name = parts[0]
            conductor.last_name = parts[1] if len(parts) > 1 else ''

        email = request.data.get('email')
        if email and email.lower().strip() != conductor.email:
            new_email = email.lower().strip()
            if Usuario.objects.filter(email=new_email).exclude(id=conductor.id).exists():
                return Response({'message': 'El correo electrónico ya está registrado.'}, status=status.HTTP_400_BAD_REQUEST)
            conductor.email = new_email
            conductor.username = new_email

        password = request.data.get('password')
        if password:
            conductor.set_password(password)
            conductor.debe_cambiar_password = True

        if 'colegio_id' in request.data and (request.user.rol in ['admin_plataforma'] or request.user.is_superuser):
            conductor.colegio_id = request.data['colegio_id']

        conductor.save()

        if hasattr(conductor, 'perfil_conductor'):
            perfil = conductor.perfil_conductor
            if 'rut' in request.data:
                try:
                    rut = validar_rut(request.data['rut'])
                except ValidationError as exc:
                    return Response({'message': exc.detail[0]}, status=status.HTTP_400_BAD_REQUEST)
                if PerfilConductor.objects.filter(rut=rut).exclude(pk=perfil.pk).exists():
                    return Response({'message': 'Este RUT ya está registrado como conductor.'}, status=400)
                mensaje = rut_ocupado(rut, permitir={CONDUCTOR})
                if mensaje:
                    return Response({'message': mensaje}, status=400)
                perfil.rut = rut
            if 'telefono' in request.data:
                perfil.telefono = request.data['telefono'].strip()
            if 'licencia_conducir' in request.data:
                perfil.licencia_conducir = request.data['licencia_conducir'].strip()
            if conductor.colegio_id:
                perfil.colegio_id = conductor.colegio_id
            perfil.save()

        return Response({
            'message': 'Conductor actualizado exitosamente.',
            'conductor': ConductorSerializer(conductor).data
        }, status=status.HTTP_200_OK)

    def delete(self, request, conductor_id):
        colegio_id = get_colegio_id_for_request(request)
        try:
            qs = Usuario.objects.filter(id=conductor_id, rol='conductor')
            if colegio_id:
                qs = qs.filter(colegio_id=colegio_id)
            conductor = qs.get()
        except Usuario.DoesNotExist:
            raise Http404

        return respuesta_desactivar(desactivar_conductor, conductor)
