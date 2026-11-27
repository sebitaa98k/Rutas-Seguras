"""Planes de los colegios y su sede principal.

Todo colegio tiene una sede principal, creada junto con él y con sus mismos datos:
- Básico y Estándar: es la única sede y no se muestra en ninguna pantalla. Lo que se registra en el
  colegio (estudiantes, furgones, rutas, inspectores) queda en ella sin que nadie la elija.
- Avanzado (multisede): la sede principal se ve y se pueden crear más sedes.

El límite de estudiantes de cada plan todavía no se aplica.
"""
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from .models import Colegio, Estudiante, Furgon, Ruta, Sede

NOMBRE_SEDE_PRINCIPAL = 'Sede Principal'


def _datos_del_colegio(colegio):
    return {campo: getattr(colegio, campo) for campo in Sede.CAMPOS_DEL_COLEGIO}


def asegurar_sede_principal(colegio):
    """Devuelve la sede principal del colegio. Si no tiene, toma la más antigua o crea una nueva."""
    principal = colegio.sede_principal()
    if principal:
        return principal
    principal = colegio.sedes.order_by('created_at', 'id').first()
    if principal:
        principal.es_principal = True
        principal.save(update_fields=['es_principal', 'updated_at'])
    else:
        principal = Sede.objects.create(
            colegio=colegio, es_principal=True, nombre=NOMBRE_SEDE_PRINCIPAL,
            activa=colegio.activo, **_datos_del_colegio(colegio),
        )
    sincronizar_sede_principal(colegio)
    return principal


def sincronizar_sede_principal(colegio):
    """La sede principal mantiene siempre la dirección, ubicación y teléfono del colegio."""
    Sede.objects.filter(colegio=colegio, es_principal=True).update(**_datos_del_colegio(colegio))


def sede_del_registro(colegio, sede):
    """
    Sede con que se guarda un estudiante, furgón, ruta o inspector. Si el colegio no es multisede
    siempre es la principal, aunque la pantalla no la haya enviado.
    """
    if colegio is None or colegio.es_multisede:
        return sede
    return asegurar_sede_principal(colegio)


def asignar_principal_a_lo_sin_sede(colegio):
    """En un colegio de una sola sede, lo que aún no tiene sede queda en la principal."""
    principal = asegurar_sede_principal(colegio)
    for modelo in (Estudiante, Furgon, Ruta):
        modelo.todos.filter(colegio=colegio, sede__isnull=True).update(sede=principal)


def _desactivar_sede_con_todo(sede):
    """Desactiva la sede junto con sus rutas, estudiantes, furgones e inspectores. Devuelve los totales."""
    from .papelera import (
        desactivar_delegado, desactivar_estudiante, desactivar_furgon, desactivar_ruta, desactivar_sede,
    )

    rutas = list(Ruta.objects.filter(sede=sede))
    estudiantes = list(Estudiante.objects.filter(sede=sede))
    furgones = list(Furgon.objects.filter(sede=sede))
    inspectores = [
        relacion.delegado.usuario
        for relacion in sede.inspectores.filter(delegado__usuario__is_active=True).select_related('delegado__usuario')
    ]
    # Primero las rutas: así los furgones quedan libres y los estudiantes salen de ellas.
    for ruta in rutas:
        desactivar_ruta(ruta)
    for estudiante in estudiantes:
        # Conserva su rostro: el colegio puede traerlo de vuelta con "Mover al colegio".
        desactivar_estudiante(estudiante, borrar_biometria=False)
    for furgon in furgones:
        desactivar_furgon(furgon)
    for usuario in inspectores:
        desactivar_delegado(usuario)
    desactivar_sede(sede)
    return {
        'rutas': len(rutas), 'estudiantes': len(estudiantes),
        'furgones': len(furgones), 'inspectores': len(inspectores),
    }


def _revisar_recorridos_en_curso(sedes):
    """Un recorrido en curso no se interrumpe: si toca alguna de esas sedes, no se cambia el plan."""
    from .papelera import PapeleraError

    en_ruta = Ruta.objects.filter(estado='en_ruta').filter(
        Q(sede__in=sedes) | Q(estudiantes__sede__in=sedes)
    ).distinct()
    if en_ruta.exists():
        nombres = ', '.join(en_ruta.values_list('nombre', flat=True)[:3])
        raise PapeleraError(
            f'Hay recorridos en curso en las sedes que se desactivarían ({nombres}). '
            'Espera a que terminen para cambiar el plan.'
        )


@transaction.atomic
def cambiar_plan(colegio, nuevo_plan):
    """
    Cambia el plan del colegio. Si deja de ser multisede, solo se mantiene la sede principal: las demás
    se desactivan con todo lo que tienen (quedan en la papelera). Devuelve un mensaje para el panel.
    Si algo impide el cambio, lanza PapeleraError y no se cambia nada.
    """
    if nuevo_plan not in dict(Colegio.PLANES):
        raise ValueError('Plan no válido.')
    era_multisede = colegio.es_multisede
    colegio.plan = nuevo_plan
    colegio.save(update_fields=['plan', 'updated_at'])
    principal = asegurar_sede_principal(colegio)
    if colegio.es_multisede or not era_multisede:
        return ''

    otras = list(colegio.sedes.filter(activa=True).exclude(pk=principal.pk).order_by('nombre'))
    if not principal.activa:
        # La principal nunca queda desactivada mientras el colegio esté activo.
        principal.activa = True
        principal.desactivado_en = None
        principal.save(update_fields=['activa', 'desactivado_en', 'updated_at'])
    if not otras:
        asignar_principal_a_lo_sin_sede(colegio)
        return ''

    _revisar_recorridos_en_curso(otras)
    totales = {'rutas': 0, 'estudiantes': 0, 'furgones': 0, 'inspectores': 0}
    for sede in otras:
        for clave, cantidad in _desactivar_sede_con_todo(sede).items():
            totales[clave] += cantidad
    asignar_principal_a_lo_sin_sede(colegio)

    detalle = ', '.join(f'{cantidad} {clave}' for clave, cantidad in totales.items() if cantidad)
    nombres = ', '.join(sede.nombre for sede in otras)
    mensaje = f'Se mantuvo solo la sede principal. Se desactivaron las sedes {nombres}'
    mensaje += f' junto con {detalle}.' if detalle else '.'
    return mensaje + ' Puedes revisarlos en la papelera.'


def nombre_establecimiento(ruta, por_defecto='el colegio'):
    """Cómo se llama el destino de una ruta: su sede si se ve, si no el colegio."""
    if ruta.sede_id and not ruta.sede.oculta:
        return ruta.sede.nombre
    return ruta.colegio.nombre if ruta.colegio_id else por_defecto


class NombreSedeVisible(serializers.Field):
    """Nombre de la sede para mostrar. Vacío si la sede está oculta (colegio que no es multisede)."""

    def __init__(self, **kwargs):
        kwargs.setdefault('source', 'sede')
        kwargs['read_only'] = True
        super().__init__(**kwargs)

    def to_representation(self, sede):
        return '' if sede.oculta else sede.nombre
