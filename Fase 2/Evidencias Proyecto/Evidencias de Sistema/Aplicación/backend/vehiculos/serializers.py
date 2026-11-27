"""Furgones."""
from rest_framework import serializers

from usuarios.models import Furgon, Ruta
from usuarios.planes import NombreSedeVisible, sede_del_registro


class FurgonSerializer(serializers.ModelSerializer):
    colegio_nombre = serializers.ReadOnlyField(source='colegio.nombre')
    sede_nombre = NombreSedeVisible()
    # El conductor sale de las rutas: es la única forma de asignar un furgón.
    conductor = serializers.SerializerMethodField()

    class Meta:
        model = Furgon
        fields = [
            'id', 'patente', 'marca_modelo', 'capacidad',
            'conductor', 'estado', 'colegio', 'colegio_nombre',
            'sede', 'sede_nombre', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


    def get_conductor(self, obj):
        ruta = Ruta.objects.filter(furgon=obj).exclude(conductor_perfil__isnull=True).select_related(
            'conductor_perfil__usuario',
        ).first()
        if not ruta:
            return None
        usuario = ruta.conductor_perfil.usuario
        return usuario.get_full_name() or usuario.email

    def validate_patente(self, value):
        patente = value.strip().upper()
        # `todos`: también revisa la papelera, porque la patente sigue ocupada.
        existentes = Furgon.todos.filter(patente__iexact=patente)
        if self.instance:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.filter(activo=False).exists():
            raise serializers.ValidationError('Esta patente es de un furgón desactivado: reactívalo desde la papelera.')
        if existentes.exists():
            raise serializers.ValidationError('Ya existe un furgón con esta patente.')
        return patente

    def validate_colegio(self, value):
        if value and not value.activo:
            raise serializers.ValidationError('El colegio seleccionado se encuentra desactivado y no admite nuevas asignaciones.')
        return value

    def validate(self, attrs):
        instance = self.instance
        colegio = attrs.get('colegio', getattr(instance, 'colegio', None))
        sede = attrs.get('sede', getattr(instance, 'sede', None))
        if colegio and not colegio.es_multisede:
            sede = attrs['sede'] = sede_del_registro(colegio, sede)
        if not sede:
            raise serializers.ValidationError({'sede': 'Selecciona la sede del furgón.'})
        if sede and colegio and sede.colegio_id != colegio.id:
            raise serializers.ValidationError({
                'sede': 'La sede debe pertenecer al mismo colegio del furgon.'
            })
        return attrs
