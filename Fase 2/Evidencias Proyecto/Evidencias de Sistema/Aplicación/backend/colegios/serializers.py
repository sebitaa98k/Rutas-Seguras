from usuarios.obligatorios import campos_faltantes
"""Colegios y sedes."""
import re
from django.db import transaction
from rest_framework import serializers

from usuarios.models import Colegio, Sede
from usuarios.papelera import PapeleraError
from usuarios.planes import asegurar_sede_principal, cambiar_plan, sincronizar_sede_principal


class ColegioSerializer(serializers.ModelSerializer):
    total_estudiantes = serializers.SerializerMethodField()
    total_conductores = serializers.SerializerMethodField()
    total_sedes = serializers.SerializerMethodField()
    plan_nombre = serializers.CharField(source='get_plan_display', read_only=True)
    es_multisede = serializers.BooleanField(read_only=True)

    class Meta:
        model = Colegio
        fields = [
            'id', 'nombre', 'rbd', 'plan', 'plan_nombre', 'es_multisede',
            'direccion', 'comuna', 'region', 'latitud', 'longitud', 'telefono',
            'email_contacto', 'activo', 'total_estudiantes',
            'total_conductores', 'total_sedes', 'created_at', 'updated_at'
        ]
        # `activo` solo cambia con Desactivar y la Papelera, que revisan que el colegio esté vacío.
        read_only_fields = ['id', 'activo', 'created_at', 'updated_at']

    # Mensaje del cambio de plan (por ejemplo, qué sedes se desactivaron), para mostrarlo en el panel.
    mensaje_plan = ''

    @transaction.atomic
    def create(self, validated_data):
        colegio = super().create(validated_data)
        # Todo colegio nace con su sede principal, copiada de sus datos. Solo se ve si es multisede.
        asegurar_sede_principal(colegio)
        return colegio

    @transaction.atomic
    def update(self, instance, validated_data):
        nuevo_plan = validated_data.pop('plan', instance.plan)
        colegio = super().update(instance, validated_data)
        if nuevo_plan != colegio.plan:
            try:
                self.mensaje_plan = cambiar_plan(colegio, nuevo_plan)
            except PapeleraError as exc:
                raise serializers.ValidationError({'plan': str(exc)}) from exc
        sincronizar_sede_principal(colegio)
        return colegio

    def validate(self, attrs):
        instance = self.instance
        lat = attrs.get('latitud', getattr(instance, 'latitud', None))
        lon = attrs.get('longitud', getattr(instance, 'longitud', None))
        direccion = attrs.get('direccion', getattr(instance, 'direccion', None))
        errors = campos_faltantes(attrs, instance, {
            'rbd': 'El RBD del colegio es obligatorio.',
            'direccion': 'La dirección del colegio es obligatoria.',
            'region': 'La región del colegio es obligatoria.',
            'comuna': 'La comuna del colegio es obligatoria.',
            'latitud': 'Marca la ubicación del colegio en el mapa.',
            'longitud': 'Marca la ubicación del colegio en el mapa.',
            'telefono': 'El teléfono del colegio es obligatorio.',
            'email_contacto': 'El correo de contacto del colegio es obligatorio.',
        })
        rbd = (attrs.get('rbd') or '').strip()
        if rbd:
            # El RBD es el identificador oficial del Mineduc: no puede haber dos colegios con el mismo.
            repetidos = Colegio.objects.filter(rbd__iexact=rbd)
            if instance:
                repetidos = repetidos.exclude(pk=instance.pk)
            if repetidos.exists():
                errors['rbd'] = 'Ya existe un colegio con este RBD.'
            attrs['rbd'] = rbd
        if (lat is None) != (lon is None):
            errors['ubicacion'] = 'La latitud y la longitud del colegio deben registrarse juntas.'
        if lat is not None and not -90 <= lat <= 90:
            errors['latitud'] = 'La latitud debe estar entre -90 y 90.'
        if lon is not None and not -180 <= lon <= 180:
            errors['longitud'] = 'La longitud debe estar entre -180 y 180.'
        if lat is not None and not (direccion or '').strip():
            errors['direccion'] = 'Se requiere dirección cuando el colegio tiene coordenadas.'
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_total_estudiantes(self, obj):
        return obj.estudiantes.count()

    def get_total_conductores(self, obj):
        return obj.conductores.count()

    def get_total_sedes(self, obj):
        # Las sedes solo existen a la vista en los colegios multisede.
        return obj.sedes.filter(activa=True).count() if obj.es_multisede else 0


class SedeSerializer(serializers.ModelSerializer):
    colegio_nombre = serializers.ReadOnlyField(source='colegio.nombre')
    inspectores = serializers.SerializerMethodField()
    oculta = serializers.BooleanField(read_only=True)

    def validate_colegio(self, value):
        if value and not value.activo:
            raise serializers.ValidationError('El colegio seleccionado se encuentra desactivado y no admite nuevas asignaciones.')
        return value

    def validate_telefono(self, value):
        """Cada sede de un colegio tiene su propio teléfono (la principal usa el del colegio)."""
        digitos = re.sub(r'\D', '', value or '')
        if not digitos:
            return value
        colegio_id = (
            self.initial_data.get('colegio') or self.initial_data.get('colegio_id')
            or (self.instance.colegio_id if self.instance else None)
        )
        if not colegio_id:
            return value
        otras = Sede.objects.filter(colegio_id=colegio_id, activa=True)
        if self.instance:
            otras = otras.exclude(pk=self.instance.pk)
        for otra in otras.exclude(telefono__isnull=True).exclude(telefono=''):
            if re.sub(r'\D', '', otra.telefono) == digitos:
                raise serializers.ValidationError(f'Ese teléfono ya lo usa la sede "{otra.nombre}".')
        return value

    class Meta:
        model = Sede
        fields = [
            'id', 'colegio', 'colegio_nombre', 'nombre',
            'direccion', 'comuna', 'region', 'latitud', 'longitud', 'telefono',
            'activa', 'es_principal', 'oculta', 'inspectores', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'es_principal', 'created_at', 'updated_at']

    def get_inspectores(self, obj):
        """Inspectores de la sede: puede haber varios, para que siempre haya quien reciba."""
        return [
            {
                'id': relacion.delegado.usuario_id,
                'nombre': relacion.delegado.usuario.get_full_name() or relacion.delegado.usuario.email,
                'rut': relacion.delegado.rut,
            }
            for relacion in obj.inspectores.filter(activo=True).select_related('delegado__usuario')
        ]

    def validate(self, attrs):
        instance = self.instance
        if instance and instance.es_principal:
            # La sede principal usa los datos del colegio: se cambian editando el colegio.
            for campo in Sede.CAMPOS_DEL_COLEGIO:
                attrs.pop(campo, None)
            # Y se mantiene activa mientras el colegio lo esté.
            attrs.pop('activa', None)
        latitud = attrs.get('latitud', getattr(instance, 'latitud', None))
        longitud = attrs.get('longitud', getattr(instance, 'longitud', None))
        direccion = attrs.get('direccion', getattr(instance, 'direccion', None))
        errors = campos_faltantes(attrs, instance, {
            'nombre': 'El nombre de la sede es obligatorio.',
            'direccion': 'La dirección de la sede es obligatoria.',
            'region': 'La región de la sede es obligatoria.',
            'comuna': 'La comuna de la sede es obligatoria.',
            'latitud': 'Marca la ubicación de la sede en el mapa.',
            'longitud': 'Marca la ubicación de la sede en el mapa.',
            'telefono': 'El teléfono de la sede es obligatorio.',
        })
        if (latitud is None) != (longitud is None):
            errors['ubicacion'] = 'La latitud y longitud deben registrarse juntas.'
        if latitud is not None and not -90 <= latitud <= 90:
            errors['latitud'] = 'La latitud debe estar entre -90 y 90.'
        if longitud is not None and not -180 <= longitud <= 180:
            errors['longitud'] = 'La longitud debe estar entre -180 y 180.'
        if (latitud is not None or longitud is not None) and not (direccion or '').strip():
            errors['direccion'] = 'La dirección es obligatoria cuando la sede tiene coordenadas.'
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
