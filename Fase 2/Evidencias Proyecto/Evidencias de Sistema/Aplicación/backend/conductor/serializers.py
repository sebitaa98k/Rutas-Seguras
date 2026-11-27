from usuarios.rut import validar_rut
from usuarios.rut_unico import CONDUCTOR, rut_ocupado
"""Conductores y su registro."""
from rest_framework import serializers

from usuarios.models import Colegio, PerfilConductor, Usuario


class RegistroConductorSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    apellido = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    rut = serializers.CharField(max_length=12)
    email = serializers.EmailField()
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    licencia_conducir = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    password = serializers.CharField(write_only=True, min_length=6)
    colegio_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_colegio_id(self, value):
        if value:
            colegio = Colegio.objects.filter(id=value).first()
            if not colegio:
                raise serializers.ValidationError('El colegio seleccionado no existe.')
            if not colegio.activo:
                raise serializers.ValidationError('El colegio seleccionado se encuentra desactivado y no admite nuevas asignaciones.')
        return value

    def validate_email(self, value):
        normalized_email = value.lower().strip()
        if Usuario.objects.filter(email=normalized_email).exists():
            raise serializers.ValidationError('Este correo electrónico ya está registrado.')
        return normalized_email

    def validate_rut(self, value):
        cleaned_rut = validar_rut(value)
        if PerfilConductor.objects.filter(rut=cleaned_rut).exists():
            raise serializers.ValidationError('Este RUT ya está registrado como conductor.')
        mensaje = rut_ocupado(cleaned_rut, permitir={CONDUCTOR})
        if mensaje:
            raise serializers.ValidationError(mensaje)
        return cleaned_rut

    def create(self, validated_data):
        colegio_id = validated_data.pop('colegio_id', None)
        colegio_obj = Colegio.objects.filter(id=colegio_id).first() if colegio_id else None

        usuario = Usuario.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['nombre'],
            last_name=validated_data.get('apellido', ''),
            rol='conductor',
            colegio=colegio_obj
        )
        PerfilConductor.objects.create(
            usuario=usuario,
            rut=validated_data['rut'],
            telefono=validated_data.get('telefono', ''),
            licencia_conducir=validated_data.get('licencia_conducir', ''),
            colegio=colegio_obj
        )
        return usuario


class ConductorSerializer(serializers.ModelSerializer):
    perfil_id = serializers.ReadOnlyField(source='perfil_conductor.id')
    nombre_completo = serializers.SerializerMethodField()
    rut = serializers.SerializerMethodField()
    telefono = serializers.SerializerMethodField()
    licencia_conducir = serializers.SerializerMethodField()
    usuario = serializers.CharField(source='email', read_only=True)
    total_estudiantes = serializers.SerializerMethodField()
    colegio_id = serializers.ReadOnlyField(source='colegio.id')
    colegio_nombre = serializers.ReadOnlyField(source='colegio.nombre')

    class Meta:
        model = Usuario
        fields = [
            'id', 'perfil_id', 'usuario', 'email', 'first_name', 'last_name',
            'nombre_completo', 'rut', 'telefono', 'licencia_conducir', 'rol',
            'colegio_id', 'colegio_nombre', 'total_estudiantes'
        ]

    def get_nombre_completo(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.email

    def get_rut(self, obj):
        return obj.perfil_conductor.rut if hasattr(obj, 'perfil_conductor') else ''

    def get_telefono(self, obj):
        return obj.perfil_conductor.telefono if hasattr(obj, 'perfil_conductor') else ''

    def get_licencia_conducir(self, obj):
        return obj.perfil_conductor.licencia_conducir if hasattr(obj, 'perfil_conductor') else ''

    def get_total_estudiantes(self, obj):
        if hasattr(obj, 'perfil_conductor'):
            from usuarios.asignaciones import estudiantes_del_conductor
            return estudiantes_del_conductor(obj.perfil_conductor).count()
        return 0
