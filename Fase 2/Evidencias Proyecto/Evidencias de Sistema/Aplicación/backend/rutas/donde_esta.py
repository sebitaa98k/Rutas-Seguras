"""Dónde quedó un estudiante hoy según lo registrado en sus recorridos (casa, colegio o sin dato)."""
from datetime import datetime, time

from usuarios.inasistencias import ZONA_CHILE, hoy_chile
from usuarios.models import EventoRecorrido

TIPOS_QUE_UBICAN = ('entrega', 'ausente', 'no_asiste', 'abordaje', 'no_recibido')
ROL_INSPECTOR = 'Inspector/a'


def _inicio_de_hoy():
    return datetime.combine(hoy_chile(), time.min, tzinfo=ZONA_CHILE)


def _hora(momento):
    return momento.astimezone(ZONA_CHILE).strftime('%H:%M')


def donde_esta_hoy(estudiante):
    """
    Devuelve {'lugar': 'casa' | 'colegio' | 'furgon' | None, 'detalle': texto, 'hora': 'HH:MM' | None}.
    Se basa en el último evento del día: la ida deja al estudiante en el colegio; la vuelta, en su casa,
    salvo que lo haya recibido el inspector porque nadie estaba en la casa.
    """
    evento = (
        EventoRecorrido.objects.select_related('recorrido')
        .filter(estudiante=estudiante, tipo__in=TIPOS_QUE_UBICAN, creado_en__gte=_inicio_de_hoy())
        .order_by('-creado_en', '-id')
        .first()
    )
    if not evento:
        return {'lugar': None, 'detalle': 'Hoy no ha viajado en el furgón.', 'hora': None}

    hora = _hora(evento.creado_en)
    ida = evento.recorrido.sentido == 'hacia_colegio'
    if evento.tipo == 'entrega':
        if ida:
            return {'lugar': 'colegio', 'detalle': f'Llegó al colegio a las {hora}.', 'hora': hora}
        if evento.persona_rol == ROL_INSPECTOR:
            return {'lugar': 'colegio', 'detalle': f'Nadie lo recibió en casa: volvió al colegio a las {hora}.', 'hora': hora}
        return {'lugar': 'casa', 'detalle': f'Fue entregado en su casa a las {hora}.', 'hora': hora}
    if evento.tipo in ('ausente', 'no_asiste'):
        if ida:
            return {'lugar': 'casa', 'detalle': 'Hoy no viajó al colegio en el furgón.', 'hora': hora}
        return {'lugar': None, 'detalle': 'Hoy no volvió a casa en el furgón.', 'hora': hora}
    if evento.recorrido.finalizado_en is None:
        return {'lugar': 'furgon', 'detalle': f'Va en el furgón desde las {hora}.', 'hora': hora}
    return {'lugar': None, 'detalle': 'Sin información de su ubicación.', 'hora': hora}


def resumen_de_fin(ruta):
    """Texto claro para el conductor al terminar: cuántos quedaron en casa, en el colegio o no viajaron."""
    ida = ruta.sentido == 'hacia_colegio'
    en_casa = en_colegio = sin_viajar = 0
    for estudiante in ruta.estudiantes.all():
        lugar = donde_esta_hoy(estudiante)['lugar']
        if lugar == 'colegio':
            en_colegio += 1
        elif lugar == 'casa' and not ida:
            en_casa += 1
        else:
            sin_viajar += 1
    hora = _hora(ruta.finalizada_en) if ruta.finalizada_en else ''
    def n(cantidad, singular, plural):
        return f'{cantidad} {singular if cantidad == 1 else plural}'

    partes = []
    if ida:
        partes.append(n(en_colegio, 'llegó al colegio', 'llegaron al colegio'))
    else:
        partes.append(n(en_casa, 'entregado en su casa', 'entregados en su casa'))
        if en_colegio:
            partes.append(n(en_colegio, 'volvió al colegio', 'volvieron al colegio'))
    if sin_viajar:
        partes.append(n(sin_viajar, 'no viajó', 'no viajaron'))
    tramo = 'de ida' if ida else 'de vuelta'
    return f'Terminaste la ruta {tramo} "{ruta.nombre}" a las {hora}. ' + ', '.join(partes) + '.'
