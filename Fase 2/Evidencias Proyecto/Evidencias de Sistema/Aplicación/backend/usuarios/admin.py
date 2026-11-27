from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Usuario, PerfilApoderado, PerfilConductor, PerfilDelegado, Estudiante, CodigoRecuperacion, Colegio, Sede,
    Furgon, Ruta, ConsentimientoBiometrico,
)


@admin.register(Colegio)
class ColegioAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'rbd', 'telefono', 'email_contacto', 'activo', 'created_at')
    search_fields = ('nombre', 'rbd', 'email_contacto')
    list_filter = ('activo',)


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'colegio', 'telefono', 'activa', 'created_at')
    search_fields = ('nombre', 'colegio__nombre')
    list_filter = ('colegio', 'activa')


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'rol', 'colegio', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('rol', 'colegio', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    fieldsets = UserAdmin.fieldsets + (
        ('Rol y Colegio', {'fields': ('rol', 'colegio')}),
    )


@admin.register(PerfilApoderado)
class PerfilApoderadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'colegio', 'rut', 'telefono', 'created_at')
    search_fields = ('usuario__email', 'usuario__first_name', 'usuario__last_name', 'rut', 'telefono')
    list_filter = ('colegio',)
    raw_id_fields = ('usuario',)


@admin.register(PerfilConductor)
class PerfilConductorAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'colegio', 'rut', 'telefono', 'licencia_conducir', 'created_at')
    search_fields = ('usuario__email', 'usuario__first_name', 'usuario__last_name', 'rut', 'telefono', 'licencia_conducir')
    list_filter = ('colegio',)
    raw_id_fields = ('usuario',)


@admin.register(PerfilDelegado)
class PerfilDelegadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'colegio', 'rut', 'telefono', 'created_at')
    search_fields = ('usuario__email', 'usuario__first_name', 'usuario__last_name', 'rut', 'telefono')
    list_filter = ('colegio',)
    raw_id_fields = ('usuario',)


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    # En el admin se ve todo, también lo que está en la papelera.
    def get_queryset(self, request):
        return Estudiante.todos.all()

    list_display = ('id', 'nombre', 'apellido', 'rut', 'colegio', 'sede', 'curso', 'apoderado', 'activo', 'created_at')
    search_fields = ('nombre', 'apellido', 'rut', 'curso', 'apoderado__usuario__email')
    list_filter = ('colegio', 'sede', 'curso')
    raw_id_fields = ('apoderado', 'conductor')
    # El admin mostraría el vector descifrado, y al guardar el formulario lo borraría.
    exclude = ('embedding_facial',)


@admin.register(Furgon)
class FurgonAdmin(admin.ModelAdmin):
    # En el admin se ve todo, también lo que está en la papelera.
    def get_queryset(self, request):
        return Furgon.todos.all()

    list_display = ('id', 'patente', 'marca_modelo', 'colegio', 'sede', 'capacidad', 'estado', 'activo', 'created_at')
    search_fields = ('patente', 'marca_modelo', 'conductor_asignado')
    list_filter = ('colegio', 'sede', 'estado')


@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    # En el admin se ve todo, también lo que está en la papelera.
    def get_queryset(self, request):
        return Ruta.todos.all()

    list_display = ('id', 'nombre', 'colegio', 'sede', 'conductor', 'estado', 'activo', 'created_at')
    search_fields = ('nombre', 'conductor')
    list_filter = ('colegio', 'sede', 'estado')


@admin.register(CodigoRecuperacion)
class CodigoRecuperacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'codigo', 'creado_en', 'usado')
    search_fields = ('usuario__email', 'codigo')
    list_filter = ('usado',)


@admin.register(ConsentimientoBiometrico)
class ConsentimientoBiometricoAdmin(admin.ModelAdmin):
    """Solo lectura: las constancias de consentimiento no se crean, editan ni borran a mano."""

    list_display = ('creado_en', 'estudiante_nombre', 'apoderado_nombre', 'colegio_nombre', 'evento', 'origen')
    search_fields = ('estudiante_nombre', 'estudiante_rut', 'apoderado_nombre', 'apoderado_rut')
    list_filter = ('evento', 'origen')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
