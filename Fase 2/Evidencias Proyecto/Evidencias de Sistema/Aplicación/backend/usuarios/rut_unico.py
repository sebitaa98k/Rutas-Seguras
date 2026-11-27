"""Un RUT identifica a una sola persona con un solo rol en todo Rutas Seguras.

Regla estricta (por ahora): si un RUT ya se usa como apoderado, conductor, inspector/delegado o
estudiante —en cualquier colegio, incluida la papelera— no se puede usar para otro rol.

Excepción que sí se permite: el mismo apoderado en varios colegios usa SU MISMA cuenta
(por eso quien valida un apoderado pasa permitir={'apoderado'}).

A futuro se flexibilizará: por ejemplo, un conductor que también es apoderado de su hijo podrá
tener una segunda cuenta con otro correo. Ver documentos/Cambios_22_RutasSeguras.md.
"""
from usuarios.models import (
    Estudiante,
    EstudianteHabilitado,
    PerfilApoderado,
    PerfilConductor,
    PerfilDelegado,
    RutHabilitado,
)

APODERADO = 'apoderado'
CONDUCTOR = 'conductor'
DELEGADO = 'delegado'
ESTUDIANTE = 'estudiante'


def _usos(rut):
    """(rol, nombre para el mensaje, queryset) de cada lugar donde puede estar el RUT."""
    return (
        (APODERADO, 'apoderado', PerfilApoderado.objects.filter(rut=rut)),
        (APODERADO, 'apoderado habilitado', RutHabilitado.objects.filter(rut=rut, activo=True)),
        (CONDUCTOR, 'conductor', PerfilConductor.objects.filter(rut=rut)),
        (DELEGADO, 'inspector o delegado', PerfilDelegado.objects.filter(rut=rut)),
        (ESTUDIANTE, 'estudiante', Estudiante.todos.filter(rut=rut)),
        (ESTUDIANTE, 'estudiante habilitado', EstudianteHabilitado.objects.filter(rut=rut, activo=True)),
    )


def rut_ocupado(rut, permitir=(), excluir=None):
    """Devuelve el mensaje de error si el RUT ya está usado en otro rol, o None si está libre.

    `permitir`: roles que no cuentan como choque (los revisa cada formulario a su manera).
    `excluir`: el propio registro que se está editando.
    """
    if not rut:
        return None
    for rol, nombre, queryset in _usos(rut):
        if rol in permitir:
            continue
        if excluir is not None and queryset.model is type(excluir):
            queryset = queryset.exclude(pk=excluir.pk)
        if queryset.exists():
            return (
                f'Este RUT ya está registrado en Rutas Seguras como {nombre}. '
                'Un RUT solo puede usarse para una persona y un rol.'
            )
    return None
