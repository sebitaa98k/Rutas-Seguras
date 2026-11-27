from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from usuarios.models import Colegio, Emergencia, Estudiante, Furgon, Ruta, Sede, Usuario
from usuarios.permissions import IsAdministrador
from usuarios.view_common import get_colegio_id_for_request, queryset_usuarios_por_colegio
from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.db.models import Exists, OuterRef

from .dashboard_alerts import (
    ESTADOS_RUTA_OPERACIONAL,
    anotar_estado_alertas_estudiantes,
    datos_entrega_completos,
    embedding_facial_valido,
)
class DashboardStatsView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request):
        colegio_id = get_colegio_id_for_request(request)

        estudiantes_qs = Estudiante.objects.all()
        conductores_qs = Usuario.objects.filter(rol='conductor')
        apoderados_qs = Usuario.objects.filter(rol='apoderado', is_superuser=False, is_staff=False)
        furgones_qs = Furgon.objects.all()
        rutas_qs = Ruta.objects.all()

        if colegio_id:
            estudiantes_qs = estudiantes_qs.filter(colegio_id=colegio_id)
            conductores_qs = conductores_qs.filter(colegio_id=colegio_id)
            apoderados_qs = queryset_usuarios_por_colegio(
                apoderados_qs,
                colegio_id,
                'apoderado',
            )
            furgones_qs = furgones_qs.filter(colegio_id=colegio_id)
            rutas_qs = rutas_qs.filter(colegio_id=colegio_id)

        data = {
            'estudiantes': estudiantes_qs.count(),
            'conductores': conductores_qs.count(),
            'apoderados': apoderados_qs.count(),
            'furgones': furgones_qs.count(),
            'rutas': rutas_qs.count()
        }

        # Para consultas en contexto de colegio (admin_colegio o filtro por colegio), incluir alertas operativas del colegio
        if colegio_id:
            delegados_qs = queryset_usuarios_por_colegio(
                Usuario.objects.filter(rol='delegado', is_superuser=False, is_staff=False),
                colegio_id,
                'delegado',
            )

            zona_santiago = ZoneInfo('America/Santiago')
            hoy_santiago = timezone.now().astimezone(zona_santiago).date()
            inicio_dia = datetime.combine(hoy_santiago, time.min, tzinfo=zona_santiago)
            fin_dia = datetime.combine(hoy_santiago, time.max, tzinfo=zona_santiago)

            rutas_en_recorrido = rutas_qs.filter(estado='en_ruta')
            abordaje_vigente = Ruta.objects.filter(
                pk__in=rutas_en_recorrido,
                estudiantes_abordados=OuterRef('pk'),
            ).exclude(estudiantes_entregados=OuterRef('pk'))
            estudiantes_a_bordo = Estudiante.objects.filter(
                colegio_id=colegio_id,
            ).annotate(
                esta_a_bordo=Exists(abordaje_vigente),
            ).filter(esta_a_bordo=True).count()
            recorridos_completados = rutas_qs.filter(
                finalizada_en__range=(inicio_dia, fin_dia),
            ).count()
            incidencias_hoy = Emergencia.objects.filter(
                colegio_id=colegio_id,
                creado_en__range=(inicio_dia, fin_dia),
            ).count()

            data['colegio_nombre'] = Colegio.objects.filter(
                pk=colegio_id,
            ).values_list('nombre', flat=True).first()
            data['delegados'] = delegados_qs.count()
            data['operacion_hoy'] = {
                'rutas_en_recorrido': rutas_en_recorrido.count(),
                'estudiantes_a_bordo': estudiantes_a_bordo,
                'recorridos_completados': recorridos_completados,
                'incidencias': incidencias_hoy,
            }

            estudiantes_alertas = anotar_estado_alertas_estudiantes(estudiantes_qs)
            # Solo es pendiente si su apoderado autorizó la biometría de ese hijo; si no, usa QR.
            sin_biometria = sum(
                1 for estudiante in estudiantes_alertas.filter(autoriza_biometria=True)
                if not embedding_facial_valido(estudiante.embedding_facial)
            )
            sin_conductor = estudiantes_alertas.filter(
                tiene_conductor_operacional=False,
            ).count()
            datos_incompletos = sum(
                1 for estudiante in estudiantes_alertas
                if not datos_entrega_completos(estudiante)
            )

            rutas_vigentes_del_furgon = Ruta.objects.filter(
                furgon=OuterRef('pk'),
                colegio_id=colegio_id,
                estado__in=ESTADOS_RUTA_OPERACIONAL,
                conductor_perfil__isnull=False,
            )
            furgones_sin_conductor = furgones_qs.exclude(
                estado='mantenimiento',
            ).annotate(
                tiene_conductor_vigente=Exists(rutas_vigentes_del_furgon),
            ).filter(tiene_conductor_vigente=False).count()

            rutas_sin_conductor = rutas_qs.filter(
                estado__in=ESTADOS_RUTA_OPERACIONAL,
                conductor_perfil__isnull=True,
            ).count()
            # Sin furgón la ruta no se puede iniciar.
            rutas_sin_furgon = rutas_qs.filter(
                estado__in=ESTADOS_RUTA_OPERACIONAL,
                furgon__isnull=True,
            ).count()

            # Sin inspector, nadie puede recibir a los estudiantes de la sede en el colegio.
            sedes_sin_inspector = Sede.objects.filter(colegio_id=colegio_id, activa=True).exclude(
                inspectores__activo=True,
            ).count()

            data['alertas'] = {
                'estudiantes_sin_biometria': sin_biometria,
                'estudiantes_sin_conductor': sin_conductor,
                'estudiantes_datos_incompletos': datos_incompletos,
                'furgones_sin_conductor': furgones_sin_conductor,
                'rutas_sin_conductor': rutas_sin_conductor,
                'rutas_sin_furgon': rutas_sin_furgon,
                'sedes_sin_inspector': sedes_sin_inspector,
            }
            # Si no es multisede, la alerta de inspector habla del colegio y no de su sede (que no se muestra).
            data['colegio_multisede'] = Colegio.objects.filter(pk=colegio_id, plan=Colegio.PLAN_AVANZADO).exists()

        # En modo global (sin colegio_id), incluir conteo total de colegios registrados
        if not colegio_id:
            data['colegios'] = Colegio.objects.count()

        return Response(data, status=status.HTTP_200_OK)
