"""Funciones que comparten las vistas de la operación de la ruta."""



def obtener_conductor_autenticado(request):
    if request.user.rol != 'conductor':
        return None
    return getattr(request.user, 'perfil_conductor', None)
