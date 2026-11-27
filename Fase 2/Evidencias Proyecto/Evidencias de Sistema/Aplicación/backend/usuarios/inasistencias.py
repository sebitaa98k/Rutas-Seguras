"""Avisos de inasistencia que registra el apoderado ("hoy no lo envío a clases").

Un aviso vale para un día y para la ida, la vuelta o ambas. Las rutas lo consultan
en cada cálculo, por lo que se puede registrar antes de iniciar la ruta o con el
conductor en pleno recorrido: el estudiante sale de las paradas pendientes y el
orden óptimo se recalcula. Se bloquea solo cuando ya no tiene sentido (el niño ya
subió, ya fue entregado, el conductor ya registró que no se presentó o el
recorrido de ese tramo ya terminó hoy).
"""
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from .models import InasistenciaEstudiante, Ruta

# El servidor trabaja en UTC; "hoy" debe ser el día en Chile.
ZONA_CHILE = ZoneInfo('America/Santiago')

TRAMOS = ('ida', 'vuelta')
SENTIDO_DE_TRAMO = {'ida': 'hacia_colegio', 'vuelta': 'desde_colegio'}
TRAMO_DE_SENTIDO = {sentido: tramo for tramo, sentido in SENTIDO_DE_TRAMO.items()}


class InasistenciaError(ValueError):
    """Regla de negocio que impide registrar o cancelar el aviso."""


def hoy_chile():
    return timezone.now().astimezone(ZONA_CHILE).date()


def fechas_permitidas():
    hoy = hoy_chile()
    return hoy, hoy + timedelta(days=1)


def fecha_local(momento):
    return momento.astimezone(ZONA_CHILE).date() if momento else None


def interpretar_fecha(valor):
    """Acepta 'hoy', 'manana'/'mañana' o una fecha ISO; solo hoy o mañana son válidas."""
    hoy, manana = fechas_permitidas()
    texto = str(valor or '').strip().lower()
    if texto in ('', 'hoy'):
        return hoy
    if texto in ('manana', 'mañana'):
        return manana
    try:
        fecha = date.fromisoformat(texto)
    except ValueError:
        raise InasistenciaError('La fecha no tiene un formato válido.')
    if fecha not in (hoy, manana):
        raise InasistenciaError('Solo puedes avisar inasistencias para hoy o mañana.')
    return fecha


def interpretar_tramos(valor):
    texto = str(valor or 'ambos').strip().lower()
    if texto == 'ambos':
        return list(TRAMOS)
    if texto in TRAMOS:
        return [texto]
    raise InasistenciaError('El tramo debe ser "ida", "vuelta" o "ambos".')


def ids_no_asisten(ruta, fecha=None):
    """Estudiantes de la ruta con aviso de inasistencia vigente para su tramo."""
    if not ruta.pk:
        return set()
    campo = TRAMO_DE_SENTIDO.get(ruta.sentido, 'ida')
    return set(
        InasistenciaEstudiante.objects.filter(
            estudiante__rutas=ruta,
            fecha=fecha or hoy_chile(),
            **{campo: True},
        ).values_list('estudiante_id', flat=True)
    )


def _nombre(estudiante):
    return f'{estudiante.nombre} {estudiante.apellido}'.strip()


def _rutas_del_tramo(estudiante, tramo, bloquear=False):
    rutas = Ruta.objects.filter(estudiantes=estudiante, sentido=SENTIDO_DE_TRAMO[tramo]).exclude(estado='inactiva')
    if bloquear:
        # Mismo bloqueo que usa el abordaje: aviso y escaneo simultáneos no se pisan.
        rutas = rutas.select_for_update()
    return list(rutas.order_by('id'))


def bloqueo_tramo(estudiante, tramo, fecha, rutas=None):
    """Motivo por el que no se puede cambiar la asistencia de ese tramo, o None si se puede."""
    if fecha != hoy_chile():
        return None
    nombre = _nombre(estudiante)
    for ruta in _rutas_del_tramo(estudiante, tramo) if rutas is None else rutas:
        if ruta.estado == 'finalizada' and fecha_local(ruta.finalizada_en) == fecha:
            return f'El recorrido de {tramo} de hoy ya terminó.'
        if ruta.estado not in ('activa', 'en_ruta'):
            continue
        if ruta.estudiantes_entregados.filter(pk=estudiante.pk).exists():
            return f'{nombre} ya fue entregado.'
        if ruta.estudiantes_abordados.filter(pk=estudiante.pk).exists():
            return f'{nombre} ya está en el furgón.'
        if ruta.estado == 'en_ruta' and ruta.estudiantes_ausentes.filter(pk=estudiante.pk).exists():
            if tramo == 'vuelta':
                return 'El conductor ya registró que no subió al furgón.'
            return 'El conductor ya pasó por el domicilio y registró que no se presentó.'
    return None


def estado_asistencia(estudiante):
    """Estado de hoy y mañana, por tramo, tal como lo muestra la app del apoderado."""
    hoy, manana = fechas_permitidas()
    avisos = {
        aviso.fecha: aviso
        for aviso in InasistenciaEstudiante.objects.filter(estudiante=estudiante, fecha__in=(hoy, manana))
    }
    rutas_por_tramo = {tramo: _rutas_del_tramo(estudiante, tramo) for tramo in TRAMOS}

    dias = []
    for fecha, etiqueta in ((hoy, 'Hoy'), (manana, 'Mañana')):
        aviso = avisos.get(fecha)
        dia = {'fecha': fecha.isoformat(), 'etiqueta': etiqueta, 'motivo': aviso.motivo if aviso else ''}
        for tramo in TRAMOS:
            dia[tramo] = {
                'no_asiste': bool(aviso and getattr(aviso, tramo)),
                'tiene_ruta': bool(rutas_por_tramo[tramo]),
                'bloqueo': bloqueo_tramo(estudiante, tramo, fecha, rutas_por_tramo[tramo]),
            }
        dias.append(dia)
    return {
        'estudiante_id': estudiante.id,
        'estudiante_nombre': _nombre(estudiante),
        'dias': dias,
    }


def _texto_tramos(tramos):
    return 'ida y vuelta' if len(tramos) == 2 else tramos[0]


def _texto_dia(fecha):
    return 'hoy' if fecha == hoy_chile() else 'mañana'


def marcar_inasistencia(estudiante, fecha, tramos, motivo='', usuario=None):
    cambios = []
    with transaction.atomic():
        for tramo in tramos:
            bloqueo = bloqueo_tramo(estudiante, tramo, fecha, _rutas_del_tramo(estudiante, tramo, bloquear=True))
            if bloqueo:
                raise InasistenciaError(bloqueo)
        aviso, _ = InasistenciaEstudiante.objects.select_for_update().get_or_create(
            estudiante=estudiante, fecha=fecha, defaults={'creado_por': usuario},
        )
        for tramo in tramos:
            if not getattr(aviso, tramo):
                cambios.append(tramo)
            setattr(aviso, tramo, True)
        if motivo:
            aviso.motivo = motivo[:200]
        aviso.save()
    if cambios:
        from .push_service import crear_y_despachar_notificacion_usuario
        nombre = _nombre(estudiante)
        for tramo in cambios:
            rutas = Ruta.objects.filter(
                estudiantes=estudiante, sentido=SENTIDO_DE_TRAMO[tramo],
                estado__in=('activa', 'en_ruta'), colegio_id=estudiante.colegio_id,
                conductor_perfil__isnull=False,
            ).select_related('conductor_perfil__usuario').distinct()
            for ruta in rutas:
                crear_y_despachar_notificacion_usuario(
                    ruta.conductor_perfil.usuario,
                    'Estudiante no utilizará el furgón',
                    f'{nombre} no utilizará el furgón {_texto_dia(fecha)} en el tramo de {tramo}.',
                    estudiante=estudiante,
                )
    return f'Listo: {_nombre(estudiante)} no usará el furgón {_texto_dia(fecha)} ({_texto_tramos(tramos)}). Se avisará al conductor.'


def cancelar_inasistencia(estudiante, fecha, tramos):
    with transaction.atomic():
        aviso = InasistenciaEstudiante.objects.select_for_update().filter(estudiante=estudiante, fecha=fecha).first()
        marcados = [tramo for tramo in tramos if aviso and getattr(aviso, tramo)]
        if not marcados:
            raise InasistenciaError('No hay un aviso de inasistencia para cancelar.')
        for tramo in marcados:
            bloqueo = bloqueo_tramo(estudiante, tramo, fecha, _rutas_del_tramo(estudiante, tramo, bloquear=True))
            if bloqueo:
                raise InasistenciaError(bloqueo)
            setattr(aviso, tramo, False)
        if not aviso.ida and not aviso.vuelta:
            aviso.motivo = ''
        aviso.save()
    return f'Listo: {_nombre(estudiante)} sí usará el furgón {_texto_dia(fecha)} ({_texto_tramos(marcados)}).'


def anular_por_abordaje(ruta, estudiante):
    """
    El estudiante subió al furgón aunque tenía aviso de inasistencia para este tramo:
    el rostro/QR confirma que está ahí, así que el aviso se anula. Devuelve True si había aviso.
    """
    campo = TRAMO_DE_SENTIDO.get(ruta.sentido, 'ida')
    return InasistenciaEstudiante.objects.filter(
        estudiante=estudiante, fecha=hoy_chile(), **{campo: True}
    ).update(**{campo: False}) > 0
