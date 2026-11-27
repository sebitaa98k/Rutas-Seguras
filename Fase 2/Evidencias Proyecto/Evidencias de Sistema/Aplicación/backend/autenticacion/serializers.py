"""Inicio de sesión y datos del usuario que recibe la app y el panel."""
from django.contrib.auth import authenticate
from rest_framework import serializers

from usuarios.models import Usuario
from usuarios.terminos import debe_aceptar_terminos


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        if not email or not password:
            raise serializers.ValidationError('Debe ingresar correo y contraseña.')
        user = authenticate(username=email, password=password)
        if not user:
            try:
                user_obj = Usuario.objects.get(email=email)
                if user_obj.check_password(password):
                    user = user_obj
            except Usuario.DoesNotExist:
                pass
        if not user:
            raise serializers.ValidationError('Correo electrónico o contraseña incorrectos.')
        if not user.is_active:
            raise serializers.ValidationError('Esta cuenta de usuario está desactivada.')
        data['user'] = user
        return data


class UsuarioResponseSerializer(serializers.ModelSerializer):
    rut = serializers.SerializerMethodField()
    telefono = serializers.SerializerMethodField()
    licencia_conducir = serializers.SerializerMethodField()
    colegio_id = serializers.ReadOnlyField(source='colegio.id')
    colegio_nombre = serializers.ReadOnlyField(source='colegio.nombre')
    tipo_delegado = serializers.SerializerMethodField()
    sedes_responsable = serializers.SerializerMethodField()
    debe_aceptar_terminos = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            'id', 'email', 'first_name', 'last_name', 'rol', 'colegio_id',
            'colegio_nombre', 'rut', 'telefono', 'licencia_conducir',
            'tipo_delegado', 'sedes_responsable', 'debe_cambiar_password',
            'debe_aceptar_terminos',
        ]

    def get_debe_aceptar_terminos(self, obj):
        return debe_aceptar_terminos(obj)

    def get_rut(self, obj):
        if hasattr(obj, 'perfil_apoderado'):
            return obj.perfil_apoderado.rut
        if hasattr(obj, 'perfil_conductor'):
            return obj.perfil_conductor.rut
        if hasattr(obj, 'perfil_delegado'):
            return obj.perfil_delegado.rut
        return None

    def get_telefono(self, obj):
        if hasattr(obj, 'perfil_apoderado'):
            return obj.perfil_apoderado.telefono
        if hasattr(obj, 'perfil_conductor'):
            return obj.perfil_conductor.telefono
        if hasattr(obj, 'perfil_delegado'):
            return obj.perfil_delegado.telefono
        return None

    def get_licencia_conducir(self, obj):
        if hasattr(obj, 'perfil_conductor'):
            return obj.perfil_conductor.licencia_conducir
        return None

    def get_tipo_delegado(self, obj):
        if hasattr(obj, 'perfil_delegado'):
            return obj.perfil_delegado.tipo_delegado
        return None

    def get_sedes_responsable(self, obj):
        if not hasattr(obj, 'perfil_delegado'):
            return []
        return [
            {'id': item.sede_id, 'nombre': item.sede.colegio.nombre if item.sede.oculta else item.sede.nombre}
            for item in obj.perfil_delegado.sedes_responsable.filter(activo=True).select_related('sede')
        ]
