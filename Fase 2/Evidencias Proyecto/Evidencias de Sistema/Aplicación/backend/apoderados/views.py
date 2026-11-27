from usuarios.papelera import desactivar_apoderado
from usuarios.papelera_views import respuesta_desactivar
from usuarios.password_inicial import aplicar_password_inicial, password_provisoria
from django.db.models import Q
from django.http import Http404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from usuarios.models import Estudiante, Usuario
from usuarios.permissions import IsAdministrador
from apoderados.serializers import ApoderadoSerializer, RegistroApoderadoSerializer
from autenticacion.serializers import UsuarioResponseSerializer
from estudiantes.serializers import EstudianteSerializer
from usuarios.view_common import get_colegio_id_for_request, queryset_usuarios_por_colegio
from usuarios.rut import validar_rut
from usuarios.vinculos import (
    colegios_del_apoderado, desvincular_apoderado, es_colegio_dueno, puede_editar_apoderado, vincular_apoderado,
)
from django.db import transaction

from usuarios.models import Colegio, PerfilApoderado
from usuarios.permissions import IsApoderado


class ApoderadoPerfilView(APIView):
    permission_classes = [IsAuthenticated, IsApoderado]

    def get(self, request):
        return Response(UsuarioResponseSerializer(request.user).data, status=status.HTTP_200_OK)

    def patch(self, request):
        usuario = request.user
        perfil = getattr(usuario, 'perfil_apoderado', None)
        if perfil is None:
            raise Http404

        if 'first_name' in request.data:
            usuario.first_name = (request.data.get('first_name') or '').strip()
        if 'last_name' in request.data:
            usuario.last_name = (request.data.get('last_name') or '').strip()
        if not usuario.first_name:
            return Response(
                {'message': 'El nombre es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if 'telefono' in request.data:
            perfil.telefono = (request.data.get('telefono') or '').strip()

        usuario.save(update_fields=['first_name', 'last_name'])
        perfil.save(update_fields=['telefono', 'updated_at'])
        return Response({
            'message': 'Perfil actualizado correctamente.',
            'usuario': UsuarioResponseSerializer(usuario).data,
        }, status=status.HTTP_200_OK)


class RegistroApoderadoView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistroApoderadoSerializer(
            data=request.data,
            context={'request_registro': request},
        )
        if serializer.is_valid():
            usuario = serializer.save()
            token, _ = Token.objects.get_or_create(user=usuario)
            user_data = UsuarioResponseSerializer(usuario).data
            return Response({
                'message': 'Apoderado registrado exitosamente.',
                'token': token.key,
                'usuario': user_data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'message': 'Error en el registro.',
            'errors': serializer.errors,
            'contacto_colegio': serializer.contacto_colegio,
        }, status=status.HTTP_400_BAD_REQUEST)


class ColegiosRegistroView(APIView):
    """Público: colegios que el apoderado puede elegir al crear su cuenta."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        colegios = Colegio.objects.filter(activo=True).order_by('nombre').values('id', 'nombre', 'comuna')
        return Response(list(colegios), status=status.HTTP_200_OK)


def _crear_estudiantes_del_apoderado(perfil, estudiantes_data, target_colegio_id):
    """Hijos que el colegio registra junto con el apoderado (o al vincularlo). No necesitan habilitación."""
    for index, estudiante_data in enumerate(estudiantes_data):
        estudiante_data = dict(estudiante_data)
        nombre_completo = estudiante_data.pop('nombre_completo', '').strip()
        if nombre_completo and not estudiante_data.get('nombre'):
            partes = nombre_completo.split(' ', 1)
            estudiante_data['nombre'] = partes[0]
            estudiante_data['apellido'] = partes[1] if len(partes) > 1 else ''

        direccion = estudiante_data.pop('direccion_retiro', None)
        if direccion is not None:
            estudiante_data['direccion_principal'] = direccion

        # El formulario de apoderados mostraba el colegio como texto. La
        # asociación real siempre debe provenir del colegio autorizado.
        estudiante_data.pop('colegio', None)
        # La biometría se registra después de que el apoderado acepte los términos.
        estudiante_data.pop('foto', None)
        if target_colegio_id:
            estudiante_data['colegio'] = target_colegio_id
        estudiante_data.pop('estado_matricula', None)
        estudiante_data.pop('activo', None)
        estudiante_data['apoderado'] = perfil.id
        estudiante_data['ubicacion_confirmada'] = (
            estudiante_data.get('latitud') is not None
            and estudiante_data.get('longitud') is not None
        )

        estudiante_serializer = EstudianteSerializer(data=estudiante_data)
        if not estudiante_serializer.is_valid():
            raise ValidationError({
                'estudiantes': {index: estudiante_serializer.errors}
            })
        estudiante_serializer.save()


class ApoderadoListCreateView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request):
        colegio_id = get_colegio_id_for_request(request)
        apoderados = Usuario.objects.filter(rol='apoderado', is_active=True, is_superuser=False, is_staff=False)
        apoderados = queryset_usuarios_por_colegio(apoderados, colegio_id, 'apoderado')
        apoderados = apoderados.order_by('-id')
        serializer = ApoderadoSerializer(apoderados, many=True, context={'colegio_id': colegio_id})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data.copy()
        estudiantes_data = data.pop('estudiantes', [])
        target_colegio_id = get_colegio_id_for_request(request) or data.get('colegio_id')
        if not target_colegio_id:
            # Sin colegio la cuenta quedaba huérfana y sin su RUT habilitado en ningún colegio.
            return Response({
                'message': 'Elige un colegio en el selector de arriba a la derecha para registrar al apoderado.',
                'errors': {'colegio_id': ['El colegio es obligatorio.']},
            }, status=status.HTTP_400_BAD_REQUEST)
        data['colegio_id'] = target_colegio_id

        if 'nombre_completo' in data and not data.get('nombre'):
            parts = data['nombre_completo'].strip().split(' ', 1)
            data['nombre'] = parts[0]
            data['apellido'] = parts[1] if len(parts) > 1 else ''
        if 'usuario' in data and not data.get('email'):
            data['email'] = data['usuario']
        # El apoderado ya tiene cuenta en otro colegio: no se crea otra, se vincula a este.
        existente = _apoderado_con_rut(data.get('rut'))
        if existente is not None:
            return self._vincular_existente(request, existente, data, estudiantes_data, target_colegio_id)

        # El administrador no elige la contraseña: se asigna la de la regla tras crear la cuenta.
        data['password'] = password_provisoria()

        serializer = RegistroApoderadoSerializer(data=data, context={'creado_por': request.user})
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    usuario = serializer.save()
                    perfil = usuario.perfil_apoderado
                    password_inicial = aplicar_password_inicial(usuario, perfil.rut)

                    _crear_estudiantes_del_apoderado(perfil, estudiantes_data, target_colegio_id)

                    user_data = ApoderadoSerializer(
                        usuario,
                        context={'colegio_id': target_colegio_id}
                    ).data
            except ValidationError as exc:
                return Response({
                    'message': 'Error al registrar los estudiantes del apoderado.',
                    'errors': exc.detail
                }, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'message': 'Apoderado y estudiantes registrados exitosamente.',
                'apoderado': user_data,
                'password_inicial': password_inicial,
            }, status=status.HTTP_201_CREATED)
        return Response({
            'message': 'Error al registrar el apoderado.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def _vincular_existente(self, request, perfil, data, estudiantes_data, target_colegio_id):
        colegio = Colegio.objects.filter(pk=target_colegio_id, activo=True).first()
        if colegio is None:
            return Response({'message': 'El colegio seleccionado no existe o está desactivado.'}, status=400)
        if not perfil.usuario.is_active:
            return Response({
                'message': 'Ese RUT es de una cuenta desactivada. Reactívala desde la papelera antes de vincularla.',
            }, status=status.HTTP_409_CONFLICT)
        if colegio.id in colegios_del_apoderado(perfil):
            return Response({'message': 'Este apoderado ya está registrado en este colegio.'}, status=400)
        usuario = perfil.usuario
        datos_existente = {
            'nombre': usuario.get_full_name() or usuario.email,
            'email': usuario.email,
            'rut': perfil.rut,
            'colegio_dueno': perfil.colegio.nombre if perfil.colegio_id else '',
        }
        if str(data.get('vincular', '')).lower() not in ('1', 'true', 'si', 'sí'):
            # La pantalla pregunta antes de vincular, para que el colegio sepa que la cuenta ya existe.
            return Response({
                'message': (
                    f'Este apoderado ya tiene cuenta en {datos_existente["colegio_dueno"] or "otro colegio"}. '
                    'Puedes vincularlo a este colegio y agregar a sus hijos de aquí. Sus datos los administra ese colegio.'
                ),
                'apoderado_existente': datos_existente,
            }, status=status.HTTP_409_CONFLICT)
        try:
            with transaction.atomic():
                vincular_apoderado(perfil, colegio, creado_por=request.user)
                _crear_estudiantes_del_apoderado(perfil, estudiantes_data, colegio.id)
        except ValidationError as exc:
            return Response({
                'message': 'Error al registrar los estudiantes del apoderado.',
                'errors': exc.detail,
            }, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'message': f'Apoderado vinculado a {colegio.nombre}. Su cuenta y contraseña siguen siendo las mismas.',
            'vinculado': True,
            'apoderado': ApoderadoSerializer(usuario, context={'colegio_id': colegio.id}).data,
        }, status=status.HTTP_201_CREATED)


def _apoderado_con_rut(rut):
    if not rut:
        return None
    try:
        rut = validar_rut(rut)
    except ValidationError:
        return None
    return PerfilApoderado.objects.select_related('usuario', 'colegio').filter(rut=rut).first()


class ApoderadoDetailView(APIView):
    permission_classes = [IsAdministrador]

    def get_object(self, request, apoderado_id):
        colegio_id = get_colegio_id_for_request(request)
        qs = Usuario.objects.filter(id=apoderado_id, rol='apoderado')
        qs = queryset_usuarios_por_colegio(qs, colegio_id, 'apoderado')
        try:
            return qs.get()
        except Usuario.DoesNotExist:
            raise Http404

    def get(self, request, apoderado_id):
        apoderado = self.get_object(request, apoderado_id)
        colegio_id = get_colegio_id_for_request(request)
        return Response(ApoderadoSerializer(apoderado, context={'colegio_id': colegio_id}).data, status=status.HTTP_200_OK)

    def patch(self, request, apoderado_id):
        apoderado = self.get_object(request, apoderado_id)
        perfil = getattr(apoderado, 'perfil_apoderado', None)
        if perfil is not None and not puede_editar_apoderado(request.user, perfil):
            # El apoderado está en varios colegios: sus datos los edita solo el colegio que lo registró primero.
            dueno = perfil.colegio.nombre if perfil.colegio_id else 'otro colegio'
            return Response({
                'message': f'Los datos de este apoderado los administra {dueno}. Solo ese colegio puede editarlos.',
            }, status=status.HTTP_403_FORBIDDEN)

        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        if first_name is not None:
            apoderado.first_name = first_name.strip()
        if last_name is not None:
            apoderado.last_name = last_name.strip()

        nombre = request.data.get('nombre') or request.data.get('nombre_completo')
        if nombre and first_name is None:
            parts = nombre.strip().split(' ', 1)
            apoderado.first_name = parts[0]
            apoderado.last_name = parts[1] if len(parts) > 1 else ''

        email = request.data.get('email') or request.data.get('usuario')
        if email and email.lower().strip() != apoderado.email:
            new_email = email.lower().strip()
            if Usuario.objects.filter(email=new_email).exclude(id=apoderado.id).exists():
                return Response({'message': 'El correo electrónico ya está registrado.'}, status=status.HTTP_400_BAD_REQUEST)
            apoderado.email = new_email
            apoderado.username = new_email

        # La contraseña la cambia solo el apoderado (desde la app o con "Recuperar contraseña"): si un
        # colegio la cambiara, también le cambiaría el acceso en sus otros colegios.
        apoderado.save()

        if hasattr(apoderado, 'perfil_apoderado'):
            perfil = apoderado.perfil_apoderado
            if 'telefono' in request.data:
                perfil.telefono = request.data['telefono'].strip()
            perfil.save()

        return Response({
            'message': 'Apoderado actualizado exitosamente.',
            'apoderado': ApoderadoSerializer(
                apoderado,
                context={'colegio_id': get_colegio_id_for_request(request)}
            ).data
        }, status=status.HTTP_200_OK)


    def delete(self, request, apoderado_id):
        apoderado = self.get_object(request, apoderado_id)
        perfil = getattr(apoderado, 'perfil_apoderado', None)
        colegio_id = get_colegio_id_for_request(request)
        if perfil is not None and colegio_id and colegios_del_apoderado(perfil) - {int(colegio_id)}:
            # Tiene otro colegio: solo se desvincula de este y su cuenta sigue activa.
            colegio = Colegio.objects.get(pk=colegio_id)
            return respuesta_desactivar(lambda _: desvincular_apoderado(perfil, colegio), apoderado)
        return respuesta_desactivar(desactivar_apoderado, apoderado)


class CambiarPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, apoderado_id):
        try:
            apoderado = Usuario.objects.get(id=apoderado_id, rol='apoderado')
        except Usuario.DoesNotExist:
            raise Http404

        if request.user.id != apoderado.id and not request.user.is_staff:
            return Response({'message': 'No tiene permisos para modificar la contraseña de este usuario.'}, status=status.HTTP_403_FORBIDDEN)

        password_actual = request.data.get('password_actual', '')
        nueva_password = request.data.get('nueva_password', '')

        if not password_actual or not nueva_password:
            return Response({'message': 'Debe ingresar la contraseña actual y la nueva contraseña.'}, status=status.HTTP_400_BAD_REQUEST)

        if not apoderado.check_password(password_actual):
            return Response({'message': 'La contraseña actual es incorrecta.'}, status=status.HTTP_400_BAD_REQUEST)

        if apoderado.check_password(nueva_password) or password_actual == nueva_password:
            return Response({'message': 'La nueva contraseña no puede ser igual a la contraseña anterior.'}, status=status.HTTP_400_BAD_REQUEST)

        if len(nueva_password) < 6:
            return Response({'message': 'La nueva contraseña debe tener al menos 6 caracteres.'}, status=status.HTTP_400_BAD_REQUEST)

        apoderado.set_password(nueva_password)
        apoderado.save()

        return Response({'message': 'Contraseña actualizada exitosamente.'}, status=status.HTTP_200_OK)
