"""Apoderados y su registro."""
from django.db import transaction
from rest_framework import serializers

from usuarios.models import Colegio, Estudiante, PerfilApoderado, RutHabilitado, Usuario
from usuarios.rut import (
    MENSAJE_RUT_NO_HABILITADO,
    validar_rut,
    reservar_rut_habilitado,
)
from usuarios.terminos import VERSION_VIGENTE, registrar_aceptacion


class RegistroApoderadoSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    apellido = serializers.CharField(max_length=150)
    rut = serializers.CharField(max_length=12)
    email = serializers.EmailField()
    # El conductor lo usa para llamar en la vuelta cuando nadie recibe al estudiante.
    telefono = serializers.CharField(max_length=20, error_messages={'required': 'El teléfono es obligatorio.', 'blank': 'El teléfono es obligatorio.'})
    password = serializers.CharField(write_only=True, min_length=6)
    colegio_id = serializers.IntegerField(required=False, allow_null=True)
    acepta_terminos = serializers.BooleanField(required=False, default=False)
    version_terminos = serializers.CharField(required=False, allow_blank=True, default='')

    # Datos para contactar al colegio cuando rechaza un RUT.
    contacto_colegio = None

    @property
    def es_registro_publico(self):
        return 'request_registro' in self.context

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
        rut = validar_rut(value)
        if PerfilApoderado.objects.filter(rut=rut).exists():
            raise serializers.ValidationError('Este RUT ya está registrado.')
        from usuarios.rut_unico import APODERADO, rut_ocupado
        mensaje = rut_ocupado(rut, permitir={APODERADO})
        if mensaje:
            raise serializers.ValidationError(mensaje)
        return rut

    def validate(self, attrs):
        if not self.es_registro_publico:
            return attrs

        colegio_id = attrs.get('colegio_id')
        if not colegio_id:
            raise serializers.ValidationError({'colegio_id': 'Selecciona el colegio de tu hijo o hija.'})

        habilitado = RutHabilitado.objects.filter(
            colegio_id=colegio_id, rut=attrs['rut'], apoderado__isnull=True,
        ).exists()
        if not habilitado:
            colegio = Colegio.objects.get(id=colegio_id)
            self.contacto_colegio = {
                'nombre': colegio.nombre,
                'telefono': colegio.telefono or '',
                'email': colegio.email_contacto or '',
            }
            raise serializers.ValidationError({'rut': MENSAJE_RUT_NO_HABILITADO})

        # La biometría es opcional (casilla aparte): sin ella, sus hijos usan QR o el inspector.
        if not attrs['acepta_terminos']:
            raise serializers.ValidationError({
                'terminos': 'Debes aceptar los términos y condiciones para crear tu cuenta.',
            })
        if attrs['version_terminos'] != VERSION_VIGENTE:
            raise serializers.ValidationError({
                'terminos': 'Los términos cambiaron. Vuelve a leerlos y acéptalos.',
            })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        colegio_id = validated_data.pop('colegio_id', None)
        colegio_obj = Colegio.objects.filter(id=colegio_id).first() if colegio_id else None

        usuario = Usuario.objects.create_user(
            username=validated_data['email'], email=validated_data['email'],
            password=validated_data['password'], first_name=validated_data['nombre'],
            last_name=validated_data['apellido'], rol='apoderado',
            colegio=colegio_obj
        )
        perfil = PerfilApoderado.objects.create(
            usuario=usuario,
            rut=validated_data['rut'],
            telefono=validated_data.get('telefono', ''),
            colegio=colegio_obj
        )
        reservar_rut_habilitado(
            perfil, colegio_obj,
            exigir_disponible=self.es_registro_publico,
            creado_por=self.context.get('creado_por'),
        )
        if self.es_registro_publico:
            # La biometría ya no se autoriza aquí: se autoriza por cada hijo al inscribirlo.
            registrar_aceptacion(usuario, 'registro', self.context['request_registro'])
        return usuario


class ApoderadoEstudianteSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()
    direccion_retiro = serializers.CharField(source='direccion_completa', read_only=True)
    estado_matricula = serializers.SerializerMethodField()
    conductor_nombre = serializers.SerializerMethodField()
    tiene_biometria = serializers.SerializerMethodField()
    biometria_autorizada = serializers.SerializerMethodField()
    colegio_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Estudiante
        fields = [
            'id', 'rut', 'nombre', 'apellido', 'nombre_completo',
            'fecha_nacimiento', 'curso', 'colegio', 'colegio_nombre', 'direccion_retiro',
            'estado_matricula', 'conductor', 'conductor_nombre', 'tiene_biometria',
            'biometria_autorizada',
        ]

    def get_nombre_completo(self, obj):
        return f"{obj.nombre} {obj.apellido}".strip()

    def get_estado_matricula(self, obj):
        return 'aprobado'

    def get_conductor_nombre(self, obj):
        if obj.conductor:
            return obj.conductor.usuario.get_full_name() or obj.conductor.usuario.email
        return None

    def get_tiene_biometria(self, obj):
        return bool(obj.embedding_facial and len(obj.embedding_facial) == 128)

    def get_biometria_autorizada(self, obj):
        # Consentimiento de este hijo: sin él no se carga su rostro y usa QR o el inspector.
        return bool(obj.autoriza_biometria)

    def get_colegio_nombre(self, obj):
        if obj.colegio:
            return obj.colegio.nombre
        return obj.colegio_texto_legacy or ''


class ApoderadoSerializer(serializers.ModelSerializer):
    perfil_id = serializers.ReadOnlyField(source='perfil_apoderado.id')
    nombre_completo = serializers.SerializerMethodField()
    rut = serializers.SerializerMethodField()
    telefono = serializers.SerializerMethodField()
    usuario = serializers.CharField(source='email', read_only=True)
    estudiantes = serializers.SerializerMethodField()
    # El colegio de la cuenta es el "dueño": el primero que lo registró y el único que edita sus datos.
    colegio_id = serializers.ReadOnlyField(source='colegio.id')
    colegio_nombre = serializers.ReadOnlyField(source='colegio.nombre')
    colegios_vinculados = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            'id', 'perfil_id', 'usuario', 'email', 'first_name', 'last_name',
            'nombre_completo', 'rut', 'telefono', 'rol', 'colegio_id', 'colegio_nombre',
            'colegios_vinculados', 'estudiantes'
        ]

    def get_colegios_vinculados(self, obj):
        """Todos los colegios del apoderado (tiene hijos en más de uno)."""
        from usuarios.vinculos import colegios_del_apoderado

        perfil = getattr(obj, 'perfil_apoderado', None)
        if perfil is None:
            return []
        ids = colegios_del_apoderado(perfil)
        return [
            {'id': colegio.id, 'nombre': colegio.nombre, 'es_dueno': colegio.id == perfil.colegio_id}
            for colegio in Colegio.objects.filter(id__in=ids).order_by('nombre')
        ]

    def get_nombre_completo(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.email

    def get_rut(self, obj):
        return obj.perfil_apoderado.rut if hasattr(obj, 'perfil_apoderado') else ''

    def get_telefono(self, obj):
        return obj.perfil_apoderado.telefono if hasattr(obj, 'perfil_apoderado') else ''

    def get_estudiantes(self, obj):
        if hasattr(obj, 'perfil_apoderado'):
            estudiantes = obj.perfil_apoderado.estudiantes.all()
            colegio_id = self.context.get('colegio_id')
            if colegio_id:
                estudiantes = estudiantes.filter(colegio_id=colegio_id)
            return ApoderadoEstudianteSerializer(estudiantes, many=True).data
        return []
