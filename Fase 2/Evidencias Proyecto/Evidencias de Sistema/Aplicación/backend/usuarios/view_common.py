"""Filtros por colegio que comparten las vistas del panel y de la app."""
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from .autorizaciones import normalizar_rut
from .models import Colegio, Estudiante
from .permissions import es_admin_colegio, es_admin_plataforma


def queryset_usuarios_por_colegio(queryset, colegio_id, rol):
    """Filtra usuarios sin asumir que apoderado/delegado tienen un solo colegio."""
    if not colegio_id:
        return queryset
    if rol == 'apoderado':
        # Un apoderado puede estar en varios colegios: aparece donde es dueño, donde su RUT está vinculado
        # o donde tiene un hijo activo. Si un colegio lo desvinculó, ahí ya no aparece.
        return queryset.filter(
            Q(perfil_apoderado__estudiantes__colegio_id=colegio_id, perfil_apoderado__estudiantes__activo=True)
            | Q(perfil_apoderado__ruts_habilitados__colegio_id=colegio_id, perfil_apoderado__ruts_habilitados__activo=True)
            | Q(perfil_apoderado__colegio_id=colegio_id)
        ).distinct()
    if rol == 'delegado':
        # Las personas autorizadas no tienen colegio propio: se ubican por el RUT de sus autorizaciones.
        from .models import PersonaAutorizada
        ruts = list(Estudiante.objects.filter(colegio_id=colegio_id).exclude(
            rut_persona_autorizada__isnull=True
        ).exclude(rut_persona_autorizada='').values_list('rut_persona_autorizada', flat=True))
        ruts += PersonaAutorizada.objects.filter(
            colegio_id=colegio_id, activa=True,
        ).values_list('rut', flat=True)
        ruts_normalizados = {
            normalizar_rut(str(rut)) for rut in ruts
        }
        ids = [
            usuario.id for usuario in queryset.select_related('perfil_delegado')
            if hasattr(usuario, 'perfil_delegado')
            and usuario.perfil_delegado.rut
            and normalizar_rut(usuario.perfil_delegado.rut) in ruts_normalizados
        ]
        ids_sede = queryset.filter(
            perfil_delegado__sedes_responsable__sede__colegio_id=colegio_id,
            perfil_delegado__sedes_responsable__activo=True,
        ).values_list('id', flat=True)
        return queryset.filter(
            Q(colegio_id=colegio_id) | Q(id__in=ids) | Q(id__in=ids_sede)
        ).distinct()
    return queryset.filter(colegio_id=colegio_id)


def get_colegio_id_for_request(request):
    """
    Determina el colegio_id para filtrar o asociar datos según las reglas de seguridad:
    - Para 'admin_colegio': OBLIGATORIAMENTE se usa request.user.colegio_id.
    - Para 'admin_plataforma': Se usa el colegio_id especificado en X-Colegio-ID header o query param 'colegio_id' (si existe).
    - Para otros usuarios: Se usa request.user.colegio_id si existe.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None

    if user.rol == 'admin_colegio':
        if not user.colegio_id:
            raise ValidationError({'colegio_id': 'El administrador no tiene un colegio asignado.'})
        return user.colegio_id

    if es_admin_plataforma(user):
        header_val = request.headers.get('X-Colegio-ID') or request.META.get('HTTP_X_COLEGIO_ID')
        param_val = request.query_params.get('colegio_id')
        val = header_val or param_val
        if val:
            try:
                colegio_id = int(val)
            except (ValueError, TypeError):
                raise ValidationError({'colegio_id': 'El colegio seleccionado no es válido.'})
            colegio = Colegio.objects.filter(pk=colegio_id).first()
            if not colegio:
                raise ValidationError({'colegio_id': 'El colegio seleccionado no existe.'})
            if not colegio.activo:
                raise ValidationError({'colegio_id': 'El colegio seleccionado está inactivo.'})
            return colegio_id
        return None

    return user.colegio_id
