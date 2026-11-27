"""Asignación conductor-estudiante derivada de las rutas.

La ruta es la única fuente de verdad: un estudiante está a cargo de un
conductor cuando pertenece a una ruta operacional de ese conductor.
`Estudiante.conductor` se mantiene sincronizado solo como dato de consulta.
"""
from .models import Estudiante

# 'finalizada' solo indica que el recorrido de hoy terminó: la ruta (y su conductor) sigue vigente
# y se vuelve a iniciar al día siguiente. Solo 'inactiva' la saca de servicio.
ESTADOS_RUTA_VIGENTE = ('activa', 'en_ruta', 'finalizada')


def estudiantes_del_conductor(perfil_conductor):
    if perfil_conductor is None:
        return Estudiante.objects.none()
    # Ambas condiciones en el mismo filter() para que apliquen a la misma ruta.
    return Estudiante.objects.filter(
        rutas__conductor_perfil=perfil_conductor,
        rutas__estado__in=ESTADOS_RUTA_VIGENTE,
    ).distinct()


def sincronizar_conductor_de_estudiantes(estudiante_ids):
    """Recalcula `Estudiante.conductor` a partir de las rutas de cada estudiante."""
    for estudiante in Estudiante.objects.filter(id__in=set(estudiante_ids)):
        rutas = estudiante.rutas.exclude(conductor_perfil__isnull=True)
        ruta = rutas.filter(estado__in=ESTADOS_RUTA_VIGENTE).order_by('id').first()
        conductor_id = ruta.conductor_perfil_id if ruta else None
        if estudiante.conductor_id != conductor_id:
            estudiante.conductor_id = conductor_id
            estudiante.save(update_fields=['conductor', 'updated_at'])
