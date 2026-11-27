from collections import defaultdict
from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.inasistencias import ZONA_CHILE
from usuarios.models import Colegio, RecorridoRuta
from usuarios.permissions import IsAdministrador
from usuarios.view_common import get_colegio_id_for_request

from .auditoria import TOLERANCIA_ATRASO_MINUTOS
from .auditoria_views import _alumnos, _inicio_del_dia

DIAS_POR_DEFECTO = 30
# Estados finales en que el niño alcanzó a subir al furgón.
ESTADOS_QUE_VIAJARON = ('a_bordo', 'entregado', 'no_recibido')


def _totales_vacios():
    return {
        'recorridos': 0, 'con_horario': 0, 'puntuales': 0, 'suma_atraso': 0,
        'viajes': 0, 'no_subio': 0, 'inasistencias': 0, 'entregados': 0,
        'no_recibidos': 0, 'emergencias': 0, 'sin_registro': 0,
    }


def _sumar_alumnos(totales, alumnos):
    for alumno in alumnos:
        estado = alumno['estado']
        totales['viajes'] += estado in ESTADOS_QUE_VIAJARON
        totales['no_subio'] += estado == 'ausente'
        totales['inasistencias'] += estado == 'no_asiste'
        totales['entregados'] += estado == 'entregado'
        totales['no_recibidos'] += estado == 'no_recibido'
        totales['sin_registro'] += estado == 'pendiente'


def _sumar_recorrido(totales, recorrido, alumnos, emergencias):
    totales['recorridos'] += 1
    totales['emergencias'] += emergencias
    if recorrido.minutos_atraso is not None:
        totales['con_horario'] += 1
        totales['suma_atraso'] += recorrido.minutos_atraso
        totales['puntuales'] += recorrido.minutos_atraso <= TOLERANCIA_ATRASO_MINUTOS
    _sumar_alumnos(totales, alumnos)


def _indicadores(totales):
    """Reemplaza los acumuladores por lo que se muestra. Sin horarios no hay puntualidad que informar."""
    datos = dict(totales)
    con_horario = datos['con_horario']
    suma_atraso = datos.pop('suma_atraso')
    datos['porcentaje_puntualidad'] = round(datos['puntuales'] * 100 / con_horario) if con_horario else None
    datos['atraso_promedio_minutos'] = round(suma_atraso / con_horario, 1) if con_horario else None
    return datos


def _periodo(request):
    hoy = timezone.now().astimezone(ZONA_CHILE).date()
    hasta = request.query_params.get('hasta') or hoy.isoformat()
    desde = request.query_params.get('desde') or (hoy - timedelta(days=DIAS_POR_DEFECTO - 1)).isoformat()
    return desde, hasta


class ReporteRecorridosView(APIView):
    """Resumen de los recorridos terminados de un período. Es solo de lectura."""

    permission_classes = [IsAdministrador]

    def get(self, request):
        desde, hasta = _periodo(request)
        try:
            inicio = _inicio_del_dia(desde)
            fin = _inicio_del_dia(hasta) + timedelta(days=1)
        except ValueError:
            return Response({'message': 'La fecha debe tener el formato AAAA-MM-DD.'}, status=400)
        if inicio >= fin:
            return Response({'message': 'La fecha inicial no puede ser posterior a la final.'}, status=400)

        recorridos = (
            RecorridoRuta.objects.select_related('colegio').prefetch_related('eventos')
            .filter(finalizado_en__isnull=False, creado_en__gte=inicio, creado_en__lt=fin)
        )
        # Los recorridos simulados (presentación) no cuentan, salvo que se pidan.
        incluir_simulados = request.query_params.get('incluir_simulados') in ('1', 'true')
        if not incluir_simulados:
            recorridos = recorridos.exclude(simulado=True)
        colegio_id = get_colegio_id_for_request(request)
        colegio_nombre = 'Todos los colegios'
        if colegio_id:
            recorridos = recorridos.filter(colegio_id=colegio_id)
            colegio_nombre = Colegio.objects.filter(id=colegio_id).values_list('nombre', flat=True).first() or ''

        general = _totales_vacios()
        por_ruta = defaultdict(_totales_vacios)
        por_conductor = defaultdict(_totales_vacios)
        por_estudiante = defaultdict(_totales_vacios)
        etiquetas_ruta, etiquetas_conductor, etiquetas_estudiante = {}, {}, {}

        for recorrido in recorridos:
            eventos = list(recorrido.eventos.all())
            alumnos = _alumnos(recorrido, eventos)
            emergencias = sum(evento.tipo == 'emergencia' for evento in eventos)
            nombre_colegio_recorrido = recorrido.colegio.nombre if recorrido.colegio_id else ''

            clave_ruta = recorrido.ruta_id or recorrido.nombre_ruta
            etiquetas_ruta[clave_ruta] = {'nombre': recorrido.nombre_ruta, 'colegio_nombre': nombre_colegio_recorrido}
            nombre_conductor = recorrido.conductor_nombre or 'Sin conductor'
            clave_conductor = (recorrido.colegio_id, nombre_conductor)
            etiquetas_conductor[clave_conductor] = {
                'nombre': nombre_conductor, 'colegio_nombre': nombre_colegio_recorrido,
            }

            _sumar_recorrido(general, recorrido, alumnos, emergencias)
            _sumar_recorrido(por_ruta[clave_ruta], recorrido, alumnos, emergencias)
            _sumar_recorrido(por_conductor[clave_conductor], recorrido, alumnos, emergencias)

            for alumno in alumnos:
                clave = alumno['id'] or alumno['nombre']
                etiquetas_estudiante[clave] = {
                    'nombre': alumno['nombre'], 'colegio_nombre': nombre_colegio_recorrido,
                }
                por_estudiante[clave]['recorridos'] += 1
                _sumar_alumnos(por_estudiante[clave], [alumno])

        def filas(agrupado, etiquetas):
            return sorted(
                ({**etiquetas[clave], **_indicadores(totales)} for clave, totales in agrupado.items()),
                key=lambda fila: fila['nombre'].lower(),
            )

        return Response({
            'desde': desde,
            'hasta': hasta,
            'colegio_nombre': colegio_nombre,
            'tolerancia_atraso_minutos': TOLERANCIA_ATRASO_MINUTOS,
            'incluye_simulados': incluir_simulados,
            'resumen': _indicadores(general),
            'por_ruta': filas(por_ruta, etiquetas_ruta),
            'por_conductor': filas(por_conductor, etiquetas_conductor),
            'por_estudiante': filas(por_estudiante, etiquetas_estudiante),
        })
