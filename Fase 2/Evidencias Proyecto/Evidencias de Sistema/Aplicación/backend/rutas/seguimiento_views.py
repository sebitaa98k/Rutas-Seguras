"""Seguimiento del furgón para apoderados, conductores y delegados."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rutas.donde_esta import donde_esta_hoy
from rutas.serializers import RutaSerializer

from usuarios.asignaciones import estudiantes_del_conductor
from usuarios.autorizaciones import estudiantes_del_inspector, normalizar_rut
from usuarios.inasistencias import ZONA_CHILE, fecha_local, hoy_chile, ids_no_asisten
from usuarios.models import Estudiante, Ruta
from usuarios.view_common import get_colegio_id_for_request


class SeguimientoView(APIView):
    """Entrega el recorrido y la última posición GPS reales de la ruta asociada."""

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _ruta_prioritaria(rutas):
        for estado_ruta in ('en_ruta', 'activa', 'finalizada'):
            ruta = rutas.filter(estado=estado_ruta).order_by('-iniciada_en', '-id').first()
            if ruta:
                return ruta
        return rutas.order_by('-id').first()

    @staticmethod
    def _ultima_terminada_hoy(rutas):
        ruta = rutas.filter(estado='finalizada', finalizada_en__isnull=False).order_by('-finalizada_en').first()
        if not ruta or fecha_local(ruta.finalizada_en) != hoy_chile():
            return None
        return {
            'nombre': ruta.nombre,
            'sentido': ruta.sentido,
            'hora': ruta.finalizada_en.astimezone(ZONA_CHILE).strftime('%H:%M'),
        }

    def get(self, request):
        user = request.user
        colegio_id = get_colegio_id_for_request(request)
        es_apoderado = hasattr(user, 'perfil_apoderado')
        estudiantes = Estudiante.objects.select_related(
            'apoderado__usuario', 'conductor__usuario', 'colegio', 'sede'
        )

        if es_apoderado:
            estudiantes = estudiantes.filter(apoderado=user.perfil_apoderado)
        elif hasattr(user, 'perfil_conductor'):
            estudiantes = estudiantes.filter(
                id__in=estudiantes_del_conductor(user.perfil_conductor).values('id')
            )
        elif hasattr(user, 'perfil_delegado'):
            perfil = user.perfil_delegado
            if perfil.tipo_delegado == 'inspector':
                estudiantes = estudiantes.filter(id__in=estudiantes_del_inspector(perfil).values('id'))
                estudiante_ids = list(estudiantes.values_list('id', flat=True))
            else:
                estudiante_ids = list(estudiantes.filter(
                    personas_autorizadas__perfil_delegado=perfil,
                    personas_autorizadas__activa=True,
                ).values_list('id', flat=True))
                delegado_rut = normalizar_rut(perfil.rut)
                estudiante_ids += [e.id for e in estudiantes.exclude(id__in=estudiante_ids)
                                   if delegado_rut and delegado_rut == normalizar_rut(e.rut_persona_autorizada)]
            estudiantes = Estudiante.objects.filter(id__in=estudiante_ids)
        else:
            return Response(
                {'message': 'El usuario no posee un perfil habilitado para seguimiento.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if colegio_id and not es_apoderado:
            estudiantes = estudiantes.filter(colegio_id=colegio_id)

        if es_apoderado:
            estudiante_id = request.query_params.get('estudiante_id')
            if estudiante_id:
                try:
                    estudiante_id = int(estudiante_id)
                except (TypeError, ValueError):
                    estudiante_id = None
                estudiante = estudiantes.filter(pk=estudiante_id).first() if estudiante_id else None
                if not estudiante:
                    return Response(
                        {'message': 'Estudiante no encontrado.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                estudiantes = estudiantes.filter(pk=estudiante.pk)
            elif estudiantes.count() > 1:
                return Response(
                    {'message': 'Debe seleccionar un estudiante para consultar su seguimiento.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        rutas = Ruta.objects.select_related(
            'colegio', 'sede', 'conductor_perfil__usuario', 'furgon'
        ).prefetch_related(
            'estudiantes__apoderado__usuario', 'paradas_completadas'
        ).filter(estudiantes__in=estudiantes).distinct()
        ruta = self._ruta_prioritaria(rutas)
        if not ruta:
            return Response(
                {'message': 'No existe una ruta asociada a los estudiantes del usuario.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        estudiante = estudiantes.filter(rutas=ruta).order_by('id').first()
        if not estudiante:
            return Response(
                {'message': 'No se encontró un estudiante asociado a esta ruta.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        conductor = ruta.conductor_perfil or estudiante.conductor
        conductor_usuario = conductor.usuario if conductor else None
        conductor_info = {
            'id': conductor.id if conductor else 0,
            'nombre': (
                conductor_usuario.get_full_name() or conductor_usuario.email
                if conductor_usuario else 'Conductor no asignado'
            ),
            'telefono': conductor.telefono if conductor else None,
        }

        estados = {
            'activa': 'no_iniciada',
            'en_ruta': 'en_camino',
            'finalizada': 'finalizada',
            'inactiva': 'pausada',
        }
        ruta_serializada = RutaSerializer(ruta).data
        tiene_gps = ruta.ultima_latitud is not None and ruta.ultima_longitud is not None
        completadas = set(ruta.paradas_completadas.values_list('id', flat=True))
        puntos_pendientes = [
            punto for punto in ruta_serializada.get('puntos_recorrido', [])
            if punto.get('tipo') != 'estudiante' or punto.get('id') not in completadas
        ]

        return Response({
            'estudiante': {
                'id': estudiante.id,
                'nombre': f'{estudiante.nombre} {estudiante.apellido}'.strip(),
                # Aviso del apoderado: hoy no usa el furgón en este tramo.
                'no_asiste_hoy': estudiante.id in ids_no_asisten(ruta),
                # Sin ruta en curso, la familia ve si quedó en casa o en el colegio.
                'donde_esta': donde_esta_hoy(estudiante),
            },
            'ultima_ruta_terminada': self._ultima_terminada_hoy(rutas),
            'conductor': conductor_info,
            'ruta': {
                'id': ruta.id,
                'nombre': ruta.nombre,
                'sentido': ruta.sentido,
                'estado': estados.get(ruta.estado, 'no_iniciada'),
                'puntos_recorrido': puntos_pendientes,
                'puntos_trazado': ruta_serializada.get('puntos_trazado', []),
            },
            'ubicacion': {
                'latitud': float(ruta.ultima_latitud) if tiene_gps else None,
                'longitud': float(ruta.ultima_longitud) if tiene_gps else None,
                'precision_metros': float(ruta.precision_gps_metros) if ruta.precision_gps_metros is not None else None,
                'ultima_actualizacion': (
                    ruta.ubicacion_actualizada_en.isoformat()
                    if ruta.ubicacion_actualizada_en else None
                ),
            },
            'llegada_estimada': None,
        })
