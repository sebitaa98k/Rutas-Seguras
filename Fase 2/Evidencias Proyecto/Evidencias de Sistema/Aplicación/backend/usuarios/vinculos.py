"""Apoderados con hijos en varios colegios.

Un apoderado tiene una sola cuenta y puede estar vinculado a varios colegios. El vínculo es su RUT
habilitado (RutHabilitado) en cada colegio. El colegio "dueño" es `PerfilApoderado.colegio`: el primero
que lo registró. Solo el dueño (o el administrador de plataforma) edita su nombre, correo y teléfono, y
nadie más que el propio apoderado cambia su contraseña.

Cada colegio ve y administra solo lo suyo: si un colegio lo desactiva, se desvincula de ese colegio
(sus hijos ahí se desactivan) y la cuenta sigue activa mientras tenga otro colegio.
"""
from django.db import transaction
from django.utils import timezone

from .models import Colegio, Estudiante, PerfilApoderado, RutHabilitado
from .permissions import es_admin_plataforma


def colegios_del_apoderado(perfil):
    """Ids de los colegios activos a los que está vinculado el apoderado."""
    ids = set(
        RutHabilitado.objects.filter(apoderado=perfil, activo=True).values_list('colegio_id', flat=True)
    )
    ids |= set(Estudiante.objects.filter(apoderado=perfil).exclude(colegio__isnull=True).values_list('colegio_id', flat=True))
    if perfil.colegio_id:
        ids.add(perfil.colegio_id)
    return set(Colegio.objects.filter(id__in=ids, activo=True).values_list('id', flat=True))


def _cambiar_dueno(perfil, colegio_id):
    perfil.colegio_id = colegio_id
    perfil.save(update_fields=['colegio', 'updated_at'])
    usuario = perfil.usuario
    usuario.colegio_id = colegio_id
    usuario.save(update_fields=['colegio'])


def _notificar_vinculo(perfil, colegio):
    from .push_service import crear_y_despachar_notificacion_usuario

    crear_y_despachar_notificacion_usuario(
        perfil.usuario,
        'Nuevo colegio vinculado',
        f'El colegio {colegio.nombre} te vinculó como apoderado. Ya puedes ver y agregar a tus hijos de ese colegio.',
    )


def vincular_apoderado(perfil, colegio, creado_por=None, notificar=True):
    """
    Vincula una cuenta de apoderado existente a un colegio (habilita y usa su RUT en él).
    Devuelve True si el vínculo es nuevo. Si la cuenta no tenía colegio dueño, este pasa a serlo.
    """
    entrada = RutHabilitado.objects.select_for_update().filter(colegio=colegio, rut=perfil.rut).first()
    ya_vinculado = bool(entrada and entrada.apoderado_id == perfil.id and entrada.activo)
    if entrada is None:
        entrada = RutHabilitado(colegio=colegio, rut=perfil.rut, creado_por=creado_por)
    if not ya_vinculado:
        entrada.apoderado = perfil
        entrada.usado_en = entrada.usado_en or timezone.now()
        entrada.activo = True
        entrada.desactivado_en = None
        entrada.save()
    if perfil.colegio_id is None:
        _cambiar_dueno(perfil, colegio.id)
    elif not ya_vinculado and notificar and perfil.colegio_id != colegio.id:
        _notificar_vinculo(perfil, colegio)
    return not ya_vinculado


def habilitar_rut_apoderado(colegio, rut, creado_por=None):
    """
    Deja el RUT del apoderado habilitado en el colegio. Si ya tiene cuenta, la vincula.
    Devuelve (habilitado_ahora, cuenta_vinculada).
    """
    entrada = RutHabilitado.objects.filter(colegio=colegio, rut=rut).first()
    habilitado_ahora = entrada is None or not entrada.activo
    if entrada is None:
        entrada = RutHabilitado.objects.create(colegio=colegio, rut=rut, creado_por=creado_por)
    elif not entrada.activo:
        entrada.activo = True
        entrada.desactivado_en = None
        entrada.save(update_fields=['activo', 'desactivado_en'])
    perfil = PerfilApoderado.objects.filter(rut=rut, usuario__is_active=True).first()
    vinculada = False
    if perfil and entrada.apoderado_id != perfil.id:
        vinculada = vincular_apoderado(perfil, colegio, creado_por=creado_por)
    return habilitado_ahora, vinculada


def es_colegio_dueno(perfil, colegio_id):
    return bool(colegio_id) and perfil.colegio_id == int(colegio_id)


def puede_editar_apoderado(usuario, perfil):
    """Nombre, correo y teléfono los edita solo el colegio dueño (o el administrador de plataforma)."""
    if es_admin_plataforma(usuario):
        return True
    return usuario.rol == 'admin_colegio' and perfil.colegio_id == usuario.colegio_id


@transaction.atomic
def desvincular_apoderado(perfil, colegio):
    """
    Quita al apoderado de un colegio sin tocar su cuenta: sus hijos de ese colegio se desactivan y deja de
    aparecer ahí. Si ese colegio era el dueño, el rol pasa al colegio más antiguo de los que le quedan.
    Lanza PapeleraError si algo lo impide (por ejemplo, un hijo en un recorrido en curso).
    """
    from .papelera import PapeleraError, desactivar_estudiante

    otros = colegios_del_apoderado(perfil) - {colegio.id}
    if not otros:
        raise PapeleraError('El apoderado no está en otro colegio.')

    hijos = list(Estudiante.objects.filter(apoderado=perfil, colegio=colegio))
    for hijo in hijos:
        desactivar_estudiante(hijo)
    ahora = timezone.now()
    RutHabilitado.objects.filter(apoderado=perfil, colegio=colegio, activo=True).update(
        activo=False, desactivado_en=ahora,
    )

    mensaje = f'{perfil.usuario.get_full_name() or perfil.usuario.email} ya no está vinculado a {colegio.nombre}.'
    if hijos:
        mensaje += f' Se desactivaron sus hijos de este colegio ({", ".join(f"{h.nombre} {h.apellido}" for h in hijos)}).'
    if perfil.colegio_id == colegio.id:
        nuevo = (
            RutHabilitado.objects.filter(apoderado=perfil, activo=True, colegio_id__in=otros)
            .order_by('usado_en', 'id').values_list('colegio_id', flat=True).first()
        ) or min(otros)
        _cambiar_dueno(perfil, nuevo)
        mensaje += f' Ahora lo administra {Colegio.objects.get(pk=nuevo).nombre}.'
    mensaje += ' Su cuenta sigue activa en sus otros colegios. Puedes volver a vincularlo reactivando su RUT en la papelera.'
    return mensaje
