"""Papelera: nada se borra de la base de datos. Se desactiva y se puede reactivar desde el panel.

Cada tipo define qué impide desactivarlo (por ejemplo, una sede con estudiantes activos) y qué
necesita para volver (por ejemplo, un estudiante necesita que su apoderado esté activo).
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from .asignaciones import sincronizar_conductor_de_estudiantes
from .models import Colegio, Estudiante, EstudianteHabilitado, FCMToken, Furgon, Ruta, RutHabilitado, Sede, Usuario


class PapeleraError(Exception):
    """El registro no se puede desactivar o reactivar todavía; el mensaje dice qué falta."""


def _lista(nombres, maximo=3):
    nombres = list(nombres)
    texto = ', '.join(nombres[:maximo])
    return texto + (f' y {len(nombres) - maximo} más' if len(nombres) > maximo else '')


def _nombre_usuario(usuario):
    return usuario.get_full_name() or usuario.email


def _desactivar_cuenta(usuario):
    usuario.is_active = False
    usuario.desactivado_en = timezone.now()
    usuario.save(update_fields=['is_active', 'desactivado_en'])
    # Cierra sus sesiones y deja de enviarle notificaciones.
    Token.objects.filter(user=usuario).delete()
    FCMToken.objects.filter(usuario=usuario).update(is_active=False)


def _reactivar_cuenta(usuario):
    if usuario.colegio_id and not usuario.colegio.activo:
        raise PapeleraError('Su colegio está desactivado: reactívalo primero.')
    usuario.is_active = True
    usuario.desactivado_en = None
    usuario.save(update_fields=['is_active', 'desactivado_en'])


def _quitar_de_las_rutas(estudiante):
    rutas = list(Ruta.objects.filter(estudiantes=estudiante))
    for ruta in rutas:
        ruta.estudiantes.remove(estudiante)
        ruta.estudiantes_count = ruta.estudiantes.count()
        ruta.save(update_fields=['estudiantes_count', 'updated_at'])
    sincronizar_conductor_de_estudiantes([estudiante.id])
    return rutas


# ---------------------------------------------------------------- desactivar

def desactivar_colegio(colegio):
    pendientes = []
    # La sede principal no cuenta: se desactiva y se reactiva junto con el colegio.
    if colegio.sedes.filter(activa=True, es_principal=False).exists():
        pendientes.append('sedes')
    if Estudiante.objects.filter(colegio=colegio).exists():
        pendientes.append('estudiantes')
    if Furgon.objects.filter(colegio=colegio).exists():
        pendientes.append('furgones')
    if Ruta.objects.filter(colegio=colegio).exists():
        pendientes.append('rutas')
    if colegio.usuarios.filter(is_active=True).exclude(rol='admin_colegio').exists():
        pendientes.append('cuentas de usuarios')
    if pendientes:
        raise PapeleraError(
            f'El colegio aún tiene {_lista(pendientes)} activos. Desactívalos antes de desactivar el colegio.'
        )
    colegio.activo = False
    colegio.desactivado_en = timezone.now()
    colegio.save(update_fields=['activo', 'desactivado_en', 'updated_at'])
    colegio.sedes.filter(es_principal=True).update(activa=False, desactivado_en=colegio.desactivado_en)
    # Sus administradores dejan de poder ingresar mientras el colegio esté desactivado.
    for admin in colegio.usuarios.filter(rol='admin_colegio', is_active=True):
        _desactivar_cuenta(admin)
    return f'El colegio "{colegio.nombre}" quedó desactivado. Puedes reactivarlo desde la papelera.'


def desactivar_sede(sede):
    if sede.es_principal:
        raise PapeleraError(
            'La sede principal no se puede desactivar: se desactiva junto con el colegio.'
        )
    pendientes = []
    estudiantes = Estudiante.objects.filter(sede=sede)
    if estudiantes.exists():
        pendientes.append(f'{estudiantes.count()} estudiante(s)')
    furgones = Furgon.objects.filter(sede=sede)
    if furgones.exists():
        pendientes.append(f'{furgones.count()} furgón(es)')
    rutas = Ruta.objects.filter(sede=sede)
    if rutas.exists():
        pendientes.append(f'{rutas.count()} ruta(s)')
    inspectores = sede.inspectores.filter(delegado__usuario__is_active=True)
    if inspectores.exists():
        pendientes.append(f'{inspectores.count()} inspector(es)')
    if pendientes:
        raise PapeleraError(
            f'La sede "{sede.nombre}" aún tiene {_lista(pendientes, 4)}. '
            'Muévelos a otra sede o desactívalos antes de desactivarla.'
        )
    sede.activa = False
    sede.desactivado_en = timezone.now()
    sede.save(update_fields=['activa', 'desactivado_en', 'updated_at'])
    return f'La sede "{sede.nombre}" quedó desactivada. Puedes reactivarla desde la papelera.'


def desactivar_estudiante(estudiante, borrar_biometria=True):
    """Lo saca del servicio. Su rostro se borra: no se guarda el de un menor que ya no lo usa.

    `borrar_biometria=False` solo al cerrar una sede por bajar de plan: es un cambio del colegio,
    no del estudiante, y puede volver con "Mover al colegio".
    """
    en_recorrido = Ruta.objects.filter(estudiantes=estudiante, estado='en_ruta')
    if en_recorrido.exists():
        raise PapeleraError('El estudiante va en una ruta en recorrido. Espera a que termine para desactivarlo.')
    rutas = _quitar_de_las_rutas(estudiante)
    estudiante.activo = False
    estudiante.desactivado_en = timezone.now()
    estudiante.save(update_fields=['activo', 'desactivado_en', 'updated_at'])
    mensaje = f'{estudiante.nombre} {estudiante.apellido} quedó desactivado.'
    if rutas:
        mensaje += f' Se quitó de {_lista(ruta.nombre for ruta in rutas)}.'
    if borrar_biometria:
        from .terminos import cambiar_biometria_estudiante, eliminar_biometria
        # Deja de usar el servicio: se suprimen sus datos faciales y su consentimiento queda revocado
        # (con constancia). Si vuelve, su apoderado debe autorizarlo de nuevo.
        if estudiante.autoriza_biometria:
            borrados = cambiar_biometria_estudiante(estudiante, False, origen='desactivacion')
        else:
            borrados = bool(eliminar_biometria([estudiante]))
        if borrados:
            mensaje += ' Se eliminaron su foto y sus datos faciales.'
    return mensaje + ' Puedes reactivarlo desde la papelera.'


def desactivar_furgon(furgon):
    rutas = Ruta.objects.filter(furgon=furgon)
    if rutas.exists():
        raise PapeleraError(
            f'El furgón está asignado a {_lista(ruta.nombre for ruta in rutas)}. '
            'Asigna otro furgón a esas rutas o desactívalas primero.'
        )
    furgon.activo = False
    furgon.desactivado_en = timezone.now()
    furgon.save(update_fields=['activo', 'desactivado_en', 'updated_at'])
    return f'El furgón {furgon.patente} quedó desactivado. Puedes reactivarlo desde la papelera.'


def desactivar_ruta(ruta):
    if ruta.estado == 'en_ruta':
        raise PapeleraError('No se puede desactivar una ruta en recorrido.')
    estudiante_ids = list(ruta.estudiantes.values_list('id', flat=True))
    ruta.activo = False
    ruta.simulacion_activa = False
    ruta.desactivado_en = timezone.now()
    ruta.save(update_fields=['activo', 'simulacion_activa', 'desactivado_en', 'updated_at'])
    sincronizar_conductor_de_estudiantes(estudiante_ids)
    return f'La ruta "{ruta.nombre}" quedó desactivada. Puedes reactivarla desde la papelera.'


def desactivar_conductor(usuario):
    rutas = Ruta.objects.filter(conductor_perfil__usuario=usuario)
    if rutas.exists():
        raise PapeleraError(
            f'El conductor tiene asignada(s) {_lista(ruta.nombre for ruta in rutas)}. '
            'Asigna otro conductor a esas rutas o desactívalas primero.'
        )
    _desactivar_cuenta(usuario)
    return f'La cuenta de {_nombre_usuario(usuario)} quedó desactivada: ya no puede ingresar.'


def desactivar_delegado(usuario):
    _desactivar_cuenta(usuario)
    return f'La cuenta de {_nombre_usuario(usuario)} quedó desactivada: ya no puede ingresar.'


def desactivar_apoderado(usuario):
    perfil = getattr(usuario, 'perfil_apoderado', None)
    hijos = Estudiante.objects.filter(apoderado=perfil) if perfil else Estudiante.objects.none()
    if hijos.exists():
        raise PapeleraError(
            f'El apoderado tiene estudiantes activos ({_lista(f"{e.nombre} {e.apellido}" for e in hijos)}). '
            'Desactívalos primero.'
        )
    _desactivar_cuenta(usuario)
    return f'La cuenta de {_nombre_usuario(usuario)} quedó desactivada: ya no puede ingresar.'


def desactivar_rut_habilitado(entrada):
    if entrada.apoderado_id:
        raise PapeleraError('Este RUT ya tiene una cuenta. Primero debes liberarlo.')
    entrada.activo = False
    entrada.desactivado_en = timezone.now()
    entrada.save(update_fields=['activo', 'desactivado_en'])
    return f'El RUT {entrada.rut} ya no está habilitado. Puedes reactivarlo desde la papelera.'


def desactivar_estudiante_habilitado(entrada):
    if entrada.estudiante_id:
        raise PapeleraError('Este estudiante ya fue inscrito por su apoderado: se administra desde Estudiantes.')
    entrada.activo = False
    entrada.desactivado_en = timezone.now()
    entrada.save(update_fields=['activo', 'desactivado_en'])
    return f'El estudiante {entrada.rut} ya no está habilitado. Puedes reactivarlo desde la papelera.'


# ---------------------------------------------------------------- reactivar

def _reactivar_colegio(colegio):
    colegio.activo = True
    colegio.desactivado_en = None
    colegio.save(update_fields=['activo', 'desactivado_en', 'updated_at'])
    colegio.sedes.filter(es_principal=True).update(activa=True, desactivado_en=None)
    for admin in colegio.usuarios.filter(rol='admin_colegio', is_active=False):
        _reactivar_cuenta(admin)


def _reactivar_sede(sede):
    if not sede.colegio.activo:
        raise PapeleraError('Su colegio está desactivado: reactívalo primero.')
    if not sede.colegio.es_multisede:
        raise PapeleraError(
            'Su colegio no tiene el plan Avanzado (multisede): cámbialo de plan para reactivar otras sedes.'
        )
    sede.activa = True
    sede.desactivado_en = None
    sede.save(update_fields=['activa', 'desactivado_en', 'updated_at'])


def _reactivar_estudiante(estudiante):
    if not estudiante.apoderado.usuario.is_active:
        raise PapeleraError('Su apoderado está desactivado: reactívalo primero.')
    if estudiante.colegio_id and not estudiante.colegio.activo:
        raise PapeleraError('Su colegio está desactivado: reactívalo primero.')
    if estudiante.sede_id and not estudiante.sede.activa:
        raise PapeleraError('Su sede está desactivada: reactívala primero.')
    estudiante.activo = True
    estudiante.desactivado_en = None
    estudiante.save(update_fields=['activo', 'desactivado_en', 'updated_at'])
    if estudiante.colegio_id:
        # Si su colegio había desvinculado al apoderado, vuelve a quedar vinculado.
        from .vinculos import vincular_apoderado
        vincular_apoderado(estudiante.apoderado, estudiante.colegio, notificar=False)


def _reactivar_furgon(furgon):
    if furgon.colegio_id and not furgon.colegio.activo:
        raise PapeleraError('Su colegio está desactivado: reactívalo primero.')
    if furgon.sede_id and not furgon.sede.activa:
        raise PapeleraError('Su sede está desactivada: reactívala primero.')
    furgon.activo = True
    furgon.desactivado_en = None
    furgon.save(update_fields=['activo', 'desactivado_en', 'updated_at'])


def _reactivar_ruta(ruta):
    if ruta.colegio_id and not ruta.colegio.activo:
        raise PapeleraError('Su colegio está desactivado: reactívalo primero.')
    if ruta.sede_id and not ruta.sede.activa:
        raise PapeleraError('Su sede está desactivada: reactívala primero.')
    if ruta.furgon_id and not ruta.furgon.activo:
        raise PapeleraError(f'Su furgón ({ruta.furgon.patente}) está desactivado: reactívalo o cambia el furgón.')
    if ruta.conductor_perfil_id and not ruta.conductor_perfil.usuario.is_active:
        raise PapeleraError('Su conductor está desactivado: reactívalo primero.')
    ruta.activo = True
    ruta.desactivado_en = None
    ruta.save(update_fields=['activo', 'desactivado_en', 'updated_at'])
    # Los estudiantes que siguen activos vuelven a quedar a cargo de su conductor.
    sincronizar_conductor_de_estudiantes(ruta.estudiantes.values_list('id', flat=True))


def _reactivar_estudiante_habilitado(entrada):
    if not entrada.colegio.activo:
        raise PapeleraError('Su colegio está desactivado: reactívalo primero.')
    otra = EstudianteHabilitado.objects.filter(rut=entrada.rut, activo=True).exclude(pk=entrada.pk).first()
    if otra:
        raise PapeleraError(f'Este estudiante ya está habilitado en {otra.colegio.nombre}.')
    if Estudiante.todos.filter(rut=entrada.rut).exists():
        raise PapeleraError('Este estudiante ya está inscrito: no necesita habilitación.')
    entrada.activo = True
    entrada.desactivado_en = None
    entrada.save(update_fields=['activo', 'desactivado_en'])


def _reactivar_rut(entrada):
    entrada.activo = True
    entrada.desactivado_en = None
    entrada.save(update_fields=['activo', 'desactivado_en'])


# ---------------------------------------------------------------- tipos

def _usuarios(rol):
    # Las cuentas liberadas para que otra persona use el RUT no vuelven: no están en la papelera.
    return Usuario.objects.filter(rol=rol, is_active=False).exclude(email__endswith='@cuenta-liberada.invalid')


TIPOS = {
    'colegio': {
        'titulo': 'Colegios',
        'papelera': lambda colegio_id: Colegio.objects.filter(activo=False),
        'buscar': lambda pk: Colegio.objects.get(pk=pk),
        'colegio_de': lambda obj: obj.id,
        'nombre': lambda obj: obj.nombre,
        'detalle': lambda obj: obj.comuna or '',
        'reactivar': _reactivar_colegio,
        'solo_plataforma': True,
    },
    'sede': {
        'titulo': 'Sedes',
        # La sede principal sigue al colegio, así que no aparece sola en la papelera.
        'papelera': lambda colegio_id: Sede.objects.filter(activa=False, es_principal=False),
        'buscar': lambda pk: Sede.objects.get(pk=pk),
        'colegio_de': lambda obj: obj.colegio_id,
        'nombre': lambda obj: obj.nombre,
        'detalle': lambda obj: obj.colegio.nombre,
        'reactivar': _reactivar_sede,
        # Crear, desactivar y reactivar sedes lo hace la plataforma; el colegio lo solicita por fuera.
        'solo_plataforma': True,
    },
    'estudiante': {
        'titulo': 'Estudiantes',
        'papelera': lambda colegio_id: Estudiante.todos.filter(activo=False),
        'buscar': lambda pk: Estudiante.todos.get(pk=pk),
        'colegio_de': lambda obj: obj.colegio_id,
        'nombre': lambda obj: f'{obj.nombre} {obj.apellido}',
        'detalle': lambda obj: f'RUT {obj.rut} · {obj.curso}',
        'reactivar': _reactivar_estudiante,
    },
    'apoderado': {
        'titulo': 'Apoderados',
        'papelera': lambda colegio_id: _usuarios('apoderado'),
        'buscar': lambda pk: Usuario.objects.get(pk=pk, rol='apoderado'),
        'rol': 'apoderado',
        'nombre': _nombre_usuario,
        'detalle': lambda obj: obj.email,
        'reactivar': _reactivar_cuenta,
    },
    'conductor': {
        'titulo': 'Conductores',
        'papelera': lambda colegio_id: _usuarios('conductor'),
        'buscar': lambda pk: Usuario.objects.get(pk=pk, rol='conductor'),
        'rol': 'conductor',
        'nombre': _nombre_usuario,
        'detalle': lambda obj: obj.email,
        'reactivar': _reactivar_cuenta,
    },
    'delegado': {
        'titulo': 'Delegados e inspectores',
        'papelera': lambda colegio_id: _usuarios('delegado'),
        'buscar': lambda pk: Usuario.objects.get(pk=pk, rol='delegado'),
        'rol': 'delegado',
        'nombre': _nombre_usuario,
        'detalle': lambda obj: obj.email,
        'reactivar': _reactivar_cuenta,
    },
    'furgon': {
        'titulo': 'Furgones',
        'papelera': lambda colegio_id: Furgon.todos.filter(activo=False),
        'buscar': lambda pk: Furgon.todos.get(pk=pk),
        'colegio_de': lambda obj: obj.colegio_id,
        'nombre': lambda obj: obj.patente,
        'detalle': lambda obj: obj.marca_modelo,
        'reactivar': _reactivar_furgon,
    },
    'ruta': {
        'titulo': 'Rutas',
        'papelera': lambda colegio_id: Ruta.todos.filter(activo=False),
        'buscar': lambda pk: Ruta.todos.get(pk=pk),
        'colegio_de': lambda obj: obj.colegio_id,
        'nombre': lambda obj: obj.nombre,
        'detalle': lambda obj: 'Ida' if obj.sentido == 'hacia_colegio' else 'Vuelta',
        'reactivar': _reactivar_ruta,
    },
    'estudiante_habilitado': {
        'titulo': 'Estudiantes habilitados',
        'papelera': lambda colegio_id: EstudianteHabilitado.objects.filter(activo=False),
        'buscar': lambda pk: EstudianteHabilitado.objects.get(pk=pk),
        'colegio_de': lambda obj: obj.colegio_id,
        'nombre': lambda obj: obj.rut,
        'detalle': lambda obj: f'Apoderado {obj.rut_apoderado} · {obj.colegio.nombre}',
        'reactivar': _reactivar_estudiante_habilitado,
    },
    'rut_habilitado': {
        'titulo': 'RUT habilitados',
        'papelera': lambda colegio_id: RutHabilitado.objects.filter(activo=False),
        'buscar': lambda pk: RutHabilitado.objects.get(pk=pk),
        'colegio_de': lambda obj: obj.colegio_id,
        'nombre': lambda obj: obj.rut,
        'detalle': lambda obj: obj.colegio.nombre,
        'reactivar': _reactivar_rut,
    },
}

CAMPO_COLEGIO = {'colegio': 'id', 'sede': 'colegio_id'}


def _del_colegio(tipo, cfg, queryset, colegio_id):
    if not colegio_id:
        return queryset
    if 'rol' in cfg:
        from .view_common import queryset_usuarios_por_colegio
        return queryset_usuarios_por_colegio(queryset, colegio_id, cfg['rol'])
    return queryset.filter(**{CAMPO_COLEGIO.get(tipo, 'colegio_id'): colegio_id})


def contenido_papelera(colegio_id=None, admin_plataforma=False):
    """Lo desactivado, agrupado por tipo. Con colegio_id, solo lo de ese colegio."""
    grupos = []
    for tipo, cfg in TIPOS.items():
        if cfg.get('solo_plataforma') and not admin_plataforma:
            continue
        queryset = _del_colegio(tipo, cfg, cfg['papelera'](colegio_id), colegio_id)
        items = [
            {
                'id': obj.pk,
                'tipo': tipo,
                'nombre': cfg['nombre'](obj),
                'detalle': cfg['detalle'](obj),
                'desactivado_en': obj.desactivado_en.isoformat() if obj.desactivado_en else None,
                # Quedó en una sede cerrada al bajar de plan: se mueve al colegio en vez de reactivarse.
                'puede_mover': _quedo_en_sede_cerrada_por_plan(tipo, obj),
            }
            for obj in queryset.order_by('-desactivado_en', '-pk')
        ]
        grupos.append({'tipo': tipo, 'titulo': cfg['titulo'], 'items': items})
    return grupos


@transaction.atomic
def reactivar(tipo, pk, colegio_id=None, admin_plataforma=False):
    cfg = TIPOS.get(tipo)
    if not cfg or (cfg.get('solo_plataforma') and not admin_plataforma):
        raise LookupError
    try:
        obj = cfg['buscar'](pk)
    except Exception as exc:
        raise LookupError from exc
    if colegio_id and not _del_colegio(tipo, cfg, type(obj)._base_manager.filter(pk=obj.pk), colegio_id).exists():
        raise LookupError
    if _quedo_en_sede_cerrada_por_plan(tipo, obj):
        # Su sede se cerró al bajar de plan: no puede volver a ella (un inspector quedaría en una sede cerrada).
        raise PapeleraError('Su sede se cerró al cambiar el plan del colegio. Usa "Mover al colegio".')
    cfg['reactivar'](obj)
    return f'"{cfg["nombre"](obj)}" se reactivó.'


MENSAJE_CON_HISTORIAL = (
    'No se puede eliminar definitivamente porque tiene historial de recorridos (subidas o entregas registradas). '
    'Ese historial es la evidencia de Auditoría y Reportes, así que queda en la papelera.'
)


def _en_papelera(tipo, cfg, pk, colegio_id):
    """El registro debe estar desactivado y ser del colegio de quien lo pide."""
    try:
        obj = cfg['buscar'](pk)
    except Exception as exc:
        raise LookupError from exc
    queryset = _del_colegio(tipo, cfg, cfg['papelera'](colegio_id), colegio_id)
    if not queryset.filter(pk=obj.pk).exists():
        raise LookupError
    return obj


def eliminar_definitivo(tipo, pk, colegio_id=None, admin_plataforma=False):
    """Borra de verdad algo que está en la papelera. No se puede deshacer."""
    from django.db.models import ProtectedError

    cfg = TIPOS.get(tipo)
    if not cfg or (cfg.get('solo_plataforma') and not admin_plataforma):
        raise LookupError
    obj = _en_papelera(tipo, cfg, pk, colegio_id)
    nombre = cfg['nombre'](obj)
    foto = getattr(obj, 'foto', None) if tipo == 'estudiante' else None
    try:
        with transaction.atomic():
            obj.delete()
    except ProtectedError as exc:
        modelos = {type(bloqueo).__name__ for bloqueo in exc.protected_objects}
        if modelos & {'RegistroAbordaje', 'RegistroEntrega'}:
            raise PapeleraError(MENSAJE_CON_HISTORIAL) from exc
        raise PapeleraError(
            'No se puede eliminar definitivamente porque otros registros dependen de él '
            '(por ejemplo, inspectores de esta sede). Elimina o mueve esos registros primero.'
        ) from exc
    # La foto (cifrada) también se borra del disco: no debe quedar la imagen de un menor sin registro.
    if foto:
        foto.storage.delete(foto.name)
    return f'"{nombre}" se eliminó definitivamente.'


# ---------------------------------------------------------------- mover al colegio
#
# Al bajar un colegio de Avanzado (multisede) a Básico o Estándar, sus otras sedes se desactivan con
# todo lo que tienen. Eso no se junta solo en la sede principal, porque cada plan tendrá un límite de
# estudiantes: el administrador decide, uno por uno, qué vuelve al colegio con "Mover al colegio".
# No hace falta un campo nuevo: se reconoce porque su sede quedó cerrada y el colegio ya no es multisede.

TIPOS_MOVIBLES = ('estudiante', 'furgon', 'ruta', 'delegado')


def _sede_de(tipo, obj):
    """Sede a la que pertenece el registro (para un inspector, la sede que tenía a cargo)."""
    if tipo == 'delegado':
        from .models import DelegadoSede
        relacion = DelegadoSede.objects.filter(delegado__usuario=obj).select_related('sede__colegio').first()
        return relacion.sede if relacion else None
    return obj.sede if getattr(obj, 'sede_id', None) else None


def _quedo_en_sede_cerrada_por_plan(tipo, obj):
    """Desactivado en una sede que se cerró porque el colegio dejó de ser multisede."""
    if tipo not in TIPOS_MOVIBLES:
        return False
    sede = _sede_de(tipo, obj)
    return bool(sede and not sede.activa and not sede.es_principal and not sede.colegio.es_multisede)


def _revisar_limite_del_plan(colegio, tipo):
    """
    Lugar para el límite de estudiantes de cada plan (Básico hasta 150, Estándar hasta 500).
    Todavía no se aplica: cuando se defina, aquí se lanzará PapeleraError si el colegio ya está lleno.
    """
    return None


def _mover_estudiante(estudiante, principal):
    if not estudiante.apoderado.usuario.is_active:
        raise PapeleraError('Su apoderado está desactivado: reactívalo primero.')
    # Al bajar de plan su ruta se desactivó antes que él, así que sigue dentro de ella: se saca de todas
    # (también de las desactivadas) para que no reaparezca en una ruta de la sede cerrada.
    # Se borra en la tabla intermedia: `ruta.estudiantes.remove()` filtra con el manager de solo activos
    # y no encuentra a un estudiante desactivado, así que no lo sacaba.
    rutas = list(Ruta.todos.filter(estudiantes=estudiante))
    Ruta.estudiantes.through.objects.filter(estudiante_id=estudiante.id).delete()
    for ruta in rutas:
        ruta.estudiantes_count = Ruta.estudiantes.through.objects.filter(ruta_id=ruta.id).count()
        ruta.save(update_fields=['estudiantes_count', 'updated_at'])
    estudiante.sede = principal
    estudiante.activo = True
    estudiante.desactivado_en = None
    estudiante.save(update_fields=['sede', 'activo', 'desactivado_en', 'updated_at'])
    # Si su colegio había desvinculado al apoderado, vuelve a quedar vinculado.
    from .vinculos import vincular_apoderado
    vincular_apoderado(estudiante.apoderado, principal.colegio, notificar=False)
    return 'Quedó activo y sin ruta: agrégalo a una ruta para que use el servicio.'


def _mover_furgon(furgon, principal):
    furgon.sede = principal
    furgon.activo = True
    furgon.desactivado_en = None
    furgon.save(update_fields=['sede', 'activo', 'desactivado_en', 'updated_at'])
    return 'Quedó activo y sin ruta: asígnalo al crear o editar una ruta.'


def _mover_ruta(ruta, principal):
    """La ruta vuelve vacía: sus estudiantes se mueven aparte, para no pasarse del límite del plan."""
    avisos = []
    campos = ['sede', 'activo', 'desactivado_en', 'estudiantes_count', 'updated_at']
    if ruta.furgon_id and not ruta.furgon.activo:
        avisos.append(f'su furgón {ruta.furgon.patente} sigue desactivado, así que quedó sin furgón')
        ruta.furgon = None
        campos.append('furgon')
    if ruta.conductor_perfil_id and not ruta.conductor_perfil.usuario.is_active:
        avisos.append('su conductor está desactivado, así que quedó sin conductor')
        ruta.conductor_perfil = None
        campos.append('conductor_perfil')
    # En la tabla intermedia: `clear()` no saca a los estudiantes desactivados (ver _mover_estudiante).
    Ruta.estudiantes.through.objects.filter(ruta_id=ruta.id).delete()
    ruta.sede = principal
    ruta.estudiantes_count = 0
    ruta.activo = True
    ruta.desactivado_en = None
    ruta.save(update_fields=campos)
    mensaje = 'Quedó activa y sin estudiantes: mueve primero a los que correspondan y agrégalos a la ruta.'
    if avisos:
        mensaje += ' Ojo: ' + '; '.join(avisos) + '. Sin furgón y conductor no se puede iniciar.'
    return mensaje


def _mover_inspector(usuario, principal):
    from .models import DelegadoSede
    DelegadoSede.objects.filter(delegado__usuario=usuario).update(sede=principal, activo=True)
    usuario.is_active = True
    usuario.desactivado_en = None
    usuario.save(update_fields=['is_active', 'desactivado_en'])
    return 'Su cuenta quedó activa y vuelve a recibir a los estudiantes del colegio.'


MOVER = {
    'estudiante': _mover_estudiante,
    'furgon': _mover_furgon,
    'ruta': _mover_ruta,
    'delegado': _mover_inspector,
}


@transaction.atomic
def mover_al_colegio(tipo, pk, colegio_id=None, admin_plataforma=False):
    """
    Reactiva en la sede principal algo que quedó en una sede cerrada al bajar de plan.
    El colegio debe estar activo (si no pagó y está desactivado, todo espera en la papelera).
    """
    from .planes import asegurar_sede_principal

    cfg = TIPOS.get(tipo)
    if tipo not in MOVER or not cfg:
        raise LookupError
    obj = _en_papelera(tipo, cfg, pk, colegio_id)
    if not _quedo_en_sede_cerrada_por_plan(tipo, obj):
        raise PapeleraError(
            'Solo se mueve al colegio lo que quedó en una sede cerrada al cambiar de plan. Usa "Reactivar".'
        )
    colegio = _sede_de(tipo, obj).colegio
    if not colegio.activo:
        raise PapeleraError('Primero reactiva el colegio.')
    if tipo == 'estudiante':
        _revisar_limite_del_plan(colegio, tipo)
    principal = asegurar_sede_principal(colegio)
    detalle = MOVER[tipo](obj, principal)
    return f'"{cfg["nombre"](obj)}" quedó en {colegio.nombre}. {detalle}'
