from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from uuid import uuid4

from .almacenamiento import almacenamiento_fotos_estudiantes
from .campos import EmbeddingCifradoField, RutField
from .nombres import normalizar_nombre


def foto_estudiante_upload_to(instance, filename):
    """Genera un nombre no predecible para el archivo privado."""
    return f"fotos_estudiantes/{uuid4().hex}.jpg"

def foto_apoderado_upload_to(instance, filename):
    return f"fotos_apoderados/{uuid4().hex}.jpg"

def foto_delegado_upload_to(instance, filename):
    return f"fotos_delegados/{uuid4().hex}.jpg"

class ActivosManager(models.Manager):
    """Por defecto solo se ven los registros activos. Los desactivados están en `Modelo.todos`."""

    def get_queryset(self):
        return super().get_queryset().filter(activo=True)


def unir_direccion(*partes):
    """Une calle y número, comuna y región omitiendo las partes vacías."""
    return ', '.join(parte.strip() for parte in partes if parte and parte.strip())

class Colegio(models.Model):
    # Básico y Estándar tienen una sola sede (la principal, oculta). Solo Avanzado es multisede.
    # El límite de estudiantes de cada plan todavía no se aplica.
    PLAN_BASICO = 'basico'
    PLAN_ESTANDAR = 'estandar'
    PLAN_AVANZADO = 'avanzado'
    PLANES = (
        (PLAN_BASICO, 'Básico'),
        (PLAN_ESTANDAR, 'Estándar'),
        (PLAN_AVANZADO, 'Avanzado (multisede)'),
    )

    nombre = models.CharField(max_length=200, unique=True)
    plan = models.CharField(max_length=20, choices=PLANES, default=PLAN_BASICO)
    rbd = models.CharField(max_length=50, null=True, blank=True)
    direccion = models.CharField(max_length=255, null=True, blank=True)
    comuna = models.CharField(max_length=100, blank=True, default='')
    region = models.CharField(max_length=100, blank=True, default='')
    # Ubicación del establecimiento cuando la ruta no utiliza una sede.
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    telefono = models.CharField(max_length=50, null=True, blank=True)
    email_contacto = models.EmailField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    # Papelera: nada se borra; se desactiva y se puede reactivar desde el panel.
    desactivado_en = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    @property
    def direccion_completa(self):
        return unir_direccion(self.direccion, self.comuna, self.region)

    @property
    def es_multisede(self):
        return self.plan == self.PLAN_AVANZADO

    def sede_principal(self):
        return self.sedes.filter(es_principal=True).first()


class Sede(models.Model):
    # Datos que la sede principal copia siempre de su colegio.
    CAMPOS_DEL_COLEGIO = ('direccion', 'comuna', 'region', 'latitud', 'longitud', 'telefono')

    colegio = models.ForeignKey(Colegio, on_delete=models.CASCADE, related_name='sedes')
    # Se crea junto con el colegio y usa sus mismos datos. En Básico y Estándar es la única y no se muestra.
    es_principal = models.BooleanField(default=False)
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255, null=True, blank=True)
    comuna = models.CharField(max_length=100, blank=True, default='')
    region = models.CharField(max_length=100, blank=True, default='')
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    telefono = models.CharField(max_length=50, null=True, blank=True)
    activa = models.BooleanField(default=True)
    # Papelera: nada se borra; se desactiva y se puede reactivar desde el panel.
    desactivado_en = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['colegio'], condition=Q(es_principal=True), name='una_sede_principal_por_colegio',
            ),
        ]

    def __str__(self):
        return f"{self.colegio.nombre} - {self.nombre}"

    @property
    def oculta(self):
        """En los colegios que no son multisede la sede existe, pero no se muestra en ninguna pantalla."""
        return not self.colegio.es_multisede

    @property
    def direccion_completa(self):
        return unir_direccion(self.direccion, self.comuna, self.region)


class Usuario(AbstractUser):
    ROLES = (
        ('admin_plataforma', 'Administrador de Plataforma'),
        ('admin_colegio', 'Administrador de Colegio'),
        ('apoderado', 'Apoderado'),
        ('conductor', 'Conductor'),
        ('admin', 'Administrador'),
        ('delegado', 'Delegado'),
    )

    email = models.EmailField(unique=True)
    rol = models.CharField(max_length=30, choices=ROLES, default='apoderado')
    colegio = models.ForeignKey(
        Colegio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios'
    )
    # Las cuentas creadas por un administrador parten con una contraseña
    # que él conoce, así que la persona debe cambiarla al primer ingreso.
    debe_cambiar_password = models.BooleanField(default=False)
    # Papelera: nada se borra; se desactiva y se puede reactivar desde el panel.
    desactivado_en = models.DateTimeField(null=True, blank=True)
    # Última versión de los términos que aceptó. El detalle queda en AceptacionTerminos.
    terminos_version_aceptada = models.CharField(max_length=20, blank=True, default='')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta(AbstractUser.Meta):
        constraints = [
            models.CheckConstraint(
                condition=~Q(rol='admin_plataforma') | Q(colegio__isnull=True),
                name='admin_plataforma_sin_colegio',
            ),
            models.CheckConstraint(
                condition=~Q(rol='admin_colegio') | Q(colegio__isnull=False),
                name='admin_colegio_con_colegio',
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.rol == 'admin_plataforma' and self.colegio_id is not None:
            errors['colegio'] = 'El administrador de plataforma no debe tener un colegio fijo.'
        if self.rol == 'admin_colegio':
            if self.colegio_id is None:
                errors['colegio'] = 'El administrador de colegio debe tener un colegio asignado.'
            elif not self.colegio.activo:
                errors['colegio'] = 'El administrador no puede asignarse a un colegio inactivo.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        self.first_name = normalizar_nombre(self.first_name)
        self.last_name = normalizar_nombre(self.last_name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} ({self.get_rol_display()})"


class PerfilApoderado(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name='perfil_apoderado'
    )
    colegio = models.ForeignKey(
        Colegio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='apoderados'
    )
    rut = RutField(unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    foto = models.ImageField(
        upload_to=foto_apoderado_upload_to,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Apoderado: {self.usuario.get_full_name()} ({self.rut})"


class PerfilConductor(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name='perfil_conductor'
    )
    colegio = models.ForeignKey(
        Colegio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conductores'
    )
    rut = RutField(unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    licencia_conducir = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Conductor: {self.usuario.get_full_name()} ({self.rut})"


class PerfilDelegado(models.Model):
    TIPOS = (
        ('autorizado', 'Persona autorizada por apoderado'),
        ('inspector', 'Inspector del establecimiento'),
    )

    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name='perfil_delegado'
    )
    colegio = models.ForeignKey(
        Colegio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delegados'
    )
    rut = RutField(unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    tipo_delegado = models.CharField(max_length=20, choices=TIPOS, default='autorizado')
    foto = models.ImageField(
        upload_to=foto_delegado_upload_to,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Delegado: {self.usuario.get_full_name()} ({self.rut})"


class DelegadoSede(models.Model):
    """Sede de un inspector. Cada inspector tiene una sola sede; una sede puede tener varios inspectores."""

    # PROTECT: una sede con inspectores no se puede borrar; primero se los cambia de sede.
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='inspectores')
    delegado = models.ForeignKey(PerfilDelegado, on_delete=models.CASCADE, related_name='sedes_responsable')
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['delegado'], name='inspector_con_una_sola_sede'),
        ]

    def clean(self):
        if self.delegado.colegio_id and self.delegado.colegio_id != self.sede.colegio_id:
            raise ValidationError({'delegado': 'El delegado debe pertenecer al colegio de la sede.'})


class Estudiante(models.Model):
    apoderado = models.ForeignKey(
        PerfilApoderado,
        on_delete=models.CASCADE,
        related_name='estudiantes'
    )
    conductor = models.ForeignKey(
        PerfilConductor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='estudiantes_asignados'
    )
    nombre = models.CharField(max_length=150)
    apellido = models.CharField(max_length=150)
    rut = RutField(unique=True)
    fecha_nacimiento = models.DateField()
    colegio_texto_legacy = models.CharField(max_length=200, null=True, blank=True)
    colegio = models.ForeignKey(
        Colegio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='estudiantes'
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='estudiantes'
    )
    curso = models.CharField(max_length=100)
    direccion_principal = models.CharField(max_length=255)
    comuna = models.CharField(max_length=100, blank=True, default='')
    region = models.CharField(max_length=100, blank=True, default='')
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    ubicacion_confirmada = models.BooleanField(default=False)
    direccion_alternativa = models.CharField(max_length=255, null=True, blank=True)
    persona_autorizada = models.CharField(max_length=200, null=True, blank=True)
    rut_persona_autorizada = RutField(null=True, blank=True)
    foto = models.ImageField(
        upload_to=foto_estudiante_upload_to,
        # Se guarda cifrada en el disco con la misma clave de los vectores faciales.
        storage=almacenamiento_fotos_estudiantes,
        null=True,
        blank=True,
        help_text='Foto privada del estudiante, cifrada; nunca se publica como archivo estático.'
    )
    embedding_facial = EmbeddingCifradoField(
        null=True,
        blank=True,
        help_text='Vector facial SFace (128 floats), cifrado en la base de datos'
    )
    embedding_facial_version = models.CharField(max_length=100, null=True, blank=True)
    # Consentimiento biométrico de ESTE hijo (Ley 21.719): lo da su apoderado al inscribirlo o desde
    # su detalle, y lo puede retirar cuando quiera. Sin él, sube y baja con QR o con el inspector.
    # Cada cambio queda en ConsentimientoBiometrico, que no se edita ni se borra.
    autoriza_biometria = models.BooleanField(default=False)
    autoriza_biometria_en = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    # Papelera: nada se borra; se desactiva y se puede reactivar desde el panel.
    desactivado_en = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # `objects` solo ve estudiantes activos; `todos` incluye los de la papelera.
    objects = ActivosManager()
    todos = models.Manager()

    def save(self, *args, **kwargs):
        self.nombre = normalizar_nombre(self.nombre)
        self.apellido = normalizar_nombre(self.apellido)
        self.persona_autorizada = normalizar_nombre(self.persona_autorizada)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Estudiante: {self.nombre} {self.apellido} ({self.rut})"

    @property
    def direccion_completa(self):
        return unir_direccion(self.direccion_principal, self.comuna, self.region)


class PersonaAutorizada(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='personas_autorizadas')
    apoderado = models.ForeignKey(PerfilApoderado, on_delete=models.CASCADE, related_name='personas_autorizadas')
    colegio = models.ForeignKey(Colegio, on_delete=models.CASCADE, related_name='personas_autorizadas')
    perfil_delegado = models.ForeignKey(
        PerfilDelegado, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='autorizaciones_estudiantes',
    )
    nombre = models.CharField(max_length=200)
    rut = RutField()
    telefono = models.CharField(max_length=20, blank=True, default='')
    activa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['estudiante', 'rut'], name='autorizado_unico_por_estudiante'),
        ]

    def save(self, *args, **kwargs):
        self.nombre = normalizar_nombre(self.nombre)
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.apoderado_id != self.estudiante.apoderado_id:
            errors['apoderado'] = 'El autorizado debe pertenecer al apoderado del estudiante.'
        if self.colegio_id != self.estudiante.colegio_id:
            errors['colegio'] = 'El autorizado debe pertenecer al colegio del estudiante.'
        if errors:
            raise ValidationError(errors)


from django.utils import timezone
from datetime import timedelta


class CodigoRecuperacion(models.Model):

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='codigos_recuperacion'
    )

    codigo = models.CharField(max_length=6)

    creado_en = models.DateTimeField(auto_now_add=True)

    usado = models.BooleanField(default=False)

    def esta_vigente(self):
        return (
            not self.usado
            and timezone.now() <= self.creado_en + timedelta(minutes=10)
        )

    def __str__(self):
        return f'{self.usuario.email} - {self.codigo}'


class FCMToken(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='fcm_tokens'
    )
    token = models.TextField(unique=True)
    device_name = models.CharField(max_length=100, null=True, blank=True, default='Dispositivo Móvil')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.usuario.email} - {self.device_name} ({'Activo' if self.is_active else 'Inactivo'})"


class Notificacion(models.Model):
    TIPOS = (
        ('ruta_iniciada', 'Ruta Iniciada'),
        ('estudiante_abordo', 'Estudiante Abordó'),
        ('estudiante_llego', 'Estudiante Llegó'),
        ('estudiante_ausente', 'Estudiante Ausente'),
        ('ruta_finalizada', 'Ruta Finalizada'),
        ('emergencia', 'Alerta de Emergencia'),
        ('aviso_sistema', 'Aviso del Sistema'),
    )

    apoderado = models.ForeignKey(
        PerfilApoderado,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notificaciones'
    )
    destinatario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, null=True, blank=True,
        related_name='notificaciones_recibidas',
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notificaciones'
    )
    titulo = models.CharField(max_length=150)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=30, choices=TIPOS, default='aviso_sistema')
    leido = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        usuario = self.destinatario or (self.apoderado.usuario if self.apoderado_id else None)
        return f"[{self.get_tipo_display()}] {usuario.email if usuario else 'Sin destinatario'}: {self.titulo}"


class Furgon(models.Model):
    ESTADOS = (
        ('disponible', 'Disponible'),
        ('en_ruta', 'En Ruta'),
        ('mantenimiento', 'Mantenimiento'),
    )
    colegio = models.ForeignKey(
        Colegio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='furgones'
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='furgones'
    )
    patente = models.CharField(max_length=20, unique=True)
    marca_modelo = models.CharField(max_length=100)
    capacidad = models.IntegerField(default=15)
    conductor_asignado = models.CharField(max_length=150, blank=True, default='')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='disponible')
    activo = models.BooleanField(default=True)
    # Papelera: nada se borra; se desactiva y se puede reactivar desde el panel.
    desactivado_en = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActivosManager()
    todos = models.Manager()

    def __str__(self):
        return f"{self.patente} - {self.marca_modelo}"


class Ruta(models.Model):
    SENTIDOS = (
        ('hacia_colegio', 'Hacia el colegio'),
        ('desde_colegio', 'Desde el colegio'),
    )
    ESTADOS = (
        ('activa', 'Activa'),
        ('en_ruta', 'En ruta'),
        ('finalizada', 'Finalizada'),
        ('inactiva', 'Inactiva'),
    )
    nombre = models.CharField(max_length=150)
    sentido = models.CharField(max_length=20, choices=SENTIDOS, default='hacia_colegio')
    conductor = models.CharField(max_length=150, blank=True, default='')
    colegio_texto_legacy = models.CharField(max_length=200, null=True, blank=True, default='')
    colegio = models.ForeignKey(
        Colegio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rutas'
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rutas'
    )
    conductor_perfil = models.ForeignKey(
        PerfilConductor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rutas'
    )
    furgon = models.ForeignKey(
        Furgon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rutas'
    )
    estudiantes = models.ManyToManyField(
        Estudiante,
        blank=True,
        related_name='rutas'
    )
    estudiantes_abordados = models.ManyToManyField(
        Estudiante,
        blank=True,
        related_name='rutas_abordadas',
    )
    estudiantes_entregados = models.ManyToManyField(
        Estudiante,
        blank=True,
        related_name='rutas_entregadas',
    )
    paradas_completadas = models.ManyToManyField(
        Estudiante,
        blank=True,
        related_name='rutas_con_parada_completada',
    )
    # Estudiantes que no se presentaron en su domicilio durante la ida.
    estudiantes_ausentes = models.ManyToManyField(
        Estudiante,
        blank=True,
        related_name='rutas_ausente',
    )
    # Vuelta: llamados cuando eran la parada actual; solo a ellos se les puede marcar "No se recibió".
    estudiantes_llamados = models.ManyToManyField(
        Estudiante,
        blank=True,
        related_name='rutas_llamado',
    )
    # Vuelta: nadie los recibió en su casa; siguen a bordo y vuelven al colegio.
    estudiantes_no_recibidos = models.ManyToManyField(
        Estudiante,
        blank=True,
        related_name='rutas_no_recibido',
    )
    origen_direccion = models.CharField(max_length=255, blank=True, default='')
    destino_direccion = models.CharField(max_length=255, blank=True, default='')
    origen_latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    origen_longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    destino_latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    destino_longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    estudiantes_count = models.IntegerField(default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='activa')
    # Hora de salida esperada; sin ella no se puede medir si el recorrido partió atrasado.
    hora_programada = models.TimeField(null=True, blank=True)
    # Vuelta: desde este momento ya no sube nadie y se puede entregar en las casas.
    reparto_iniciado_en = models.DateTimeField(null=True, blank=True)
    # Dónde estaba el furgón al reincorporar a un niño; rige el orden hasta la siguiente entrega.
    origen_recalculo_latitud = models.FloatField(null=True, blank=True)
    origen_recalculo_longitud = models.FloatField(null=True, blank=True)
    iniciada_en = models.DateTimeField(null=True, blank=True)
    finalizada_en = models.DateTimeField(null=True, blank=True)
    ultima_latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    ultima_longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    precision_gps_metros = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    ubicacion_actualizada_en = models.DateTimeField(null=True, blank=True)
    # Solo en modo demostración: el administrador permite que el conductor simule el recorrido.
    simulacion_activa = models.BooleanField(default=False)
    # Ruta en la papelera. Distinto de `estado`, que es su situación en el día (activa, en ruta, etc.).
    activo = models.BooleanField(default=True)
    # Papelera: nada se borra; se desactiva y se puede reactivar desde el panel.
    desactivado_en = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActivosManager()
    todos = models.Manager()

    def __str__(self):
        return f"{self.nombre} ({self.colegio.nombre if self.colegio else 'Sin Colegio'})"


class Emergencia(models.Model):
    CATEGORIAS = (
        ('emergencia_ruta', 'Emergencia en Ruta'),
        ('emergencia_estudiante', 'Emergencia de Estudiante'),
    )

    conductor = models.ForeignKey(
        PerfilConductor,
        on_delete=models.CASCADE,
        related_name='emergencias_reportadas'
    )
    ruta = models.ForeignKey(
        Ruta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emergencias'
    )
    colegio = models.ForeignKey(
        Colegio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emergencias'
    )
    furgon = models.ForeignKey(
        Furgon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emergencias'
    )
    categoria = models.CharField(max_length=30, choices=CATEGORIAS, default='emergencia_ruta')
    tipo_emergencia = models.CharField(max_length=100)
    descripcion = models.TextField()
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emergencias'
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"[{self.get_categoria_display()}] {self.conductor.usuario.email} - {self.tipo_emergencia}"


class CodigoQREntrega(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='codigos_qr_entrega')
    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.CASCADE, null=True, blank=True,
        related_name='codigos_qr_entrega'
    )
    expira_en = models.DateTimeField()
    usado_en = models.DateTimeField(null=True, blank=True)
    # QR fijo del delegado: solo existe y solo sirve con MODO_DEMOSTRACION=True (presentación).
    # No vence en minutos ni se gasta al usarlo; las reglas de la ruta se siguen aplicando.
    estatico = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']


class RegistroAbordaje(models.Model):
    METODOS = (
        ('facial', 'Reconocimiento facial'),
        ('qr', 'Codigo QR del estudiante'),
        ('validacion_institucional', 'Validacion institucional'),
    )

    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.PROTECT, related_name='registros_abordaje'
    )
    ruta = models.ForeignKey(
        Ruta, on_delete=models.PROTECT, related_name='registros_abordaje'
    )
    conductor = models.ForeignKey(
        PerfilConductor, on_delete=models.PROTECT, related_name='registros_abordaje'
    )
    colegio = models.ForeignKey(
        Colegio, on_delete=models.PROTECT, related_name='registros_abordaje'
    )
    delegado = models.ForeignKey(
        PerfilDelegado, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='registros_abordaje_validados',
    )
    metodo_validacion = models.CharField(max_length=32, choices=METODOS)
    abordado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Historial: la ruta se repite cada día, así que hay un registro por recorrido.
        ordering = ['-abordado_en']


class RegistroEntrega(models.Model):
    TIPOS_RECEPTOR = (
        ('apoderado', 'Apoderado titular'),
        ('persona_autorizada', 'Persona autorizada'),
        ('delegado_institucional', 'Delegado institucional'),
        ('domicilio', 'Entrega en domicilio (rostro del estudiante)'),
    )
    METODOS = (('facial', 'Reconocimiento facial'), ('qr', 'Código QR'))

    estudiante = models.ForeignKey(Estudiante, on_delete=models.PROTECT, related_name='registros_entrega')
    conductor = models.ForeignKey(PerfilConductor, on_delete=models.PROTECT, related_name='registros_entrega')
    ruta = models.ForeignKey(Ruta, on_delete=models.PROTECT, related_name='registros_entrega')
    colegio = models.ForeignKey(Colegio, on_delete=models.PROTECT, related_name='registros_entrega')
    persona_autorizada = models.ForeignKey(
        PersonaAutorizada, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='registros_entrega',
    )
    perfil_delegado = models.ForeignKey(
        PerfilDelegado, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='registros_entrega',
    )
    tipo_receptor = models.CharField(max_length=30, choices=TIPOS_RECEPTOR)
    receptor_nombre = models.CharField(max_length=200)
    receptor_rut = RutField(blank=True, default='')
    metodo_validacion = models.CharField(max_length=20, choices=METODOS)
    destino = models.CharField(max_length=255)
    entregado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Historial: la ruta se repite cada día, así que hay un registro por recorrido.
        ordering = ['-entregado_en']


class RecorridoRuta(models.Model):
    """Una pasada de una ruta. Copia sus datos para que el historial sobreviva a cambios en la ruta."""

    ruta = models.ForeignKey(Ruta, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorridos')
    colegio = models.ForeignKey(Colegio, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorridos')
    nombre_ruta = models.CharField(max_length=150)
    sentido = models.CharField(max_length=20, choices=Ruta.SENTIDOS, default='hacia_colegio')
    conductor_nombre = models.CharField(max_length=200, blank=True, default='')
    furgon_patente = models.CharField(max_length=20, blank=True, default='')
    hora_programada = models.TimeField(null=True, blank=True)
    minutos_atraso = models.IntegerField(null=True, blank=True)
    # Recorrido hecho con el simulador: no cuenta en los reportes salvo que se pida.
    simulado = models.BooleanField(default=False)
    estudiantes = models.JSONField(default=list, blank=True)
    iniciado_en = models.DateTimeField(null=True, blank=True)
    finalizado_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en', '-id']

    def __str__(self):
        return f'{self.nombre_ruta} ({self.creado_en:%Y-%m-%d %H:%M})'


class EventoRecorrido(models.Model):
    TIPOS = (
        ('inicio', 'Inicio de ruta'),
        ('abordaje', 'Subió al furgón'),
        ('ausente', 'No subió / ausente'),
        ('no_asiste', 'Avisó inasistencia'),
        ('inicio_reparto', 'Inicio del reparto'),
        ('llamada', 'Llamada'),
        ('no_recibido', 'No se recibió'),
        ('reincorporado', 'Apoderado disponible'),
        ('aviso_llegada', 'Aviso de llegada'),
        ('entrega', 'Entregado'),
        ('emergencia', 'Emergencia'),
        ('fin', 'Fin de ruta'),
    )

    recorrido = models.ForeignKey(RecorridoRuta, on_delete=models.CASCADE, related_name='eventos')
    tipo = models.CharField(max_length=20, choices=TIPOS)
    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.SET_NULL, null=True, blank=True, related_name='eventos_recorrido',
    )
    estudiante_nombre = models.CharField(max_length=300, blank=True, default='')
    metodo = models.CharField(max_length=60, blank=True, default='')
    persona_nombre = models.CharField(max_length=200, blank=True, default='')
    persona_rol = models.CharField(max_length=60, blank=True, default='')
    persona_rut = RutField(blank=True, default='')
    detalle = models.TextField(blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['creado_en', 'id']


class InasistenciaEstudiante(models.Model):
    """Aviso del apoderado: el estudiante no usará el furgón ese día (ida, vuelta o ambos)."""

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='inasistencias')
    fecha = models.DateField()
    ida = models.BooleanField(default=False)
    vuelta = models.BooleanField(default=False)
    motivo = models.CharField(max_length=200, blank=True, default='')
    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inasistencias_registradas',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha']
        constraints = [
            models.UniqueConstraint(fields=['estudiante', 'fecha'], name='inasistencia_unica_por_dia'),
        ]

    def __str__(self):
        tramos = [nombre for nombre, activo in (('ida', self.ida), ('vuelta', self.vuelta)) if activo]
        return f'{self.estudiante} - {self.fecha} ({", ".join(tramos) or "asiste"})'


class RutHabilitado(models.Model):
    """RUT que un colegio autorizó para crear una cuenta de apoderado."""

    colegio = models.ForeignKey(Colegio, on_delete=models.CASCADE, related_name='ruts_habilitados')
    rut = RutField()
    # Vacío mientras esté disponible.
    apoderado = models.ForeignKey(
        PerfilApoderado, on_delete=models.SET_NULL, null=True, blank=True, related_name='ruts_habilitados',
    )
    usado_en = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='ruts_habilitados_cargados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    # Última vez que un administrador liberó este RUT.
    liberado_en = models.DateTimeField(null=True, blank=True)
    liberado_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='ruts_habilitados_liberados',
    )
    cuenta_liberada = models.CharField(max_length=320, blank=True, default='')
    # Un RUT quitado de la lista queda inactivo: ya no sirve para registrarse, pero se puede reactivar.
    activo = models.BooleanField(default=True)
    # Papelera: nada se borra; se desactiva y se puede reactivar desde el panel.
    desactivado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creado_en', '-id']
        constraints = [
            models.UniqueConstraint(fields=['colegio', 'rut'], name='rut_habilitado_unico_por_colegio'),
        ]

    def __str__(self):
        return f'{self.rut} ({self.colegio.nombre})'


class EstudianteHabilitado(models.Model):
    """
    Estudiante que un colegio autorizó para que su apoderado lo inscriba desde la app.

    El colegio carga el par (RUT del apoderado, RUT del estudiante). Así, cuando el apoderado agrega a su
    hijo, el colegio sale de esta habilitación y no lo elige él: un apoderado con hijos en dos colegios no
    puede inscribir a uno en el colegio equivocado. Un estudiante solo puede estar habilitado en un colegio.
    """

    colegio = models.ForeignKey(Colegio, on_delete=models.CASCADE, related_name='estudiantes_habilitados')
    rut = RutField()
    rut_apoderado = RutField()
    # Se llena cuando el apoderado inscribe al estudiante.
    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.SET_NULL, null=True, blank=True, related_name='habilitaciones',
    )
    usado_en = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='estudiantes_habilitados_cargados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    # Papelera: nada se borra; se desactiva y se puede reactivar desde el panel.
    desactivado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creado_en', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['rut'], condition=Q(activo=True), name='estudiante_habilitado_en_un_solo_colegio',
            ),
        ]

    def __str__(self):
        return f'{self.rut} → {self.rut_apoderado} ({self.colegio.nombre})'


class AceptacionTerminos(models.Model):
    """Constancia de aceptación. Copia los datos para que sobreviva a cambios en la cuenta."""

    ORIGENES = (
        ('registro', 'Al crear su cuenta en la app'),
        ('ingreso', 'Al ingresar a la app'),
    )

    usuario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='aceptaciones_terminos',
    )
    colegio = models.ForeignKey(
        Colegio, on_delete=models.SET_NULL, null=True, blank=True, related_name='aceptaciones_terminos',
    )
    colegio_nombre = models.CharField(max_length=200, blank=True, default='')
    rut = RutField(blank=True, default='')
    nombre = models.CharField(max_length=300, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    version = models.CharField(max_length=20)
    huella_texto = models.CharField(max_length=64)
    acepta_biometria = models.BooleanField(default=False)
    origen = models.CharField(max_length=20, choices=ORIGENES)
    ip = models.GenericIPAddressField(null=True, blank=True)
    dispositivo = models.CharField(max_length=255, blank=True, default='')
    aceptado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-aceptado_en', '-id']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'version'], name='aceptacion_unica_por_version'),
        ]

    def __str__(self):
        return f'{self.nombre} - v{self.version} ({self.aceptado_en:%Y-%m-%d %H:%M})'


class CambioBiometria(models.Model):
    """Historial ANTIGUO (términos 1.0 y 1.1): la autorización general del apoderado para todos sus hijos.

    Desde los términos 1.2 ya no se escribe: el consentimiento es por hijo y queda en
    ConsentimientoBiometrico. Se conserva como respaldo de lo que pasó antes.
    """

    ORIGENES = (
        ('registro', 'Al crear su cuenta'),
        ('terminos', 'Al aceptar los términos'),
        ('perfil', 'Desde su perfil'),
    )

    usuario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='cambios_biometria',
    )
    colegio = models.ForeignKey(
        Colegio, on_delete=models.SET_NULL, null=True, blank=True, related_name='cambios_biometria',
    )
    colegio_nombre = models.CharField(max_length=200, blank=True, default='')
    nombre = models.CharField(max_length=300, blank=True, default='')
    rut = RutField(blank=True, default='')
    email = models.EmailField(blank=True, default='')
    autoriza = models.BooleanField()
    origen = models.CharField(max_length=20, choices=ORIGENES)
    # Al retirarla se borran las fotos de sus hijos: queda cuántas.
    fotos_eliminadas = models.PositiveIntegerField(default=0)
    ip = models.GenericIPAddressField(null=True, blank=True)
    dispositivo = models.CharField(max_length=255, blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en', '-id']

    def __str__(self):
        return f'{self.nombre} - {"autoriza" if self.autoriza else "retira"} ({self.creado_en:%Y-%m-%d %H:%M})'


class RegistroInmutableError(Exception):
    """Se intentó modificar o borrar una constancia de consentimiento."""


class _ConsentimientoQuerySet(models.QuerySet):
    # Lo único que se permite cambiar es soltar la referencia (NULL) cuando se borra el estudiante,
    # el apoderado o el colegio: la constancia guarda su propia copia de nombres y RUT.
    REFERENCIAS = {'apoderado', 'estudiante', 'colegio'}

    def update(self, **kwargs):
        if kwargs and all(campo in self.REFERENCIAS and valor is None for campo, valor in kwargs.items()):
            return super().update(**kwargs)
        raise RegistroInmutableError('Las constancias de consentimiento no se modifican.')

    def delete(self):
        raise RegistroInmutableError('Las constancias de consentimiento no se borran.')


class ConsentimientoBiometrico(models.Model):
    """Constancia inmutable de cada vez que un apoderado otorga o revoca la biometría de UN hijo.

    Ley 21.719 (arts. 7, 12 y 14 ter): sirve de respaldo legal aunque después se borren la foto y el
    vector del estudiante, o el estudiante mismo. Por eso guarda una copia de los nombres y RUT, y sus
    llaves quedan en NULL (no se borran) si desaparece el registro original.

    Solo se crean filas: guardar una existente, `update()` o `delete()` lanzan RegistroInmutableError.
    """

    EVENTOS = (
        ('otorgado', 'Otorgado'),
        ('revocado', 'Revocado'),
    )
    ORIGENES = (
        ('agregar_hijo', 'Al inscribir al hijo'),
        ('detalle_hijo', 'Desde el detalle del hijo'),
        ('desactivacion', 'Al desactivar al estudiante'),
        ('migracion', 'Cambio a consentimiento por hijo (términos 1.2)'),
    )

    apoderado = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='consentimientos_biometricos',
    )
    estudiante = models.ForeignKey(
        'Estudiante', on_delete=models.SET_NULL, null=True, blank=True, related_name='consentimientos_biometricos',
    )
    colegio = models.ForeignKey(
        Colegio, on_delete=models.SET_NULL, null=True, blank=True, related_name='consentimientos_biometricos',
    )
    apoderado_nombre = models.CharField(max_length=300, blank=True, default='')
    apoderado_rut = RutField(blank=True, default='')
    apoderado_email = models.EmailField(blank=True, default='')
    estudiante_nombre = models.CharField(max_length=300, blank=True, default='')
    estudiante_rut = RutField(blank=True, default='')
    colegio_nombre = models.CharField(max_length=200, blank=True, default='')
    evento = models.CharField(max_length=10, choices=EVENTOS)
    origen = models.CharField(max_length=20, choices=ORIGENES)
    version_terminos = models.CharField(max_length=20, blank=True, default='')
    # Al revocar se borran al tiro la foto y el vector facial del hijo.
    datos_eliminados = models.BooleanField(default=False)
    ip = models.GenericIPAddressField(null=True, blank=True)
    dispositivo = models.CharField(max_length=255, blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)

    objects = _ConsentimientoQuerySet.as_manager()

    class Meta:
        ordering = ['-creado_en', '-id']

    def save(self, *args, **kwargs):
        if self.pk is not None and not kwargs.get('force_insert'):
            raise RegistroInmutableError('Las constancias de consentimiento no se modifican.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroInmutableError('Las constancias de consentimiento no se borran.')

    def __str__(self):
        return f'{self.estudiante_nombre} - {self.get_evento_display()} ({self.creado_en:%Y-%m-%d %H:%M})'
