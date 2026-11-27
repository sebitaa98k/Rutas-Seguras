import secrets
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from usuarios.models import CodigoRecuperacion, Usuario
from autenticacion.serializers import LoginSerializer, UsuarioResponseSerializer
from autenticacion.correo_recuperacion import enviar_codigo_recuperacion

class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            usuario = serializer.validated_data['user']
            token, _ = Token.objects.get_or_create(user=usuario)
            user_data = UsuarioResponseSerializer(usuario).data
            return Response({
                'message': 'Inicio de sesión exitoso.',
                'token': token.key,
                'usuario': user_data
            }, status=status.HTTP_200_OK)
        return Response({
            'message': 'Error en inicio de sesión.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class AdminLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            usuario = serializer.validated_data['user']

            # RESTRICCIÓN EXCLUSIVA A ROLES ADMINISTRATIVOS
            if usuario.rol not in ['admin_plataforma', 'admin_colegio'] and not usuario.is_superuser and not usuario.is_staff:
                return Response({
                    'message': 'Acceso denegado. Este portal es exclusivo para usuarios administrativos.'
                }, status=status.HTTP_403_FORBIDDEN)

            # Para admin_colegio, verificar asignación a colegio
            if usuario.rol == 'admin_colegio' and not usuario.colegio_id:
                return Response({
                    'message': 'El usuario administrador no tiene un colegio asignado.'
                }, status=status.HTTP_403_FORBIDDEN)

            token, _ = Token.objects.get_or_create(user=usuario)
            user_data = UsuarioResponseSerializer(usuario).data
            return Response({
                'message': 'Inicio de sesión administrativo exitoso.',
                'token': token.key,
                'usuario': user_data
            }, status=status.HTTP_200_OK)

        return Response({
            'message': 'Credenciales incorrectas.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

MENSAJE_RECUPERACION = 'Si el correo está registrado, recibirás un código de recuperación.'

# Cada pantalla recupera solo las cuentas de su tipo: la app por rol y el panel web los administradores.
ROLES_POR_PANTALLA = {
    'apoderado': {'apoderado'},
    'conductor': {'conductor'},
    'delegado': {'delegado'},
    'admin': {'admin_plataforma', 'admin_colegio', 'admin'},
}


def _cuenta_de_la_pantalla(usuario, pantalla):
    if pantalla == 'admin' and usuario.is_superuser:
        return True
    return usuario.rol in ROLES_POR_PANTALLA[pantalla]


class SolicitarRecuperacionView(APIView):
    """
    Envía un código de 6 dígitos al correo. Siempre responde lo mismo, exista o no la cuenta y aunque
    el envío falle, para no revelar qué correos están registrados.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        pantalla = request.data.get('rol', '')
        if not email:
            return Response({'message': 'Ingresa tu correo electrónico.'}, status=status.HTTP_400_BAD_REQUEST)
        if pantalla not in ROLES_POR_PANTALLA:
            return Response(
                {'message': 'No se reconoce el tipo de cuenta. Actualiza la aplicación e inténtalo de nuevo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario = Usuario.objects.filter(email__iexact=email, is_active=True).first()
        # Con otro tipo de cuenta se responde igual, sin revelar que el correo existe.
        if usuario is None or not _cuenta_de_la_pantalla(usuario, pantalla):
            return Response({'message': MENSAJE_RECUPERACION})

        codigo = f'{secrets.randbelow(1000000):06d}'
        if enviar_codigo_recuperacion(usuario, codigo):
            # Solo se invalida el código anterior cuando el nuevo se envió.
            CodigoRecuperacion.objects.filter(usuario=usuario, usado=False).update(usado=True)
            CodigoRecuperacion.objects.create(usuario=usuario, codigo=codigo)

        return Response({'message': MENSAJE_RECUPERACION})


class ConfirmarRecuperacionView(APIView):

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):

        email = request.data.get(
            'email', ''
        ).strip().lower()

        codigo = request.data.get(
            'codigo', ''
        ).strip()

        nueva_password = request.data.get(
            'nueva_password', ''
        )

        if not email or not codigo or not nueva_password:

            return Response(
                {
                    'message':
                        'Correo, codigo y nueva contraseña '
                        'son obligatorios.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(codigo) != 6 or not codigo.isdigit():

            return Response(
                {
                    'message':
                        'El codigo debe tener 6 digitos.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(nueva_password) < 8:

            return Response(
                {
                    'message':
                        'La contraseña debe tener al menos '
                        '8 caracteres.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            usuario = Usuario.objects.get(
                email__iexact=email
            )

        except Usuario.DoesNotExist:

            return Response(
                {
                    'message':
                        'Codigo de recuperacion es invalido.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        recuperacion = CodigoRecuperacion.objects.filter(
            usuario=usuario,
            codigo=codigo,
            usado=False
        ).order_by('-creado_en').first()

        if not recuperacion:

            return Response(
                {
                    'message':
                        'El codigo de recuperacion es incorrecto.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not recuperacion.esta_vigente():

            return Response(
                {
                    'message':
                        'El codigo de recuperacion ha expirado.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cambiar contraseña usando el sistema de hash de Django
        usuario.set_password(nueva_password)
        usuario.debe_cambiar_password = False
        usuario.save()

        # Marcar codigo como utilizado
        recuperacion.usado = True
        recuperacion.save(
            update_fields=['usado']
        )

        # Invalidar cualquier otro codigo pendiente
        CodigoRecuperacion.objects.filter(
            usuario=usuario,
            usado=False
        ).update(usado=True)

        return Response({
            'message':
                'Contraseña actualizada correctamente.'
        })


class CambiarPasswordView(APIView):
    """Cambio de contraseña propio, para cualquier rol."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from usuarios.password_inicial import LARGO_MINIMO_NUEVA

        usuario = request.user
        actual = request.data.get('password_actual', '')
        nueva = request.data.get('nueva_password', '')

        if not actual or not nueva:
            return Response(
                {'message': 'Debes ingresar tu contraseña actual y la nueva.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not usuario.check_password(actual):
            return Response(
                {'message': 'La contraseña actual es incorrecta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if nueva == actual:
            return Response(
                {'message': 'La nueva contraseña debe ser distinta a la actual.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(nueva) < LARGO_MINIMO_NUEVA:
            return Response(
                {'message': f'La nueva contraseña debe tener al menos {LARGO_MINIMO_NUEVA} caracteres.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario.set_password(nueva)
        usuario.debe_cambiar_password = False
        usuario.save(update_fields=['password', 'debe_cambiar_password'])
        return Response({
            'message': 'Contraseña actualizada exitosamente.',
            'usuario': UsuarioResponseSerializer(usuario).data,
        })
