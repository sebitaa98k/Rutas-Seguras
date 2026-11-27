from django.db.models import Q
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from usuarios.models import FCMToken, Notificacion, PerfilApoderado
from usuarios.permissions import IsAdministrador
from usuarios.push_service import crear_y_despachar_notificacion
from notificaciones.serializers import FCMTokenSerializer, NotificacionSerializer
from usuarios.view_common import get_colegio_id_for_request


def notificaciones_del_usuario(user):
    if hasattr(user, 'perfil_apoderado'):
        return Notificacion.objects.filter(Q(apoderado=user.perfil_apoderado) | Q(destinatario=user))
    # Conductor y delegados reciben notificaciones propias: no comparten filas con el apoderado.
    if hasattr(user, 'perfil_conductor') or hasattr(user, 'perfil_delegado'):
        return Notificacion.objects.filter(destinatario=user)
    return Notificacion.objects.none()

class RegistrarFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('token', '').strip()
        device_name = request.data.get('device_name', 'Dispositivo Móvil').strip()

        if not token:
            return Response({'message': 'El token FCM es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

        fcm_token, created = FCMToken.objects.update_or_create(
            token=token,
            defaults={
                'usuario': request.user,
                'device_name': device_name,
                'is_active': True
            }
        )

        return Response({
            'message': 'Token FCM registrado exitosamente.',
            'token': FCMTokenSerializer(fcm_token).data
        }, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)

    def delete(self, request):
        token = request.data.get('token', '').strip()
        if not token:
            return Response(
                {'message': 'El token FCM es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fcm_token = FCMToken.objects.filter(
            token=token,
            usuario=request.user,
        ).first()
        if not fcm_token:
            raise Http404

        fcm_token.is_active = False
        fcm_token.save(update_fields=['is_active', 'updated_at'])
        return Response(
            {'message': 'Token FCM desactivado correctamente.'},
            status=status.HTTP_200_OK,
        )


class NotificacionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notificaciones = notificaciones_del_usuario(request.user)

        no_leidas_count = notificaciones.filter(leido=False).count()
        serializer = NotificacionSerializer(notificaciones, many=True)

        return Response({
            'no_leidas_count': no_leidas_count,
            'notificaciones': serializer.data
        }, status=status.HTTP_200_OK)


class MarcarNotificacionLeidaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notificacion_id):
        notificacion = notificaciones_del_usuario(request.user).filter(id=notificacion_id).first()
        if not notificacion:
            raise Http404
        notificacion.leido = True
        notificacion.save(update_fields=['leido'])
        return Response({'message': 'Notificacion marcada como leida.'}, status=status.HTTP_200_OK)


class MarcarTodasNotificacionesLeidasView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        notificaciones_del_usuario(request.user).filter(leido=False).update(leido=True)

        return Response({'message': 'Todas las notificaciones han sido marcadas como leídas.'}, status=status.HTTP_200_OK)


class EliminarNotificacionView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, notificacion_id):
        return self._eliminar(request, notificacion_id)

    def post(self, request, notificacion_id):
        return self._eliminar(request, notificacion_id)

    def _eliminar(self, request, notificacion_id):
        notif = notificaciones_del_usuario(request.user).filter(id=notificacion_id).first()
        if not notif:
            raise Http404
        notif.delete()
        return Response({'message': 'Notificacion eliminada.'}, status=status.HTTP_200_OK)


class EliminarTodasNotificacionesView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        return self._eliminar_todas(request)

    def post(self, request):
        return self._eliminar_todas(request)

    def _eliminar_todas(self, request):
        notificaciones_del_usuario(request.user).delete()

        return Response({'message': 'Todas las notificaciones han sido eliminadas.'}, status=status.HTTP_200_OK)


# ==========================================
# ACCIONES REALES DEL SISTEMA QUE GENERAN PUSH
# ==========================================

class AvisoSistemaView(APIView):
    permission_classes = [IsAdministrador]

    def post(self, request):
        titulo = request.data.get('titulo', 'Aviso del Sistema').strip()
        mensaje = request.data.get('mensaje', 'Estimado apoderado, se recuerda mantener actualizada la información de retiro.').strip()

        colegio_id = get_colegio_id_for_request(request)
        apoderados = PerfilApoderado.objects.all()
        if colegio_id:
            apoderados = apoderados.filter(estudiantes__colegio_id=colegio_id).distinct()
        cnt = 0
        for apoderado in apoderados:
            crear_y_despachar_notificacion(
                apoderado=apoderado,
                titulo=f"📢 {titulo}",
                mensaje=mensaje,
                tipo="aviso_sistema"
            )
            cnt += 1

        return Response({
            'message': 'Aviso del sistema despachado a los apoderados.',
            'notificados': cnt
        }, status=status.HTTP_200_OK)
