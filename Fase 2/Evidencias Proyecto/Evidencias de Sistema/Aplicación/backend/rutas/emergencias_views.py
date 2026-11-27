"""Emergencias reportadas por el conductor."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.models import Emergencia, Ruta
from usuarios.push_service import crear_y_despachar_notificacion, notificar_delegados

from .auditoria import registrar_evento
from .comun import obtener_conductor_autenticado


# Deben coincidir con la app (pages/conductor/emergencia).
TIPOS_EMERGENCIA_RUTA = (
    'Avería mecánica', 'Tráfico grave / Retraso', 'Accidente en ruta', 'Clima / Cierre de vía',
)
TIPOS_EMERGENCIA_ESTUDIANTE = (
    'Emergencia médica / Salud', 'Malestar o mareo', 'Lesión o golpe a bordo', 'Conducta o pelea a bordo',
)


def tipo_no_corresponde(categoria, tipo_emergencia):
    """True si el tipo es de la otra categoría (p. ej. "Avería mecánica" para un estudiante)."""
    if categoria == 'emergencia_estudiante':
        return tipo_emergencia in TIPOS_EMERGENCIA_RUTA
    return tipo_emergencia in TIPOS_EMERGENCIA_ESTUDIANTE


class EmergenciaCrearView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        conductor_perfil = obtener_conductor_autenticado(request)

        if not conductor_perfil:
            return Response({'message': 'Solo conductores autorizados pueden reportar emergencias.'}, status=status.HTTP_403_FORBIDDEN)

        rutas_en_curso = Ruta.objects.select_related('colegio', 'furgon').filter(
            conductor_perfil=conductor_perfil,
            estado='en_ruta',
        )
        rutas_en_curso = list(rutas_en_curso.order_by('id')[:2])
        if not rutas_en_curso:
            return Response(
                {'message': 'Solo puedes reportar emergencias durante una ruta en curso.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(rutas_en_curso) > 1:
            return Response(
                {'message': 'Existe más de una ruta en curso para el conductor.'},
                status=status.HTTP_409_CONFLICT,
            )
        ruta = rutas_en_curso[0]
        if conductor_perfil.colegio_id and ruta.colegio_id != conductor_perfil.colegio_id:
            return Response(
                {'message': 'La ruta en curso no corresponde al colegio del conductor.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if ruta.furgon_id and ruta.colegio_id and ruta.furgon.colegio_id not in (None, ruta.colegio_id):
            return Response(
                {'message': 'El furgón no corresponde al colegio de la ruta en curso.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        categoria = (request.data.get('categoria') or 'emergencia_ruta').strip()
        tipo_emergencia = (request.data.get('tipo_emergencia') or request.data.get('tipo') or 'Emergencia General').strip()
        descripcion = (request.data.get('descripcion') or request.data.get('detalle') or 'Situación reportada por el conductor').strip()
        estudiante_id = request.data.get('estudiante_id')
        if estudiante_id and categoria != 'emergencia_estudiante':
            categoria = 'emergencia_estudiante'
        if tipo_no_corresponde(categoria, tipo_emergencia):
            return Response(
                {'message': f'"{tipo_emergencia}" no es un tipo válido para esta emergencia. Elige otro tipo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # CASO A: Emergencia de Estudiante
        if categoria == 'emergencia_estudiante' or estudiante_id:
            if not estudiante_id:
                return Response({'message': 'Debe seleccionar un estudiante para emergencias individuales.'}, status=status.HTTP_400_BAD_REQUEST)

            estudiante = ruta.estudiantes.filter(id=estudiante_id, colegio_id=ruta.colegio_id).first()
            if not estudiante:
                return Response({'message': 'El estudiante seleccionado no pertenece a tu furgón o ruta activa.'}, status=status.HTTP_403_FORBIDDEN)

            emergencia_obj = Emergencia.objects.create(
                conductor=conductor_perfil,
                ruta=ruta,
                colegio=ruta.colegio,
                furgon=ruta.furgon,
                categoria='emergencia_estudiante',
                tipo_emergencia=tipo_emergencia,
                descripcion=descripcion,
                estudiante=estudiante
            )
            registrar_evento(
                ruta, 'emergencia', estudiante, metodo=tipo_emergencia, detalle=descripcion,
            )

            titulo_notif = f" Emergencia relacionada con {estudiante.nombre} {estudiante.apellido}"
            mensaje_notif = (
                f"Se ha reportado una emergencia relacionada con {estudiante.nombre} {estudiante.apellido}.\n"
                f"Tipo: {tipo_emergencia}\n"
                f"Descripción: {descripcion}"
            )

            crear_y_despachar_notificacion(
                apoderado=estudiante.apoderado,
                titulo=titulo_notif,
                mensaje=mensaje_notif,
                tipo="emergencia",
                estudiante=estudiante,
                ruta=ruta,
            )

            return Response({
                'message': f'Emergencia registrada para {estudiante.nombre} {estudiante.apellido}.',
                'emergencia_id': emergencia_obj.id,
                'estudiante': f"{estudiante.nombre} {estudiante.apellido}",
                'notificados': 1
            }, status=status.HTTP_200_OK)

        # CASO B: Emergencia en Ruta (Global)
        else:
            estudiantes_ruta = ruta.estudiantes.filter(colegio_id=ruta.colegio_id)
            if not estudiantes_ruta.exists():
                return Response({'message': 'No tienes estudiantes asignados para notificar.'}, status=status.HTTP_400_BAD_REQUEST)

            emergencia_obj = Emergencia.objects.create(
                conductor=conductor_perfil,
                ruta=ruta,
                colegio=ruta.colegio,
                furgon=ruta.furgon,
                categoria='emergencia_ruta',
                tipo_emergencia=tipo_emergencia,
                descripcion=descripcion
            )
            registrar_evento(ruta, 'emergencia', metodo=tipo_emergencia, detalle=descripcion)

            apoderados_unicos = set()
            for est in estudiantes_ruta:
                if est.apoderado:
                    apoderados_unicos.add(est.apoderado)

            titulo_notif = " Emergencia durante la ruta"
            mensaje_notif = (
                f"Se ha reportado una emergencia durante el recorrido de transporte escolar.\n"
                f"Tipo: {tipo_emergencia}\n"
                f"Descripción: {descripcion}"
            )

            cnt_notificados = 0
            for apod in apoderados_unicos:
                crear_y_despachar_notificacion(
                    apoderado=apod,
                    titulo=titulo_notif,
                    mensaje=mensaje_notif,
                    tipo="emergencia"
                )
                cnt_notificados += 1

            notificar_delegados(estudiantes_ruta, titulo_notif, mensaje_notif, 'emergencia', ruta)

            return Response({
                'message': 'Emergencia en ruta reportada y notificada exitosamente.',
                'emergencia_id': emergencia_obj.id,
                'notificados': cnt_notificados
            }, status=status.HTTP_200_OK)
