from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import PermissionDenied

from .terminos import debe_aceptar_terminos

# Lo único que puede hacer una cuenta con la contraseña inicial.
RUTAS_PERMITIDAS_SIN_CAMBIO = (
    '/api/auth/cambiar-password/',
    '/api/notificaciones/fcm-token/',
)

# Lo único que puede hacer un apoderado que aún no acepta los términos.
RUTAS_PERMITIDAS_SIN_TERMINOS = RUTAS_PERMITIDAS_SIN_CAMBIO + (
    '/api/auth/terminos/aceptar/',
)


class TokenAuthenticationConCambioPassword(TokenAuthentication):
    """Token normal, pero exige cambiar la contraseña inicial antes de usar el sistema."""

    def authenticate(self, request):
        resultado = super().authenticate(request)
        if resultado is None:
            return None
        usuario = resultado[0]
        if usuario.debe_cambiar_password and request.path not in RUTAS_PERMITIDAS_SIN_CAMBIO:
            raise PermissionDenied({
                'code': 'debe_cambiar_password',
                'message': 'Debes cambiar tu contraseña antes de continuar.',
            })
        if debe_aceptar_terminos(usuario) and request.path not in RUTAS_PERMITIDAS_SIN_TERMINOS:
            raise PermissionDenied({
                'code': 'debe_aceptar_terminos',
                'message': 'Debes aceptar los términos y condiciones antes de continuar.',
            })
        return resultado
