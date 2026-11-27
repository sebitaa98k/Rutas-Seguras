"""Tokens de notificaciones push y avisos."""
from rest_framework import serializers

from usuarios.models import FCMToken, Notificacion


class FCMTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMToken
        fields = ['id', 'token', 'device_name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_active', 'created_at', 'updated_at']


class NotificacionSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Notificacion
        fields = [
            'id', 'titulo', 'mensaje', 'tipo', 'leido',
            'creado_en', 'estudiante', 'estudiante_nombre'
        ]
        read_only_fields = ['id', 'creado_en']

    def get_estudiante_nombre(self, obj):
        if obj.estudiante:
            return f"{obj.estudiante.nombre} {obj.estudiante.apellido}".strip()
        return None
