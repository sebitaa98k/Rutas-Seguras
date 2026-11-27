from usuarios.rut import validar_rut
from usuarios.rut_unico import DELEGADO, rut_ocupado
"""Delegados (inspectores y personas autorizadas) y su registro."""
from rest_framework import serializers

from usuarios.autorizaciones import estudiantes_autorizados_de, estudiantes_del_inspector, normalizar_rut
from usuarios.models import Colegio, Estudiante, PerfilDelegado, PersonaAutorizada, Usuario
from usuarios.planes import NombreSedeVisible


class RegistroDelegadoSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    apellido = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    rut = serializers.CharField(max_length=12)
    email = serializers.EmailField()
    # Aparece en los contactos que el conductor puede llamar.
    telefono = serializers.CharField(max_length=20, error_messages={'required': 'El teléfono es obligatorio.', 'blank': 'El teléfono es obligatorio.'})
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
        if PerfilDelegado.objects.filter(rut=cleaned_rut).exists():
            raise serializers.ValidationError('Este RUT ya está registrado como delegado.')
        mensaje = rut_ocupado(cleaned_rut, permitir={DELEGADO})
        if mensaje:
            raise serializers.ValidationError(mensaje)

        # Un inspector es autorizado directamente por el administrador del colegio.
        if self.context.get('autorizar_por_colegio'):
            return cleaned_rut

        rut_clean_compare = normalizar_rut(cleaned_rut)

        encontrado = any(
            normalizar_rut(item.rut) == rut_clean_compare
            for item in PersonaAutorizada.objects.filter(activa=True)
        )
        if not encontrado:
            encontrado = any(
                normalizar_rut(est.rut_persona_autorizada) == rut_clean_compare
                for est in Estudiante.objects.exclude(rut_persona_autorizada__isnull=True)
            )

        if not encontrado:
            raise serializers.ValidationError(
                f'El RUT {cleaned_rut} no ha sido previamente autorizado por ningún apoderado. '
                'Por favor, solicita al apoderado del estudiante que te agregue como persona autorizada en la app.'
            )

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
            rol='delegado',
            colegio=colegio_obj
        )
        PerfilDelegado.objects.create(
            usuario=usuario,
            rut=validated_data['rut'],
            telefono=validated_data.get('telefono', ''),
            colegio=colegio_obj,
            tipo_delegado=(
                'inspector' if self.context.get('autorizar_por_colegio') else 'autorizado'
            ),
        )
        return usuario


class DelegadoEstudianteSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()
    apoderado_nombre = serializers.SerializerMethodField()
    apoderado_telefono = serializers.SerializerMethodField()
    conductor_nombre = serializers.SerializerMethodField()
    conductor_telefono = serializers.SerializerMethodField()
    colegio_nombre = serializers.ReadOnlyField(source='colegio.nombre')
    sede_nombre = NombreSedeVisible()

    class Meta:
        model = Estudiante
        fields = [
            'id', 'rut', 'nombre', 'apellido', 'nombre_completo',
            'fecha_nacimiento', 'colegio', 'colegio_nombre', 'sede_nombre', 'curso',
            'direccion_principal', 'comuna', 'region', 'direccion_completa', 'direccion_alternativa',
            'persona_autorizada', 'rut_persona_autorizada',
            'apoderado_nombre', 'apoderado_telefono',
            'conductor_nombre', 'conductor_telefono'
        ]

    def get_nombre_completo(self, obj):
        return f"{obj.nombre} {obj.apellido}".strip()

    def get_apoderado_nombre(self, obj):
        if obj.apoderado and obj.apoderado.usuario:
            return obj.apoderado.usuario.get_full_name() or obj.apoderado.usuario.email
        return None

    def get_apoderado_telefono(self, obj):
        if obj.apoderado:
            return obj.apoderado.telefono
        return None

    def get_conductor_nombre(self, obj):
        if obj.conductor and obj.conductor.usuario:
            return obj.conductor.usuario.get_full_name() or obj.conductor.usuario.email
        return None

    def get_conductor_telefono(self, obj):
        if obj.conductor:
            return obj.conductor.telefono
        return None


class DelegadoSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()
    rut = serializers.SerializerMethodField()
    telefono = serializers.SerializerMethodField()
    usuario = serializers.CharField(source='email', read_only=True)
    estudiantes = serializers.SerializerMethodField()
    sedes_responsable = serializers.SerializerMethodField()
    colegio_id = serializers.ReadOnlyField(source='colegio.id')
    colegio_nombre = serializers.ReadOnlyField(source='colegio.nombre')
    tipo_delegado = serializers.ReadOnlyField(source='perfil_delegado.tipo_delegado')

    class Meta:
        model = Usuario
        fields = [
            'id', 'usuario', 'email', 'first_name', 'last_name',
            'nombre_completo', 'rut', 'telefono', 'rol', 'colegio_id', 'colegio_nombre',
            'tipo_delegado', 'estudiantes', 'sedes_responsable'
        ]

    def get_nombre_completo(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.email

    def get_rut(self, obj):
        return obj.perfil_delegado.rut if hasattr(obj, 'perfil_delegado') else ''

    def get_telefono(self, obj):
        return obj.perfil_delegado.telefono if hasattr(obj, 'perfil_delegado') else ''

    def get_estudiantes(self, obj):
        if not hasattr(obj, 'perfil_delegado'):
            return []

        perfil = obj.perfil_delegado
        if perfil.tipo_delegado == 'inspector':
            return DelegadoEstudianteSerializer(estudiantes_del_inspector(perfil), many=True).data

        estudiantes = estudiantes_autorizados_de(perfil)
        colegio_id = self.context.get('colegio_id')
        if colegio_id:
            estudiantes = estudiantes.filter(colegio_id=colegio_id)
        return DelegadoEstudianteSerializer(estudiantes, many=True).data

    def get_sedes_responsable(self, obj):
        if not hasattr(obj, 'perfil_delegado'):
            return []
        return [
            {
                'id': item.sede_id, 'nombre': item.sede.nombre, 'colegio_id': item.sede.colegio_id,
                # En colegios de una sola sede la pantalla no la muestra.
                'oculta': item.sede.oculta,
            }
            for item in obj.perfil_delegado.sedes_responsable.filter(activo=True).select_related('sede__colegio')
        ]
