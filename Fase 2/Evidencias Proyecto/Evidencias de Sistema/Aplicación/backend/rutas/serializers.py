from usuarios.obligatorios import campos_faltantes
"""Rutas, sus paradas y el trazado del recorrido."""
from django.conf import settings
from rest_framework import serializers

from usuarios.autorizaciones import inspectores_de, personas_autorizadas_a_mostrar
from usuarios.dashboard_alerts import embedding_facial_valido
from usuarios.inasistencias import ids_no_asisten
from usuarios.models import Estudiante, PerfilConductor, Ruta
from usuarios.optimizacion_rutas import estudiantes_en_orden
from usuarios.planes import NombreSedeVisible, sede_del_registro


class RutaSerializer(serializers.ModelSerializer):
    colegio_nombre = serializers.SerializerMethodField()
    sede_nombre = NombreSedeVisible()
    sede_direccion = serializers.ReadOnlyField(source='sede.direccion')
    sede_latitud = serializers.ReadOnlyField(source='sede.latitud')
    sede_longitud = serializers.ReadOnlyField(source='sede.longitud')
    conductor = serializers.SerializerMethodField()
    conductor_id = serializers.PrimaryKeyRelatedField(
        source='conductor_perfil',
        queryset=PerfilConductor.objects.select_related('usuario', 'colegio').all(),
        # Puede quedar en blanco: la ruta no se puede iniciar hasta tener conductor y furgón.
        required=False,
        allow_null=True,
    )
    conductor_nombre = serializers.SerializerMethodField()
    furgon_patente = serializers.ReadOnlyField(source='furgon.patente')
    estudiantes_count = serializers.SerializerMethodField()
    paradas = serializers.SerializerMethodField()
    puntos_recorrido = serializers.SerializerMethodField()
    puntos_trazado = serializers.SerializerMethodField()
    simulacion_activa = serializers.SerializerMethodField()
    modo_demostracion = serializers.SerializerMethodField()
    estudiantes = serializers.PrimaryKeyRelatedField(
        queryset=Estudiante.objects.select_related('colegio', 'sede').all(),
        many=True,
        required=False,
    )

    class Meta:
        model = Ruta
        fields = [
            'id', 'nombre', 'conductor', 'conductor_id', 'conductor_nombre',
            'colegio', 'colegio_nombre', 'sede', 'sede_nombre',
            'sede_direccion', 'sede_latitud', 'sede_longitud',
            'furgon', 'furgon_patente', 'estudiantes', 'estudiantes_count',
            'paradas', 'puntos_recorrido', 'puntos_trazado', 'sentido',
            'origen_direccion', 'destino_direccion',
            'origen_latitud', 'origen_longitud',
            'destino_latitud', 'destino_longitud',
            'estado', 'hora_programada', 'reparto_iniciado_en',
            'origen_recalculo_latitud', 'origen_recalculo_longitud', 'iniciada_en', 'finalizada_en',
            'ultima_latitud', 'ultima_longitud', 'precision_gps_metros',
            'ubicacion_actualizada_en', 'simulacion_activa', 'modo_demostracion', 'created_at'
        ]
        read_only_fields = [
            'id', 'iniciada_en', 'finalizada_en', 'created_at',
            'ultima_latitud', 'ultima_longitud', 'precision_gps_metros',
            'ubicacion_actualizada_en',
            'origen_direccion', 'destino_direccion',
            'origen_latitud', 'origen_longitud',
            'destino_latitud', 'destino_longitud',
        ]

    def get_simulacion_activa(self, obj):
        """Fuera del modo demostración nunca hay simulación, aunque la ruta haya quedado marcada."""
        return bool(settings.MODO_DEMOSTRACION and obj.simulacion_activa)

    def get_modo_demostracion(self, obj):
        return settings.MODO_DEMOSTRACION

    def get_conductor(self, obj):
        return self.get_conductor_nombre(obj) or obj.conductor

    def get_conductor_nombre(self, obj):
        if obj.conductor_perfil and obj.conductor_perfil.usuario:
            usuario = obj.conductor_perfil.usuario
            return usuario.get_full_name() or usuario.email
        return obj.conductor or ''

    def get_estudiantes_count(self, obj):
        return obj.estudiantes.count() if obj.pk else 0

    def _estudiantes_ordenados(self, obj):
        # Pendientes en orden óptimo desde la posición actual del conductor.
        return estudiantes_en_orden(obj)

    def get_paradas(self, obj):
        completadas = {estudiante.id for estudiante in obj.paradas_completadas.all()}
        ausentes = {estudiante.id for estudiante in obj.estudiantes_ausentes.all()} if obj.pk else set()
        abordados = {estudiante.id for estudiante in obj.estudiantes_abordados.all()} if obj.pk else set()
        entregados = {estudiante.id for estudiante in obj.estudiantes_entregados.all()} if obj.pk else set()
        no_recibidos = {estudiante.id for estudiante in obj.estudiantes_no_recibidos.all()} if obj.pk else set()
        llamados = {estudiante.id for estudiante in obj.estudiantes_llamados.all()} if obj.pk else set()
        no_asisten = ids_no_asisten(obj)

        def estado_parada(estudiante_id):
            if estudiante_id in entregados:
                return 'entregado'
            if estudiante_id in ausentes:
                return 'ausente'
            if estudiante_id in completadas:
                return 'completada'
            # Aviso del apoderado: hoy no usa el furgón en este tramo.
            return 'no_asiste' if estudiante_id in no_asisten else 'pendiente'

        return [
            {
                'estudiante_id': estudiante.id,
                'estudiante_nombre': f'{estudiante.nombre} {estudiante.apellido}'.strip(),
                'direccion': estudiante.direccion_completa,
                'comuna': estudiante.comuna,
                'region': estudiante.region,
                'latitud': estudiante.latitud,
                'longitud': estudiante.longitud,
                'ubicacion_confirmada': estudiante.ubicacion_confirmada,
                'completada': estudiante.id in completadas,
                'estado': estado_parada(estudiante.id),
                'abordo': estudiante.id in abordados,
                'entregado': estudiante.id in entregados,
                'no_recibido': estudiante.id in no_recibidos and estudiante.id not in entregados,
                'llamado': estudiante.id in llamados,
                'no_asiste': estudiante.id in no_asisten and estudiante.id not in completadas,
                'curso': estudiante.curso,
                # Sin consentimiento para este hijo o sin rostro registrado: se valida con QR o el inspector.
                'solo_qr': not (
                    estudiante.autoriza_biometria
                    and embedding_facial_valido(estudiante.embedding_facial)
                ),
                'persona_autorizada': estudiante.persona_autorizada,
                'rut_persona_autorizada': estudiante.rut_persona_autorizada,
                'personas_autorizadas': personas_autorizadas_a_mostrar(estudiante),
                'inspectores': inspectores_de(estudiante),
                'apoderado_nombre': (
                    estudiante.apoderado.usuario.get_full_name()
                    if estudiante.apoderado and estudiante.apoderado.usuario
                    else ''
                ),
            }
            for estudiante in self._estudiantes_ordenados(obj)
        ]

    @staticmethod
    def _punto_establecimiento(colegio, sede):
        # Una sede explícita tiene prioridad sobre la ubicación del colegio.
        if sede is not None:
            if sede.latitud is None or sede.longitud is None:
                return None
            return {
                'tipo': 'sede', 'id': sede.id,
                'nombre': sede.colegio.nombre if sede.oculta else sede.nombre, 'direccion': sede.direccion_completa,
                'latitud': sede.latitud, 'longitud': sede.longitud,
            }
        if colegio is not None and colegio.latitud is not None and colegio.longitud is not None:
            return {
                'tipo': 'colegio', 'id': colegio.id,
                'nombre': colegio.nombre, 'direccion': colegio.direccion_completa,
                'latitud': colegio.latitud, 'longitud': colegio.longitud,
            }
        return None

    def get_puntos_recorrido(self, obj):
        estudiantes = self._estudiantes_ordenados(obj)
        no_asisten = ids_no_asisten(obj)
        alumnos = [
            {
                'tipo': 'estudiante',
                'id': estudiante.id,
                'nombre': f'{estudiante.nombre} {estudiante.apellido}'.strip(),
                'direccion': estudiante.direccion_completa,
                'latitud': estudiante.latitud,
                'longitud': estudiante.longitud,
            }
            for estudiante in estudiantes
            if estudiante.ubicacion_confirmada
            and estudiante.latitud is not None
            and estudiante.longitud is not None
            and estudiante.id not in no_asisten
        ]
        destino = self._punto_establecimiento(obj.colegio, obj.sede)
        if obj.sentido == 'desde_colegio':
            return ([destino] if destino else []) + alumnos
        return alumnos + ([destino] if destino else [])

    def get_puntos_trazado(self, obj):
        """
        Lo que le falta recorrer al furgón, en orden. Los mapas dibujan la línea desde su posición.
        Ida: casas por buscar y al final el colegio. Vuelta: casas por entregar y, si alguien no fue
        recibido, el colegio al final.
        """
        if not obj.pk or obj.estado != 'en_ruta':
            return []
        completadas = set(obj.paradas_completadas.values_list('id', flat=True))
        vuelven = set(
            obj.estudiantes_no_recibidos.exclude(pk__in=obj.estudiantes_entregados.values('pk'))
            .values_list('id', flat=True)
        )
        puntos = self.get_puntos_recorrido(obj)
        alumnos = [
            punto for punto in puntos
            if punto['tipo'] == 'estudiante' and punto['id'] not in completadas and punto['id'] not in vuelven
        ]
        destino = next((punto for punto in puntos if punto['tipo'] != 'estudiante'), None)
        if obj.sentido == 'desde_colegio' and not vuelven:
            destino = None
        return alumnos + ([destino] if destino else [])

    def get_colegio_nombre(self, obj):
        if obj.colegio:
            return obj.colegio.nombre
        return obj.colegio_texto_legacy or ''

    def validate(self, attrs):
        instance = self.instance
        colegio = attrs.get('colegio', getattr(instance, 'colegio', None))
        sede = attrs.get('sede', getattr(instance, 'sede', None))
        if colegio and not colegio.es_multisede:
            sede = attrs['sede'] = sede_del_registro(colegio, sede)
        conductor = attrs.get('conductor_perfil', getattr(instance, 'conductor_perfil', None))
        furgon = attrs.get('furgon', getattr(instance, 'furgon', None))
        sentido = attrs.get('sentido', getattr(instance, 'sentido', 'hacia_colegio'))
        estudiantes = attrs.get('estudiantes')
        if estudiantes is None and instance:
            estudiantes = list(instance.estudiantes.all().order_by('id'))
        estudiantes = estudiantes or []

        errors = campos_faltantes(attrs, instance, {
            'sede': 'Selecciona la sede de la ruta.',
            # Sin hora programada, Reportes no puede medir la puntualidad.
            'hora_programada': 'La hora programada de la ruta es obligatoria.',
        })
        if not colegio:
            errors['colegio'] = 'Debes seleccionar un colegio.'
        elif not colegio.activo:
            errors['colegio'] = 'El colegio seleccionado está desactivado.'

        if sede:
            if colegio and sede.colegio_id != colegio.id:
                errors['sede'] = 'La sede debe pertenecer al mismo colegio de la ruta.'
            elif not sede.activa:
                errors['sede'] = 'La sede seleccionada está desactivada.'
            elif sede.latitud is None or sede.longitud is None:
                errors['sede'] = 'La sede debe tener latitud y longitud válidas antes de utilizarla en una ruta.'
            elif not (sede.direccion or '').strip():
                errors['sede'] = 'La sede debe tener una dirección antes de utilizarla en una ruta.'
        elif colegio:
            if colegio.latitud is None or colegio.longitud is None:
                errors['colegio'] = 'El colegio debe tener latitud y longitud para rutas sin sede.'
            elif not (colegio.direccion or '').strip():
                errors['colegio'] = 'El colegio debe tener una dirección para rutas sin sede.'

        # Conductor y furgón pueden quedar en blanco (por ejemplo, para intercambiar furgones entre
        # conductores); la ruta no se puede iniciar hasta tener ambos.
        if conductor and colegio and conductor.colegio_id != colegio.id:
            errors['conductor_id'] = 'El conductor debe pertenecer al mismo colegio de la ruta.'

        if not furgon:
            pass
        elif colegio and furgon.colegio_id != colegio.id:
            errors['furgon'] = 'El furgón debe pertenecer al mismo colegio de la ruta.'
        elif sede and furgon.sede_id and furgon.sede_id != sede.id:
            errors['furgon'] = 'El furgón debe pertenecer a la sede seleccionada.'
        elif furgon.estado == 'mantenimiento':
            errors['furgon'] = 'No se puede asignar un furgón en mantenimiento.'
        elif conductor:
            # Un furgón tiene un solo conductor: todas sus rutas deben ser del mismo.
            otras = Ruta.objects.filter(furgon=furgon).exclude(conductor_perfil__isnull=True).exclude(
                conductor_perfil=conductor,
            )
            if instance:
                otras = otras.exclude(pk=instance.pk)
            otra = otras.select_related('conductor_perfil__usuario').first()
            if otra:
                otro = otra.conductor_perfil.usuario
                errors['furgon'] = (
                    f'El furgón {furgon.patente} ya lo maneja {otro.get_full_name() or otro.email} '
                    f'en la ruta "{otra.nombre}". Un furgón solo puede tener un conductor: '
                    'deja esa ruta sin furgón o elige otro.'
                )

        invalid_students = [
            student.id for student in estudiantes
            if colegio and student.colegio_id != colegio.id
        ]
        # La ruta va a una sede: sus estudiantes deben ser de esa sede.
        de_otra_sede = [
            f'{student.nombre} {student.apellido}'.strip() for student in estudiantes
            if sede and student.sede_id and student.sede_id != sede.id
        ]
        students_without_location = [
            student.id for student in estudiantes
            if not student.ubicacion_confirmada
            or student.latitud is None
            or student.longitud is None
            or not (student.direccion_principal or '').strip()
        ]

        if not estudiantes:
            errors['estudiantes'] = 'Debes asignar al menos un estudiante a la ruta.'
        elif invalid_students:
            errors['estudiantes'] = 'Todos los estudiantes deben pertenecer al mismo colegio de la ruta.'
        elif de_otra_sede:
            errors['estudiantes'] = (
                f'Todos los estudiantes deben ser de la sede {sede.nombre}. '
                f'Son de otra sede: {", ".join(de_otra_sede)}.'
            )
        elif students_without_location:
            errors['estudiantes'] = (
                'Todos los estudiantes deben tener su dirección y ubicación confirmadas por el apoderado.'
            )
        elif furgon and len(estudiantes) > furgon.capacidad:
            errors['estudiantes'] = f'La cantidad de estudiantes supera la capacidad del furgón ({furgon.capacidad}).'

        if not errors and estudiantes:
            establecimiento = sede if sede else colegio
            first_student = estudiantes[0]
            last_student = estudiantes[-1]
            if sentido == 'hacia_colegio':
                attrs['origen_direccion'] = first_student.direccion_completa[:255]
                attrs['origen_latitud'] = first_student.latitud
                attrs['origen_longitud'] = first_student.longitud
                attrs['destino_direccion'] = establecimiento.direccion_completa[:255]
                attrs['destino_latitud'] = establecimiento.latitud
                attrs['destino_longitud'] = establecimiento.longitud
            else:
                attrs['origen_direccion'] = establecimiento.direccion_completa[:255]
                attrs['origen_latitud'] = establecimiento.latitud
                attrs['origen_longitud'] = establecimiento.longitud
                attrs['destino_direccion'] = last_student.direccion_completa[:255]
                attrs['destino_latitud'] = last_student.latitud
                attrs['destino_longitud'] = last_student.longitud

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _sync_relations(self, ruta, estudiantes, anteriores_ids=()):
        from usuarios.asignaciones import sincronizar_conductor_de_estudiantes

        ruta.estudiantes.set(estudiantes)
        ruta.estudiantes_count = len(estudiantes)
        if ruta.conductor_perfil:
            usuario = ruta.conductor_perfil.usuario
            ruta.conductor = usuario.get_full_name() or usuario.email
        else:
            ruta.conductor = ''
        ruta.save(update_fields=['conductor', 'estudiantes_count', 'updated_at'])
        # Incluye a los estudiantes quitados para liberar su conductor anterior.
        sincronizar_conductor_de_estudiantes({e.id for e in estudiantes} | set(anteriores_ids))

    def create(self, validated_data):
        estudiantes = validated_data.pop('estudiantes', [])
        ruta = super().create(validated_data)
        self._sync_relations(ruta, estudiantes)
        return ruta

    def update(self, instance, validated_data):
        estudiantes = validated_data.pop('estudiantes', None)
        anteriores_ids = list(instance.estudiantes.values_list('id', flat=True))
        ruta = super().update(instance, validated_data)
        if estudiantes is None:
            estudiantes = list(ruta.estudiantes.all().order_by('id'))
        self._sync_relations(ruta, estudiantes, anteriores_ids)
        return ruta
