"""Bitácora permanente de cada recorrido.

Una ruta se reutiliza todos los días y limpia su estado al reiniciarse, así que lo ocurrido
en cada recorrido se copia aquí, con nombres y no solo referencias: no se edita ni se borra.
"""
from datetime import datetime

from django.utils import timezone

from usuarios.inasistencias import ZONA_CHILE
from usuarios.models import EventoRecorrido, RecorridoRuta

# Minutos de gracia antes de considerar atrasado el inicio de un recorrido.
TOLERANCIA_ATRASO_MINUTOS = 10

ROLES_DELEGADO = {'inspector': 'Inspector/a', 'autorizado': 'Persona autorizada'}
ROLES_RECEPTOR = {
    'apoderado': 'Apoderado',
    'persona_autorizada': 'Persona autorizada',
    'delegado_institucional': 'Inspector/a',
    'domicilio': 'Domicilio (rostro del estudiante)',
}


def _nombre_estudiante(estudiante):
    return f'{estudiante.nombre} {estudiante.apellido}'.strip()


def _datos_de_ruta(ruta):
    conductor = ''
    if ruta.conductor_perfil_id:
        usuario = ruta.conductor_perfil.usuario
        conductor = usuario.get_full_name() or usuario.email
    return {
        'colegio_id': ruta.colegio_id,
        'nombre_ruta': ruta.nombre,
        'sentido': ruta.sentido,
        'conductor_nombre': conductor or ruta.conductor or '',
        'furgon_patente': ruta.furgon.patente if ruta.furgon_id else '',
        'hora_programada': ruta.hora_programada,
        'simulado': ruta.simulacion_activa,
        'estudiantes': [
            {'id': estudiante.id, 'nombre': _nombre_estudiante(estudiante)}
            for estudiante in ruta.estudiantes.all()
        ],
    }


def minutos_de_atraso(hora_programada, inicio):
    """Minutos entre la hora programada y la real, en hora de Chile. None si no hay horario."""
    if hora_programada is None:
        return None
    local = inicio.astimezone(ZONA_CHILE)
    programada = datetime.combine(local.date(), hora_programada, tzinfo=ZONA_CHILE)
    return max(0, int((local - programada).total_seconds() // 60))


def recorrido_abierto(ruta):
    """El recorrido en curso de la ruta. Se crea si alguien sube antes de presionar "Iniciar"."""
    recorrido = RecorridoRuta.objects.filter(ruta=ruta, finalizado_en__isnull=True).order_by('-id').first()
    if recorrido:
        return recorrido
    iniciado_en = ruta.iniciada_en if ruta.estado == 'en_ruta' else None
    return RecorridoRuta.objects.create(
        ruta=ruta,
        iniciado_en=iniciado_en,
        **_datos_de_ruta(ruta),
    )


def registrar_evento(ruta, tipo, estudiante=None, **campos):
    return EventoRecorrido.objects.create(
        recorrido=recorrido_abierto(ruta),
        tipo=tipo,
        estudiante=estudiante,
        estudiante_nombre=_nombre_estudiante(estudiante) if estudiante else '',
        **campos,
    )


def registrar_inicio(ruta):
    recorrido = RecorridoRuta.objects.filter(
        ruta=ruta, finalizado_en__isnull=True, iniciado_en__isnull=True,
    ).order_by('-id').first()
    if recorrido is None:
        recorrido = RecorridoRuta(ruta=ruta)
    # Se fotografía al iniciar: la ruta y sus alumnos pueden cambiar después.
    for campo, valor in _datos_de_ruta(ruta).items():
        setattr(recorrido, campo, valor)
    recorrido.iniciado_en = ruta.iniciada_en
    recorrido.save()
    return EventoRecorrido.objects.create(recorrido=recorrido, tipo='inicio')


def registrar_salida_vuelta(ruta):
    """En la vuelta se es puntual según la hora en que el furgón sale del colegio a repartir."""
    recorrido = recorrido_abierto(ruta)
    recorrido.minutos_atraso = minutos_de_atraso(recorrido.hora_programada, ruta.reparto_iniciado_en)
    recorrido.save(update_fields=['minutos_atraso'])


def _registrar_llegada_ida(recorrido):
    """En la ida se es puntual según la hora del último QR en el colegio. Si nadie viajó, no hay llegada."""
    llegada = (
        recorrido.eventos.filter(tipo='entrega').order_by('-creado_en', '-id')
        .values_list('creado_en', flat=True).first()
    )
    if llegada:
        recorrido.minutos_atraso = minutos_de_atraso(recorrido.hora_programada, llegada)
        recorrido.save(update_fields=['minutos_atraso'])


def registrar_fin(ruta, no_asisten):
    """Cierra el recorrido, dejando constancia de quienes tenían aviso de inasistencia."""
    recorrido = recorrido_abierto(ruta)
    con_evento = set(recorrido.eventos.exclude(estudiante=None).values_list('estudiante_id', flat=True))
    for estudiante in ruta.estudiantes.filter(id__in=no_asisten).exclude(id__in=con_evento):
        registrar_evento(ruta, 'no_asiste', estudiante, detalle='Su apoderado avisó que no usaría el furgón.')
    evento = EventoRecorrido.objects.create(recorrido=recorrido, tipo='fin')
    recorrido.finalizado_en = ruta.finalizada_en or timezone.now()
    recorrido.save(update_fields=['finalizado_en'])
    if recorrido.sentido == 'hacia_colegio':
        _registrar_llegada_ida(recorrido)
    return evento
