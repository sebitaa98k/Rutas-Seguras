from rest_framework.exceptions import ValidationError
from usuarios.models import PerfilDelegado
from usuarios.rut import validar_rut
from usuarios.rut_unico import DELEGADO, rut_ocupado
from usuarios.papelera import desactivar_delegado
from usuarios.papelera_views import respuesta_desactivar
from usuarios.autorizaciones import estudiantes_autorizados_de, estudiantes_del_inspector, normalizar_rut
from usuarios.password_inicial import aplicar_password_inicial, password_provisoria
from django.http import Http404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from usuarios.models import Colegio, DelegadoSede, Estudiante, Sede, Usuario
from usuarios.planes import sede_del_registro
from usuarios.permissions import IsAdministrador
from autenticacion.serializers import UsuarioResponseSerializer
from delegados.serializers import (
    DelegadoEstudianteSerializer,
    DelegadoSerializer,
    RegistroDelegadoSerializer,
)
from usuarios.view_common import get_colegio_id_for_request, queryset_usuarios_por_colegio

class RegistroDelegadoView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistroDelegadoSerializer(data=request.data)
        if serializer.is_valid():
            usuario = serializer.save()
            token, _ = Token.objects.get_or_create(user=usuario)
            user_data = UsuarioResponseSerializer(usuario).data
            return Response({
                'message': 'Delegado registrado exitosamente.',
                'token': token.key,
                'usuario': user_data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'message': 'Error en el registro de delegado.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class DelegadoEstudiantesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'perfil_delegado'):
            return Response({
                'message': 'El usuario autenticado no tiene un perfil de delegado asignado.'
            }, status=status.HTTP_403_FORBIDDEN)

        perfil = request.user.perfil_delegado
        if perfil.tipo_delegado == 'inspector':
            serializer = DelegadoEstudianteSerializer(estudiantes_del_inspector(perfil), many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = DelegadoEstudianteSerializer(estudiantes_autorizados_de(perfil), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DelegadoPerfilView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'perfil_delegado'):
            return Response({'message': 'Perfil de delegado no encontrado.'}, status=status.HTTP_403_FORBIDDEN)

        user_data = UsuarioResponseSerializer(request.user).data
        return Response(user_data, status=status.HTTP_200_OK)

    def patch(self, request):
        if not hasattr(request.user, 'perfil_delegado'):
            return Response({'message': 'Perfil de delegado no encontrado.'}, status=status.HTTP_403_FORBIDDEN)

        user = request.user
        perfil = user.perfil_delegado

        if 'first_name' in request.data:
            user.first_name = request.data['first_name'].strip()
        if 'last_name' in request.data:
            user.last_name = request.data['last_name'].strip()
        if 'telefono' in request.data:
            perfil.telefono = request.data['telefono'].strip()

        user.save()
        perfil.save()

        return Response({
            'message': 'Perfil actualizado correctamente.',
            'usuario': UsuarioResponseSerializer(user).data
        }, status=status.HTTP_200_OK)


class DelegadoAdminListCreateView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request):
        colegio_id = get_colegio_id_for_request(request)
        delegados = Usuario.objects.filter(rol='delegado', is_active=True)
        delegados = queryset_usuarios_por_colegio(delegados, colegio_id, 'delegado')
        delegados = delegados.order_by('-id')
        serializer = DelegadoSerializer(delegados, many=True, context={'colegio_id': colegio_id})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data.copy()
        target_colegio_id = get_colegio_id_for_request(request) or data.get('colegio_id')
        if target_colegio_id:
            data['colegio_id'] = target_colegio_id

        if 'nombre_completo' in data and not data.get('nombre'):
            parts = data['nombre_completo'].strip().split(' ', 1)
            data['nombre'] = parts[0]
            data['apellido'] = parts[1] if len(parts) > 1 else ''
        if 'usuario' in data and not data.get('email'):
            data['email'] = data['usuario']
        data['password'] = password_provisoria()

        sede_id = data.get('sede_id')
        tipo_delegado = data.get('tipo_delegado', 'autorizado')
        if tipo_delegado not in ('autorizado', 'sede'):
            return Response({'message': 'El tipo de delegado no es valido.'}, status=status.HTTP_400_BAD_REQUEST)

        # El inspector se crea siempre con su sede: se valida antes de crear la cuenta.
        sede = None
        colegio_destino = Colegio.objects.filter(pk=target_colegio_id).first() if target_colegio_id else None
        if tipo_delegado == 'sede' and colegio_destino and not colegio_destino.es_multisede:
            # Colegio de una sola sede: el inspector queda en la principal sin elegirla.
            sede = sede_del_registro(colegio_destino, None)
        elif tipo_delegado == 'sede':
            if not sede_id:
                return Response({'message': 'Selecciona la sede del inspector.'}, status=400)
            sede = Sede.objects.filter(pk=sede_id, colegio_id=target_colegio_id, activa=True).first()
            if not sede:
                return Response({'message': 'La sede no pertenece al colegio administrado.'}, status=400)

        serializer_data = data.copy()
        serializer_data.pop('sede_id', None)
        serializer_data.pop('tipo_delegado', None)
        serializer = RegistroDelegadoSerializer(
            data=serializer_data,
            context={'autorizar_por_colegio': tipo_delegado == 'sede'},
        )
        if serializer.is_valid():
            usuario = serializer.save()
            password_inicial = aplicar_password_inicial(usuario, usuario.perfil_delegado.rut)
            if sede:
                perfil = usuario.perfil_delegado
                perfil.colegio_id = target_colegio_id
                perfil.save(update_fields=['colegio'])
                usuario.colegio_id = target_colegio_id
                usuario.save(update_fields=['colegio'])
                DelegadoSede.objects.create(sede=sede, delegado=perfil)
            user_data = DelegadoSerializer(usuario, context={'colegio_id': target_colegio_id}).data
            return Response({
                'message': 'Delegado registrado exitosamente.',
                'delegado': user_data,
                'password_inicial': password_inicial,
            }, status=status.HTTP_201_CREATED)
        return Response({
            'message': 'Error al registrar el delegado.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class DelegadoAdminDetailView(APIView):
    permission_classes = [IsAdministrador]

    def get_object(self, request, delegado_id):
        colegio_id = get_colegio_id_for_request(request)
        qs = Usuario.objects.filter(id=delegado_id, rol='delegado')
        qs = queryset_usuarios_por_colegio(qs, colegio_id, 'delegado')
        try:
            return qs.get(), colegio_id
        except Usuario.DoesNotExist:
            raise Http404

    def get(self, request, delegado_id):
        delegado, colegio_id = self.get_object(request, delegado_id)
        return Response(DelegadoSerializer(delegado, context={'colegio_id': colegio_id}).data, status=status.HTTP_200_OK)

    def patch(self, request, delegado_id):
        delegado, colegio_id = self.get_object(request, delegado_id)

        # El tipo (persona autorizada o delegado del colegio) no se cambia una vez creado.
        perfil_actual = getattr(delegado, 'perfil_delegado', None)
        if perfil_actual and 'tipo_delegado' in request.data:
            pedido = 'inspector' if request.data.get('tipo_delegado') == 'sede' else request.data.get('tipo_delegado')
            if pedido != perfil_actual.tipo_delegado:
                return Response({
                    'message': 'El tipo de delegado no se puede cambiar. Desactívalo y registra uno nuevo con el tipo correcto.',
                }, status=400)

        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        nombre = request.data.get('nombre') or request.data.get('nombre_completo')

        if first_name is not None:
            delegado.first_name = first_name.strip()
        if last_name is not None:
            delegado.last_name = last_name.strip()
        elif nombre:
            parts = nombre.strip().split(' ', 1)
            delegado.first_name = parts[0]
            delegado.last_name = parts[1] if len(parts) > 1 else ''

        email = request.data.get('email') or request.data.get('usuario')
        if email and email.lower().strip() != delegado.email:
            new_email = email.lower().strip()
            if Usuario.objects.filter(email=new_email).exclude(id=delegado.id).exists():
                return Response({'message': 'El correo electrónico ya está registrado.'}, status=status.HTTP_400_BAD_REQUEST)
            delegado.email = new_email
            delegado.username = new_email

        password = request.data.get('password')
        if password:
            delegado.set_password(password)
            delegado.debe_cambiar_password = True

        if 'colegio_id' in request.data and (request.user.rol in ['admin_plataforma'] or request.user.is_superuser):
            delegado.colegio_id = request.data['colegio_id']

        delegado.save()

        if hasattr(delegado, 'perfil_delegado'):
            perfil = delegado.perfil_delegado
            if 'rut' in request.data:
                try:
                    rut = validar_rut(request.data['rut'])
                except ValidationError as exc:
                    return Response({'message': exc.detail[0]}, status=status.HTTP_400_BAD_REQUEST)
                if PerfilDelegado.objects.filter(rut=rut).exclude(pk=perfil.pk).exists():
                    return Response({'message': 'Este RUT ya está registrado como delegado.'}, status=400)
                mensaje = rut_ocupado(rut, permitir={DELEGADO})
                if mensaje:
                    return Response({'message': mensaje}, status=400)
                perfil.rut = rut
            if 'telefono' in request.data:
                perfil.telefono = request.data['telefono'].strip()
            if delegado.colegio_id:
                perfil.colegio_id = delegado.colegio_id
            if 'tipo_delegado' in request.data:
                tipo_delegado = request.data.get('tipo_delegado')
                if tipo_delegado not in ('autorizado', 'sede'):
                    return Response({'message': 'El tipo de delegado no es valido.'}, status=400)
                perfil.tipo_delegado = 'inspector' if tipo_delegado == 'sede' else 'autorizado'
            # Un inspector nunca queda sin sede: se puede cambiar, pero no quitar.
            sede = None
            if perfil.tipo_delegado == 'inspector':
                sede_id = request.data.get('sede_id') if 'sede_id' in request.data else None
                colegio_sede = colegio_id or perfil.colegio_id or delegado.colegio_id
                colegio_inspector = Colegio.objects.filter(pk=colegio_sede).first() if colegio_sede else None
                if colegio_inspector and not colegio_inspector.es_multisede:
                    sede = sede_del_registro(colegio_inspector, None)
                elif sede_id:
                    sede = Sede.objects.filter(pk=sede_id, colegio_id=colegio_sede, activa=True).first()
                    if not sede:
                        return Response({'message': 'La sede no pertenece al colegio administrado.'}, status=400)
                elif not perfil.sedes_responsable.exists():
                    return Response({'message': 'Selecciona la sede del inspector.'}, status=400)
            perfil.save()
            if perfil.tipo_delegado != 'inspector':
                DelegadoSede.objects.filter(delegado=perfil).delete()
            elif sede:
                DelegadoSede.objects.update_or_create(delegado=perfil, defaults={'sede': sede, 'activo': True})

        return Response({
            'message': 'Delegado actualizado exitosamente.',
            'delegado': DelegadoSerializer(delegado, context={'colegio_id': colegio_id}).data
        }, status=status.HTTP_200_OK)

    def delete(self, request, delegado_id):
        delegado, _ = self.get_object(request, delegado_id)

        return respuesta_desactivar(desactivar_delegado, delegado)


class DelegadoDesvincularEstudianteView(APIView):
    permission_classes = [IsAdministrador]

    def post(self, request):
        estudiante_id = request.data.get('estudiante_id')
        if not estudiante_id:
            return Response({'message': 'Debe especificar el estudiante_id.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            qs = Estudiante.objects.filter(id=estudiante_id)
            colegio_id = get_colegio_id_for_request(request)
            if colegio_id:
                qs = qs.filter(colegio_id=colegio_id)
            estudiante = qs.get()
        except Estudiante.DoesNotExist:
            raise Http404

        delegado_id = request.data.get('delegado_id')
        rut_delegado = None
        if delegado_id:
            delegado = queryset_usuarios_por_colegio(
                Usuario.objects.filter(id=delegado_id, rol='delegado'), colegio_id, 'delegado'
            ).first()
            if not delegado:
                raise Http404
            if delegado.perfil_delegado.tipo_delegado == 'inspector':
                return Response(
                    {'message': 'Los estudiantes de un inspector dependen de su sede: se cambian editando al inspector.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            rut_delegado = normalizar_rut(delegado.perfil_delegado.rut)
            for autorizacion in estudiante.personas_autorizadas.all():
                if normalizar_rut(autorizacion.rut) == rut_delegado:
                    autorizacion.delete()

        if rut_delegado is None or normalizar_rut(estudiante.rut_persona_autorizada) == rut_delegado:
            estudiante.persona_autorizada = ''
            estudiante.rut_persona_autorizada = ''
            estudiante.save(update_fields=['persona_autorizada', 'rut_persona_autorizada'])

        return Response({
            'message': f'Estudiante {estudiante.nombre} {estudiante.apellido} desvinculado exitosamente.'
        }, status=status.HTTP_200_OK)
