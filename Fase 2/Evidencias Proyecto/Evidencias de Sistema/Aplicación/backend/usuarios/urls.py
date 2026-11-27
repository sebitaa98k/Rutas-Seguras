from django.urls import path

from apoderados.views import ColegiosRegistroView, RegistroApoderadoView
from autenticacion.views import (
    LoginView,
    AdminLoginView,
    SolicitarRecuperacionView,
    ConfirmarRecuperacionView,
    CambiarPasswordView,
)
from autenticacion.terminos_views import AceptarTerminosView, TerminosVigentesView
from delegados.views import RegistroDelegadoView

urlpatterns = [

    path(
        'registro/',
        RegistroApoderadoView.as_view(),
        name='registro-apoderado'
    ),

    path(
        'registro-delegado/',
        RegistroDelegadoView.as_view(),
        name='registro-delegado'
    ),

    path(
        'login/',
        LoginView.as_view(),
        name='login'
    ),

    path(
        'login-admin/',
        AdminLoginView.as_view(),
        name='login-admin'
    ),

    path(
        'password-reset/',
        SolicitarRecuperacionView.as_view(),
        name='solicitar-recuperacion'
    ),

    path(
        'password-reset/confirm/',
        ConfirmarRecuperacionView.as_view(),
        name='confirmar-recuperacion'
    ),

    path('cambiar-password/', CambiarPasswordView.as_view(), name='cambiar-password'),

    path('colegios-registro/', ColegiosRegistroView.as_view(), name='colegios-registro'),

    path('terminos/', TerminosVigentesView.as_view(), name='terminos-vigentes'),

    path('terminos/aceptar/', AceptarTerminosView.as_view(), name='terminos-aceptar'),

]
