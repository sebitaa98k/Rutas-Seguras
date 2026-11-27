from datetime import datetime, time, timedelta

from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.inasistencias import ZONA_CHILE
from usuarios.models import RecorridoRuta
from usuarios.permissions import IsAdministrador
from usuarios.view_common import get_colegio_id_for_request

from .auditoria import TOLERANCIA_ATRASO_MINUTOS

LIMITE_RECORRIDOS = 100
ETIQUETAS_ESTADO = {
    'pendiente': 'Pendiente',
    'a_bordo': 'A bordo',
    'entregado': 'Entregado',
    'ausente': 'No subió / ausente',
    'no_asiste': 'Avisó inasistencia',
    'no_recibido': 'No se recibió: volvió al colegio',
}


def _datos_evento(evento):
    return {
        'id': evento.id,
        'tipo': evento.tipo,
        'tipo_nombre': evento.get_tipo_display(),
        'estudiante_id': evento.estudiante_id,
        'estudiante_nombre': evento.estudiante_nombre,
        'metodo': evento.metodo,
        'persona_nombre': evento.persona_nombre,
        'persona_rol': evento.persona_rol,
        'persona_rut': evento.persona_rut,
        'detalle': evento.detalle,
        'creado_en': evento.creado_en,
    }


def _alumnos(recorrido, eventos):
    """Lo ocurrido con cada alumno, repasando los eventos en orden."""
    alumnos = {
        item['id']: {
            'id': item['id'], 'nombre': item['nombre'], 'estado': 'pendiente',
            'subida': None, 'entrega': None, 'observaciones': [],
        }
        for item in recorrido.estudiantes
    }
    for evento in eventos:
        if evento.estudiante_id is None and not evento.estudiante_nombre:
            continue
        alumno = alumnos.setdefault(evento.estudiante_id, {
            'id': evento.estudiante_id, 'nombre': evento.estudiante_nombre, 'estado': 'pendiente',
            'subida': None, 'entrega': None, 'observaciones': [],
        })
        if evento.tipo == 'abordaje':
            alumno['estado'] = 'a_bordo'
            alumno['subida'] = _datos_evento(evento)
        elif evento.tipo == 'entrega':
            # Quien volvió al colegio queda con la recepción del inspector, pero no fue entregado en su casa.
            if alumno['estado'] != 'no_recibido':
                alumno['estado'] = 'entregado'
            alumno['entrega'] = _datos_evento(evento)
        elif evento.tipo == 'ausente':
            alumno['estado'] = 'ausente'
        elif evento.tipo == 'no_asiste':
            alumno['estado'] = 'no_asiste'
        elif evento.tipo == 'no_recibido':
            alumno['estado'] = 'no_recibido'
        elif evento.tipo == 'reincorporado':
            alumno['estado'] = 'a_bordo'
        if evento.detalle and evento.tipo not in ('no_asiste', 'llamada'):
            alumno['observaciones'].append(evento.detalle)
    for alumno in alumnos.values():
        alumno['estado_nombre'] = ETIQUETAS_ESTADO[alumno['estado']]
    return sorted(alumnos.values(), key=lambda item: item['nombre'])


def _datos_recorrido(recorrido):
    eventos = list(recorrido.eventos.all())
    if recorrido.finalizado_en:
        estado = 'finalizado'
    else:
        estado = 'en_curso' if recorrido.iniciado_en else 'sin_iniciar'
    return {
        'id': recorrido.id,
        'ruta_id': recorrido.ruta_id,
        'nombre_ruta': recorrido.nombre_ruta,
        'sentido': recorrido.sentido,
        'colegio_nombre': recorrido.colegio.nombre if recorrido.colegio_id else '',
        'conductor_nombre': recorrido.conductor_nombre,
        'furgon_patente': recorrido.furgon_patente,
        'hora_programada': recorrido.hora_programada,
        'iniciado_en': recorrido.iniciado_en,
        'finalizado_en': recorrido.finalizado_en,
        'creado_en': recorrido.creado_en,
        'minutos_atraso': recorrido.minutos_atraso,
        'simulado': recorrido.simulado,
        'atrasado': (recorrido.minutos_atraso or 0) > TOLERANCIA_ATRASO_MINUTOS,
        'estado': estado,
        'alumnos': _alumnos(recorrido, eventos),
        'eventos': [_datos_evento(evento) for evento in eventos],
    }


def _inicio_del_dia(texto):
    return datetime.combine(datetime.strptime(texto, '%Y-%m-%d').date(), time.min, tzinfo=ZONA_CHILE)


class AuditoriaRecorridosView(APIView):
    """Historial de recorridos del colegio del administrador. Es solo de lectura."""

    permission_classes = [IsAdministrador]

    def get(self, request):
        recorridos = RecorridoRuta.objects.select_related('colegio').prefetch_related('eventos')
        colegio_id = get_colegio_id_for_request(request)
        if colegio_id:
            recorridos = recorridos.filter(colegio_id=colegio_id)

        try:
            if request.query_params.get('desde'):
                recorridos = recorridos.filter(creado_en__gte=_inicio_del_dia(request.query_params['desde']))
            if request.query_params.get('hasta'):
                recorridos = recorridos.filter(
                    creado_en__lt=_inicio_del_dia(request.query_params['hasta']) + timedelta(days=1)
                )
        except ValueError:
            return Response({'message': 'La fecha debe tener el formato AAAA-MM-DD.'}, status=400)

        buscar = (request.query_params.get('buscar') or '').strip()
        if buscar:
            recorridos = recorridos.filter(
                Q(nombre_ruta__icontains=buscar)
                | Q(conductor_nombre__icontains=buscar)
                | Q(eventos__estudiante_nombre__icontains=buscar)
                | Q(eventos__persona_nombre__icontains=buscar)
            ).distinct()
        if request.query_params.get('solo_atrasos') in ('1', 'true'):
            recorridos = recorridos.filter(minutos_atraso__gt=TOLERANCIA_ATRASO_MINUTOS)

        return Response({
            'tolerancia_atraso_minutos': TOLERANCIA_ATRASO_MINUTOS,
            'limite': LIMITE_RECORRIDOS,
            'recorridos': [_datos_recorrido(item) for item in recorridos[:LIMITE_RECORRIDOS]],
        })
