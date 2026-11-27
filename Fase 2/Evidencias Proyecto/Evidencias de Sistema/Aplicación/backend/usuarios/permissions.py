from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission

from .models import Colegio


def es_admin_plataforma(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.rol == 'admin_plataforma')
    )


def es_admin_colegio(user):
    return bool(
        user
        and user.is_authenticated
        and user.rol == 'admin_colegio'
        and user.colegio_id
    )


def colegio_administrado(request, colegio_id=None, requerido=True):
    """Resuelve y valida el colegio que un administrador puede operar."""
    user = request.user

    if es_admin_colegio(user):
        if colegio_id is not None and int(colegio_id) != user.colegio_id:
            raise PermissionDenied('No puede operar sobre otro colegio.')
        colegio_id = user.colegio_id
    elif es_admin_plataforma(user):
        header = request.headers.get('X-Colegio-ID')
        query = request.query_params.get('colegio_id')
        valor_contexto = colegio_id if colegio_id is not None else (header or query)
        if valor_contexto in (None, ''):
            if requerido:
                raise ValidationError({'colegio_id': 'Debe seleccionar un colegio.'})
            return None
        try:
            colegio_id = int(valor_contexto)
        except (TypeError, ValueError):
            raise ValidationError({'colegio_id': 'El colegio seleccionado no es válido.'})
    else:
        raise PermissionDenied('Esta operación requiere un usuario administrador.')

    try:
        return Colegio.objects.get(pk=colegio_id)
    except Colegio.DoesNotExist:
        raise NotFound('El colegio seleccionado no existe.')


class IsAdminPlataforma(BasePermission):
    message = 'Solo el administrador de plataforma puede realizar esta acción.'

    def has_permission(self, request, view):
        return es_admin_plataforma(request.user)


class IsAdminColegio(BasePermission):
    message = 'Se requiere un administrador de colegio con colegio asignado.'

    def has_permission(self, request, view):
        return es_admin_colegio(request.user)


class IsAdministrador(BasePermission):
    message = 'Esta acción requiere un usuario administrador.'

    def has_permission(self, request, view):
        return es_admin_plataforma(request.user) or es_admin_colegio(request.user)


class IsApoderado(BasePermission):
    message = 'Esta accion requiere un usuario apoderado.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.rol == 'apoderado'
        )
