from django.contrib import admin
from django.urls import path, include
from rutas.auditoria_views import AuditoriaRecorridosView
from rutas.reportes_views import ReporteRecorridosView
from apoderados.ruts_views import LiberarRutView, RutHabilitadoDetalleView, RutsHabilitadosView
from apoderados.estudiantes_habilitados_views import (
    ConsultarHabilitacionView, EstudianteHabilitadoDetalleView, EstudiantesHabilitadosView,
)
from autenticacion.terminos_views import AuditoriaTerminosView
from apoderados.views import ApoderadoPerfilView, ApoderadoDetailView, ApoderadoListCreateView, CambiarPasswordView
from colegios.views import (
    ColegioListCreateView,
    ColegioDetailView,
    ColegioAdministradorDetailView,
    ColegioAdministradoresView,
    SedeListCreateView,
    SedeDetailView,
    GeoCoincidenciasView,
)
from conductor.views import (
    ConductorListCreateView,
    ConductorDetailView,
    ConductorEstudiantesListView,
    ConductorAsignarEstudiantesView,
    ConductorDesasignarEstudianteView,
)
from delegados.views import (
    DelegadoEstudiantesListView,
    DelegadoPerfilView,
    DelegadoAdminListCreateView,
    DelegadoAdminDetailView,
    DelegadoDesvincularEstudianteView,
)
from estudiantes.views import (
    EstudianteListCreateView,
    EstudianteDetailView,
    EstudianteBiometriaView,
    EstudianteFotoView,
    EstudianteSinAsignarListView,
    RegistrarRostroView,
    InasistenciasEstudianteView,
    PersonasAutorizadasEstudianteView,
    PersonaAutorizadaEstudianteDetailView,
)
from notificaciones.views import (
    RegistrarFCMTokenView,
    NotificacionListView,
    MarcarNotificacionLeidaView,
    MarcarTodasNotificacionesLeidasView,
    EliminarNotificacionView,
    EliminarTodasNotificacionesView,
    AvisoSistemaView,
)
from rutas.emergencias_views import EmergenciaCrearView
from rutas.facial_views import RutaEscaneoFacialView
from rutas.qr_views import (
    GenerarQREntregaView,
    RutaConfirmarEntregaMultipleView,
    RutaConsultarQREntregaView,
    RutaEscanearQRView,
)
from rutas.seguimiento_views import SeguimientoView
from rutas.validacion_institucional_views import (
    RutaConfirmarAbordajeInstitucionalView,
    RutaConsultarValidacionInstitucionalView,
)
from rutas.gestion_views import (
    RutaDetailView,
    RutaFinalizarView,
    RutaIniciarView,
    RutaListCreateView,
    RutaConductorActualView,
    RutaAvisarLlegadaView,
    RutaMarcarAusenteView,
    RutaIniciarRepartoView,
    RutaCorregirAbordajeView,
    RutaContactosEstudianteView,
    RutaRegistrarLlamadaView,
    RutaNoRecibidoView,
    RutaApoderadoDisponibleView,
    RutaActualizarUbicacionView,
    RutaSimulacionView,
)
from usuarios.views import DashboardStatsView
from usuarios.papelera_views import PapeleraEliminarView, PapeleraMoverView, PapeleraReactivarView, PapeleraView
from vehiculos.views import FurgonDetailView, FurgonListCreateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('usuarios.urls')),

    # Seguimiento GPS & En tiempo real
    path('api/seguimiento/', SeguimientoView.as_view(), name='seguimiento'),

    # Colegios & Sedes
    path('api/geo/coincidencias/', GeoCoincidenciasView.as_view(), name='geo-coincidencias'),
    path('api/colegios/', ColegioListCreateView.as_view(), name='colegios-list-create'),
    path('api/colegios/<int:pk>/', ColegioDetailView.as_view(), name='colegio-detail'),
    path('api/colegios/<int:colegio_id>/administradores/', ColegioAdministradoresView.as_view(), name='colegio-administradores'),
    path('api/colegios/<int:colegio_id>/administradores/<int:usuario_id>/', ColegioAdministradorDetailView.as_view(), name='colegio-administrador-detalle'),
    path('api/colegios/<int:colegio_id>/sedes/', SedeListCreateView.as_view(), name='sedes-list-create'),
    path('api/sedes/<int:pk>/', SedeDetailView.as_view(), name='sede-detail'),
    path('api/estudiantes/', EstudianteListCreateView.as_view(), name='estudiantes-list-create'),
    path('api/estudiantes/sin-asignar/', EstudianteSinAsignarListView.as_view(), name='estudiantes-sin-asignar'),
    path('api/estudiantes/<int:estudiante_id>/', EstudianteDetailView.as_view(), name='estudiante-detail'),
    path('api/estudiantes/<int:estudiante_id>/inasistencias/', InasistenciasEstudianteView.as_view(), name='estudiante-inasistencias'),
    path('api/estudiantes/<int:estudiante_id>/personas-autorizadas/', PersonasAutorizadasEstudianteView.as_view(), name='estudiante-personas-autorizadas'),
    path('api/estudiantes/<int:estudiante_id>/personas-autorizadas/<int:persona_id>/', PersonaAutorizadaEstudianteDetailView.as_view(), name='estudiante-persona-autorizada-detail'),
    path('api/estudiantes/<int:estudiante_id>/foto/', EstudianteFotoView.as_view(), name='estudiante-foto'),
    path('api/estudiantes/<int:estudiante_id>/biometria/', EstudianteBiometriaView.as_view(), name='estudiante-biometria'),
    path('api/estudiantes/<int:estudiante_id>/registrar-rostro/', RegistrarRostroView.as_view(), name='estudiante-registrar-rostro'),
    path('api/conductores/', ConductorListCreateView.as_view(), name='conductores-list-create'),
    path('api/conductores/<int:conductor_id>/', ConductorDetailView.as_view(), name='conductor-detail'),
    path('api/conductores/<int:conductor_id>/estudiantes/', ConductorEstudiantesListView.as_view(), name='conductor-estudiantes-list'),
    path('api/conductores/<int:conductor_id>/asignar-estudiantes/', ConductorAsignarEstudiantesView.as_view(), name='conductor-asignar-estudiantes'),
    path('api/conductores/<int:conductor_id>/desasignar-estudiante/', ConductorDesasignarEstudianteView.as_view(), name='conductor-desasignar-estudiante'),
    path('api/apoderados/', ApoderadoListCreateView.as_view(), name='apoderados-list-create'),
    path('api/apoderados/ruts-habilitados/', RutsHabilitadosView.as_view(), name='ruts-habilitados'),
    path('api/apoderados/ruts-habilitados/<int:entrada_id>/', RutHabilitadoDetalleView.as_view(), name='rut-habilitado-detalle'),
    path('api/apoderados/ruts-habilitados/<int:entrada_id>/liberar/', LiberarRutView.as_view(), name='rut-habilitado-liberar'),
    path('api/apoderados/estudiantes-habilitados/', EstudiantesHabilitadosView.as_view(), name='estudiantes-habilitados'),
    path(
        'api/apoderados/estudiantes-habilitados/<int:entrada_id>/',
        EstudianteHabilitadoDetalleView.as_view(), name='estudiante-habilitado-detalle',
    ),
    path('api/apoderado/habilitacion-estudiante/', ConsultarHabilitacionView.as_view(), name='habilitacion-estudiante'),
    path('api/apoderados/perfil/', ApoderadoPerfilView.as_view(), name='apoderado-perfil'),
    path('api/apoderados/<int:apoderado_id>/', ApoderadoDetailView.as_view(), name='apoderado-detail'),
    path('api/apoderados/<int:apoderado_id>/cambiar-password/', CambiarPasswordView.as_view(), name='apoderado-cambiar-password'),
    path('api/delegados/', DelegadoAdminListCreateView.as_view(), name='delegados-admin-list-create'),
    path('api/delegados/<int:delegado_id>/', DelegadoAdminDetailView.as_view(), name='delegado-admin-detail'),
    path('api/delegados/desvincular-estudiante/', DelegadoDesvincularEstudianteView.as_view(), name='delegado-desvincular-estudiante'),
    path('api/delegados/estudiantes/', DelegadoEstudiantesListView.as_view(), name='delegado-estudiantes-list'),
    path('api/delegados/perfil/', DelegadoPerfilView.as_view(), name='delegado-perfil'),
    path('api/dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('api/papelera/', PapeleraView.as_view(), name='papelera'),
    path('api/papelera/<str:tipo>/<int:pk>/reactivar/', PapeleraReactivarView.as_view(), name='papelera-reactivar'),
    path('api/papelera/<str:tipo>/<int:pk>/mover-al-colegio/', PapeleraMoverView.as_view(), name='papelera-mover'),
    path('api/papelera/<str:tipo>/<int:pk>/', PapeleraEliminarView.as_view(), name='papelera-eliminar'),
    path('api/auditoria/recorridos/', AuditoriaRecorridosView.as_view(), name='auditoria-recorridos'),
    path('api/reportes/recorridos/', ReporteRecorridosView.as_view(), name='reportes-recorridos'),
    path('api/auditoria/terminos/', AuditoriaTerminosView.as_view(), name='auditoria-terminos'),

    # Furgones & Rutas CRUD
    path('api/furgones/', FurgonListCreateView.as_view(), name='furgones-list-create'),
    path('api/furgones/<int:pk>/', FurgonDetailView.as_view(), name='furgon-detail'),
    path('api/rutas-admin/', RutaListCreateView.as_view(), name='rutas-admin-list-create'),
    path('api/rutas-admin/<int:pk>/', RutaDetailView.as_view(), name='rutas-admin-detail'),
    path('api/rutas-admin/<int:pk>/simulacion/', RutaSimulacionView.as_view(), name='rutas-admin-simulacion'),

    # Notificaciones & FCM
    path('api/notificaciones/fcm-token/', RegistrarFCMTokenView.as_view(), name='fcm-token-register'),
    path('api/notificaciones/', NotificacionListView.as_view(), name='notificaciones-list'),
    path('api/notificaciones/<int:notificacion_id>/marcar-leido/', MarcarNotificacionLeidaView.as_view(), name='notificacion-marcar-leido'),
    path('api/notificaciones/marcar-todas-leidas/', MarcarTodasNotificacionesLeidasView.as_view(), name='notificaciones-marcar-todas-leidas'),
    path('api/notificaciones/<int:notificacion_id>/eliminar/', EliminarNotificacionView.as_view(), name='notificacion-eliminar'),
    path('api/notificaciones/<int:notificacion_id>/', EliminarNotificacionView.as_view(), name='notificacion-eliminar-directo'),
    path('api/notificaciones/eliminar-todas/', EliminarTodasNotificacionesView.as_view(), name='notificaciones-eliminar-todas'),
    path('api/notificaciones/aviso-sistema/', AvisoSistemaView.as_view(), name='notificaciones-aviso-sistema'),

    # Acciones de Ruta & Emergencias (Generan Push automáticamente)
    path('api/rutas/mi-ruta/', RutaConductorActualView.as_view(), name='rutas-mi-ruta'),
    path('api/rutas/iniciar/', RutaIniciarView.as_view(), name='rutas-iniciar'),
    path('api/rutas/avisar-llegada/', RutaAvisarLlegadaView.as_view(), name='rutas-avisar-llegada'),
    path('api/rutas/marcar-ausente/', RutaMarcarAusenteView.as_view(), name='rutas-marcar-ausente'),
    path('api/rutas/iniciar-reparto/', RutaIniciarRepartoView.as_view(), name='rutas-iniciar-reparto'),
    path('api/rutas/corregir-abordaje/', RutaCorregirAbordajeView.as_view(), name='rutas-corregir-abordaje'),
    path('api/rutas/contactos-estudiante/', RutaContactosEstudianteView.as_view(), name='rutas-contactos-estudiante'),
    path('api/rutas/registrar-llamada/', RutaRegistrarLlamadaView.as_view(), name='rutas-registrar-llamada'),
    path('api/rutas/no-recibido/', RutaNoRecibidoView.as_view(), name='rutas-no-recibido'),
    path('api/rutas/apoderado-disponible/', RutaApoderadoDisponibleView.as_view(), name='rutas-apoderado-disponible'),
    path('api/rutas/ubicacion/', RutaActualizarUbicacionView.as_view(), name='rutas-actualizar-ubicacion'),
    path('api/rutas/escanear-qr/', RutaEscanearQRView.as_view(), name='rutas-escanear-qr'),
    path('api/rutas/escaneo-facial/', RutaEscaneoFacialView.as_view(), name='rutas-escaneo-facial'),
    path('api/rutas/consultar-qr-entrega/', RutaConsultarQREntregaView.as_view(), name='rutas-consultar-qr-entrega'),
    path('api/rutas/generar-qr-entrega/', GenerarQREntregaView.as_view(), name='rutas-generar-qr-entrega'),
    path('api/rutas/confirmar-entrega-multiple/', RutaConfirmarEntregaMultipleView.as_view(), name='rutas-confirmar-entrega-multiple'),
    path('api/rutas/consultar-validacion-institucional/', RutaConsultarValidacionInstitucionalView.as_view(), name='rutas-consultar-validacion-institucional'),
    path('api/rutas/confirmar-abordaje-institucional/', RutaConfirmarAbordajeInstitucionalView.as_view(), name='rutas-confirmar-abordaje-institucional'),
    path('api/rutas/finalizar/', RutaFinalizarView.as_view(), name='rutas-finalizar'),
    path('api/emergencias/', EmergenciaCrearView.as_view(), name='emergencias-crear'),
]
