"""Reglas compartidas para las alertas operacionales del Dashboard."""
import math

from django.db.models import Exists, OuterRef

from .models import Ruta


from .asignaciones import ESTADOS_RUTA_VIGENTE

# Una ruta finalizada hoy sigue teniendo conductor asignado.
ESTADOS_RUTA_OPERACIONAL = ESTADOS_RUTA_VIGENTE
EMBEDDING_FACIAL_DIMENSION = 128


def embedding_facial_valido(embedding):
    """Acepta exclusivamente el vector numérico finito esperado por SFace."""
    return (
        isinstance(embedding, list)
        and len(embedding) == EMBEDDING_FACIAL_DIMENSION
        and all(
            isinstance(valor, (int, float))
            and not isinstance(valor, bool)
            and math.isfinite(valor)
            for valor in embedding
        )
    )


def anotar_estado_alertas_estudiantes(queryset):
    """Añade las relaciones que comparten Dashboard y listado de estudiantes."""
    rutas_operacionales = Ruta.objects.filter(
        estudiantes=OuterRef('pk'),
        colegio_id=OuterRef('colegio_id'),
        estado__in=ESTADOS_RUTA_OPERACIONAL,
        conductor_perfil__isnull=False,
    )
    return queryset.annotate(
        tiene_conductor_operacional=Exists(rutas_operacionales),
    )


def datos_entrega_completos(estudiante):
    # La persona autorizada es opcional: el apoderado siempre puede recibir al estudiante.
    return bool(
        (estudiante.direccion_principal or '').strip()
        and estudiante.ubicacion_confirmada
        and estudiante.latitud is not None
        and estudiante.longitud is not None
    )

