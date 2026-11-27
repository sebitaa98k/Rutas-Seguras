from usuarios.obligatorios import campos_faltantes
from usuarios.rut import validar_rut
from usuarios.rut_unico import ESTUDIANTE, rut_ocupado
"""Estudiantes."""
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.files.base import ContentFile
from rest_framework import serializers

from usuarios.autorizaciones import inspectores_de, personas_autorizadas_a_mostrar
from usuarios.inasistencias import hoy_chile
from usuarios.models import Estudiante
from usuarios.planes import NombreSedeVisible, sede_del_registro


class EstudianteSerializer(serializers.ModelSerializer):
    tiene_foto = serializers.SerializerMethodField(read_only=True)
    asistencia_hoy = serializers.SerializerMethodField(read_only=True)
    nombre_completo = serializers.SerializerMethodField(read_only=True)
    apoderado_nombre = serializers.SerializerMethodField(read_only=True)
    apoderado_telefono = serializers.SerializerMethodField(read_only=True)
    conductor_id = serializers.SerializerMethodField(read_only=True)
    conductor_nombre = serializers.SerializerMethodField(read_only=True)
    tiene_biometria = serializers.SerializerMethodField(read_only=True)
    # Su apoderado autorizó el reconocimiento facial. Si no, se valida con QR o con el inspector.
    biometria_autorizada = serializers.SerializerMethodField(read_only=True)
    datos_entrega_completos = serializers.SerializerMethodField(read_only=True)
    personas_autorizadas = serializers.SerializerMethodField(read_only=True)
    inspectores = serializers.SerializerMethodField(read_only=True)
    tiene_conductor_operacional = serializers.SerializerMethodField(read_only=True)
    colegio_nombre = serializers.SerializerMethodField(read_only=True)
    sede_nombre = NombreSedeVisible()

    MAX_FOTO_BYTES = 5 * 1024 * 1024
    MAX_FOTO_PIXELS = 20_000_000
    FORMATOS_PERMITIDOS = {'JPEG', 'PNG', 'WEBP'}

    class Meta:
        model = Estudiante
        fields = [
            'id', 'nombre', 'apellido', 'nombre_completo', 'rut', 'fecha_nacimiento',
            'colegio', 'colegio_nombre', 'sede', 'sede_nombre', 'curso',
            'direccion_principal', 'comuna', 'region', 'direccion_completa',
            'latitud', 'longitud', 'ubicacion_confirmada',
            'direccion_alternativa', 'persona_autorizada',
            'rut_persona_autorizada', 'foto', 'tiene_foto',
            'apoderado', 'apoderado_nombre', 'apoderado_telefono',
            'conductor', 'conductor_id', 'conductor_nombre',
            'tiene_biometria', 'biometria_autorizada', 'datos_entrega_completos', 'tiene_conductor_operacional',
            'personas_autorizadas', 'inspectores',
            'asistencia_hoy',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tiene_foto', 'direccion_completa', 'asistencia_hoy', 'created_at', 'updated_at']
        extra_kwargs = {
            'foto': {'write_only': True, 'required': False, 'allow_null': True},
            'apoderado': {'required': False, 'allow_null': True}
        }

    def validate_colegio(self, value):
        if value and not value.activo:
            raise serializers.ValidationError('El colegio seleccionado se encuentra desactivado y no admite nuevas asignaciones.')
        return value

    def validate(self, attrs):
        instance = self.instance
        colegio = attrs.get('colegio', getattr(instance, 'colegio', None))
        sede = attrs.get('sede', getattr(instance, 'sede', None))
        if colegio and not colegio.es_multisede:
            # Colegio de una sola sede: el estudiante queda en la principal sin que nadie la elija.
            sede = attrs['sede'] = sede_del_registro(colegio, sede)
        conductor = attrs.get('conductor', getattr(instance, 'conductor', None))
        latitud = attrs.get('latitud', getattr(instance, 'latitud', None))
        longitud = attrs.get('longitud', getattr(instance, 'longitud', None))
        direccion = attrs.get('direccion_principal', getattr(instance, 'direccion_principal', ''))
        ubicacion_confirmada = attrs.get(
            'ubicacion_confirmada',
            getattr(instance, 'ubicacion_confirmada', False),
        )

        errors = campos_faltantes(attrs, instance, {
            'sede': 'Selecciona la sede del estudiante.',
            'latitud': 'Marca la ubicación de la casa del estudiante en el mapa.',
            'longitud': 'Marca la ubicación de la casa del estudiante en el mapa.',
        })
        if sede and colegio and sede.colegio_id != colegio.id:
            errors['sede'] = 'La sede debe pertenecer al mismo colegio del estudiante.'
        if conductor and colegio and conductor.colegio_id != colegio.id:
            errors['conductor'] = 'El conductor debe pertenecer al mismo colegio del estudiante.'

        if (latitud is None) != (longitud is None):
            errors['ubicacion'] = 'La latitud y longitud deben registrarse juntas.'
        if latitud is not None and not -90 <= latitud <= 90:
            errors['latitud'] = 'La latitud debe estar entre -90 y 90.'
        if longitud is not None and not -180 <= longitud <= 180:
            errors['longitud'] = 'La longitud debe estar entre -180 y 180.'

        if instance and 'direccion_principal' in attrs:
            nueva = (attrs.get('direccion_principal') or '').strip()
            anterior = (instance.direccion_principal or '').strip()
            if nueva != anterior and 'latitud' not in attrs and 'longitud' not in attrs:
                attrs['ubicacion_confirmada'] = False
                ubicacion_confirmada = False

        if ubicacion_confirmada and (
            not (direccion or '').strip() or latitud is None or longitud is None
        ):
            errors['ubicacion_confirmada'] = (
                'Para confirmar la ubicación debes seleccionar una dirección válida y guardar sus coordenadas.'
            )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_colegio_nombre(self, obj):
        if obj.colegio:
            return obj.colegio.nombre
        return obj.colegio_texto_legacy or ''

    def get_tiene_foto(self, obj):
        return bool(obj.foto)

    def get_tiene_biometria(self, obj):
        from usuarios.dashboard_alerts import embedding_facial_valido
        return embedding_facial_valido(obj.embedding_facial)

    def get_biometria_autorizada(self, obj):
        # Consentimiento biométrico de este hijo (términos 1.2).
        return bool(obj.autoriza_biometria)

    def get_personas_autorizadas(self, obj):
        return personas_autorizadas_a_mostrar(obj) if obj.pk else []

    def get_inspectores(self, obj):
        return inspectores_de(obj) if obj.pk else []

    def get_datos_entrega_completos(self, obj):
        from usuarios.dashboard_alerts import datos_entrega_completos
        return datos_entrega_completos(obj)

    def get_tiene_conductor_operacional(self, obj):
        valor = getattr(obj, 'tiene_conductor_operacional', None)
        if valor is not None:
            return bool(valor)
        from usuarios.dashboard_alerts import anotar_estado_alertas_estudiantes
        return anotar_estado_alertas_estudiantes(
            Estudiante.objects.filter(pk=obj.pk)
        ).values_list('tiene_conductor_operacional', flat=True).first() or False

    def get_asistencia_hoy(self, obj):
        """Aviso de inasistencia del apoderado para hoy (False = sí usa el furgón)."""
        if not obj.pk:
            return {'no_asiste_ida': False, 'no_asiste_vuelta': False}
        aviso = obj.inasistencias.filter(fecha=hoy_chile()).first()
        return {
            'no_asiste_ida': bool(aviso and aviso.ida),
            'no_asiste_vuelta': bool(aviso and aviso.vuelta),
        }

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

    def get_conductor_id(self, obj):
        if obj.conductor:
            return obj.conductor.usuario.id
        return None

    def get_conductor_nombre(self, obj):
        if obj.conductor and obj.conductor.usuario:
            return obj.conductor.usuario.get_full_name() or obj.conductor.usuario.email
        return None

    def get_tiene_foto(self, obj):
        return bool(obj.foto)

    def validate_rut_persona_autorizada(self, value):
        return validar_rut(value) if value and value.strip() else value

    def validate_rut(self, value):
        cleaned_rut = validar_rut(value)
        # `todos`: también revisa la papelera, porque el RUT sigue ocupado.
        existentes = Estudiante.todos.filter(rut=cleaned_rut)
        if self.instance:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.filter(activo=False).exists():
            raise serializers.ValidationError('Este RUT es de un estudiante desactivado: reactívalo desde la papelera.')
        if existentes.exists():
            raise serializers.ValidationError('Este RUT de estudiante ya está registrado.')
        mensaje = rut_ocupado(cleaned_rut, permitir={ESTUDIANTE})
        if mensaje:
            raise serializers.ValidationError(mensaje)
        return cleaned_rut

    def validate_foto(self, foto):
        if foto.size > self.MAX_FOTO_BYTES:
            raise serializers.ValidationError('La foto no puede superar los 5 MB.')
        try:
            imagen = Image.open(foto)
            formato = imagen.format
            ancho, alto = imagen.size
            imagen.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise serializers.ValidationError('El archivo no es una imagen válida.')
        finally:
            foto.seek(0)
        if formato not in self.FORMATOS_PERMITIDOS:
            raise serializers.ValidationError('Solo se permiten imágenes JPEG, PNG o WebP.')
        if ancho * alto > self.MAX_FOTO_PIXELS:
            raise serializers.ValidationError('La resolución de la foto es demasiado alta.')
        return foto

    @staticmethod
    def _normalizar_foto(foto):
        """Re-codifica la imagen y elimina EXIF, incluida posible geolocalización."""
        foto.seek(0)
        with Image.open(foto) as imagen:
            imagen = ImageOps.exif_transpose(imagen)
            imagen.load()
            if imagen.mode in ('RGBA', 'LA'):
                fondo = Image.new('RGB', imagen.size, 'white')
                fondo.paste(imagen, mask=imagen.getchannel('A'))
                imagen = fondo
            elif imagen.mode != 'RGB':
                imagen = imagen.convert('RGB')
            buffer = BytesIO()
            imagen.save(buffer, format='JPEG', quality=88, optimize=True)
            return ContentFile(buffer.getvalue(), name='foto.jpg')

    def create(self, validated_data):
        foto = validated_data.pop('foto', None)
        estudiante = Estudiante(**validated_data)
        if foto:
            estudiante.foto.save('foto.jpg', self._normalizar_foto(foto), save=False)
        estudiante.save()
        return estudiante


class EstudianteUpdateSerializer(serializers.ModelSerializer):
    """Campos que un apoderado puede actualizar; RUT y foto quedan excluidos."""
    class Meta:
        model = Estudiante
        fields = [
            'nombre', 'apellido', 'fecha_nacimiento', 'colegio', 'curso',
            'direccion_principal', 'comuna', 'region', 'latitud', 'longitud', 'ubicacion_confirmada',
            'direccion_alternativa', 'persona_autorizada', 'rut_persona_autorizada'
        ]

    def validate(self, attrs):
        if 'rut' in self.initial_data:
            raise serializers.ValidationError({
                'rut': 'El RUT del estudiante no puede modificarse.'
            })

        instance = self.instance
        latitud = attrs.get('latitud', getattr(instance, 'latitud', None))
        longitud = attrs.get('longitud', getattr(instance, 'longitud', None))
        direccion = attrs.get('direccion_principal', getattr(instance, 'direccion_principal', ''))
        ubicacion_confirmada = attrs.get(
            'ubicacion_confirmada',
            getattr(instance, 'ubicacion_confirmada', False),
        )

        errors = {}
        if (latitud is None) != (longitud is None):
            errors['ubicacion'] = 'La latitud y longitud deben registrarse juntas.'
        if latitud is not None and not -90 <= latitud <= 90:
            errors['latitud'] = 'La latitud debe estar entre -90 y 90.'
        if longitud is not None and not -180 <= longitud <= 180:
            errors['longitud'] = 'La longitud debe estar entre -180 y 180.'

        if instance and 'direccion_principal' in attrs:
            nueva = (attrs.get('direccion_principal') or '').strip()
            anterior = (instance.direccion_principal or '').strip()
            if nueva != anterior and 'latitud' not in attrs and 'longitud' not in attrs:
                attrs['ubicacion_confirmada'] = False
                ubicacion_confirmada = False

        if ubicacion_confirmada and (
            not (direccion or '').strip() or latitud is None or longitud is None
        ):
            errors['ubicacion_confirmada'] = (
                'Para confirmar la ubicación debes seleccionar una dirección válida y guardar sus coordenadas.'
            )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
