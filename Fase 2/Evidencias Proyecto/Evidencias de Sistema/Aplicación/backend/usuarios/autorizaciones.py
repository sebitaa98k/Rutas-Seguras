def normalizar_rut(rut):
    return (rut or '').replace('.', '').replace('-', '').upper().strip()


def sede_del_inspector(perfil):
    """La sede de un inspector (siempre tiene una). None si es una cuenta antigua sin sede."""
    relacion = perfil.sedes_responsable.filter(activo=True).select_related('sede').first()
    return relacion.sede if relacion else None


def inspector_atiende(perfil, estudiante):
    """
    Un inspector recibe a los estudiantes de su sede. Los estudiantes de su colegio que no tienen
    sede registrada también, para que nadie quede sin quien lo reciba.
    """
    if perfil.tipo_delegado != 'inspector':
        return False
    sede = sede_del_inspector(perfil)
    if not sede or sede.colegio_id != estudiante.colegio_id:
        return False
    return estudiante.sede_id in (sede.id, None)


def estudiantes_del_inspector(perfil):
    from django.db.models import Q
    from .models import Estudiante
    sede = sede_del_inspector(perfil)
    if not sede:
        return Estudiante.objects.none()
    return Estudiante.objects.filter(colegio_id=sede.colegio_id).filter(Q(sede_id=sede.id) | Q(sede__isnull=True))


def autorizado_para_estudiante(estudiante, perfil):
    from .models import PerfilApoderado, PerfilDelegado, PersonaAutorizada

    if isinstance(perfil, PerfilApoderado):
        if estudiante.apoderado_id == perfil.id:
            return {'tipo': 'apoderado', 'nombre': perfil.usuario.get_full_name() or perfil.usuario.email,
                    'rut': perfil.rut or '', 'perfil': perfil, 'autorizacion': None}
        return None
    if not isinstance(perfil, PerfilDelegado):
        return None
    nombre = perfil.usuario.get_full_name() or perfil.usuario.email
    if perfil.tipo_delegado == 'inspector':
        if not inspector_atiende(perfil, estudiante):
            return None
        return {'tipo': 'delegado_institucional', 'nombre': nombre, 'rut': perfil.rut or '',
                'perfil': perfil, 'autorizacion': None}
    autorizacion = PersonaAutorizada.objects.filter(
        estudiante=estudiante, apoderado=estudiante.apoderado, colegio_id=estudiante.colegio_id,
        activa=True,
    ).filter(rut=perfil.rut).first()
    if not autorizacion:
        rut = normalizar_rut(perfil.rut)
        autorizacion = next((item for item in estudiante.personas_autorizadas.filter(activa=True)
                             if normalizar_rut(item.rut) == rut), None)
    if not autorizacion and normalizar_rut(estudiante.rut_persona_autorizada) == normalizar_rut(perfil.rut):
        autorizacion, _ = PersonaAutorizada.objects.get_or_create(
            estudiante=estudiante,
            rut=estudiante.rut_persona_autorizada,
            defaults={
                'apoderado': estudiante.apoderado, 'colegio': estudiante.colegio,
                'perfil_delegado': perfil,
                'nombre': estudiante.persona_autorizada or nombre,
            },
        )
    if not autorizacion:
        return None
    if autorizacion.perfil_delegado_id != perfil.id:
        autorizacion.perfil_delegado = perfil
        autorizacion.save(update_fields=['perfil_delegado', 'updated_at'])
    return {'tipo': 'persona_autorizada', 'nombre': autorizacion.nombre or nombre,
            'rut': autorizacion.rut, 'perfil': perfil, 'autorizacion': autorizacion}


def ruts_inspectores():
    from .models import PerfilDelegado
    return {
        normalizar_rut(rut)
        for rut in PerfilDelegado.objects.filter(tipo_delegado='inspector').values_list('rut', flat=True)
    }


def contactos_para_llamar(estudiante):
    """Apoderado y personas autorizadas con su teléfono. Un inspector no es un contacto de la familia."""
    from .models import PerfilDelegado
    contactos = []
    apoderado = estudiante.apoderado
    if apoderado:
        contactos.append({
            'id': 'apoderado', 'rol': 'Apoderado',
            'nombre': apoderado.usuario.get_full_name() or apoderado.usuario.email,
            'telefono': apoderado.telefono or '',
        })
    inspectores = ruts_inspectores()
    delegados = {normalizar_rut(perfil.rut): perfil for perfil in PerfilDelegado.objects.all()}
    for persona in estudiante.personas_autorizadas.filter(activa=True):
        rut = normalizar_rut(persona.rut)
        if rut in inspectores:
            continue
        # El vínculo al perfil puede faltar: el teléfono también se busca por RUT.
        perfil = persona.perfil_delegado or delegados.get(rut)
        contactos.append({
            'id': f'autorizada-{persona.id}', 'rol': 'Persona autorizada', 'nombre': persona.nombre,
            'telefono': persona.telefono or (perfil.telefono if perfil else '') or '',
        })
    return contactos


def personas_autorizadas_a_mostrar(estudiante):
    """Quienes pueden retirar al estudiante además de su apoderado. Un inspector nunca es uno de ellos."""
    inspectores = ruts_inspectores()
    personas = []
    vistos = set()
    registros = [(item.nombre, item.rut) for item in estudiante.personas_autorizadas.filter(activa=True)]
    registros.append((estudiante.persona_autorizada, estudiante.rut_persona_autorizada))
    for nombre, rut in registros:
        rut_normalizado = normalizar_rut(rut)
        if nombre and rut_normalizado not in inspectores and rut_normalizado not in vistos:
            personas.append({'nombre': nombre, 'rut': rut or ''})
            vistos.add(rut_normalizado)
    return personas


def inspectores_de(estudiante):
    """Nombres de los inspectores de la sede del estudiante."""
    from .models import PerfilDelegado
    inspectores = PerfilDelegado.objects.filter(
        tipo_delegado='inspector', sedes_responsable__sede__colegio_id=estudiante.colegio_id,
    ).select_related('usuario').distinct()
    return [
        perfil.usuario.get_full_name() or perfil.usuario.email
        for perfil in inspectores if inspector_atiende(perfil, estudiante)
    ]


def estudiantes_autorizados_de(perfil):
    """Estudiantes de una persona autorizada; se compara por RUT porque el vínculo al perfil puede faltar."""
    from .models import Estudiante, PersonaAutorizada
    rut = normalizar_rut(perfil.rut)
    ids = {
        item.estudiante_id for item in PersonaAutorizada.objects.filter(activa=True)
        if item.perfil_delegado_id == perfil.id or (rut and normalizar_rut(item.rut) == rut)
    }
    if rut:
        ids |= {
            estudiante.id for estudiante in Estudiante.objects.exclude(rut_persona_autorizada__isnull=True)
            if normalizar_rut(estudiante.rut_persona_autorizada) == rut
        }
    return Estudiante.objects.filter(id__in=ids)


def perfiles_receptores_autorizados(estudiante):
    from .models import PerfilDelegado
    perfiles = []
    vistos = set()
    for autorizado in estudiante.personas_autorizadas.filter(activa=True).select_related('perfil_delegado'):
        perfil = autorizado.perfil_delegado
        if perfil and perfil.id not in vistos:
            perfiles.append(perfil); vistos.add(perfil.id)
    rut_legacy = normalizar_rut(estudiante.rut_persona_autorizada)
    if rut_legacy:
        for perfil in PerfilDelegado.objects.filter(tipo_delegado='autorizado'):
            if normalizar_rut(perfil.rut) == rut_legacy and perfil.id not in vistos:
                perfiles.append(perfil); vistos.add(perfil.id)
    inspectores = PerfilDelegado.objects.filter(
        tipo_delegado='inspector', sedes_responsable__sede__colegio_id=estudiante.colegio_id,
    ).distinct()
    for perfil in inspectores:
        if inspector_atiende(perfil, estudiante) and perfil.id not in vistos:
            perfiles.append(perfil); vistos.add(perfil.id)
    return perfiles


def notificar_actualizacion_autorizados(estudiante):
    from .models import Ruta
    from .push_service import crear_y_despachar_notificacion_usuario
    rutas = Ruta.objects.filter(
        estudiantes=estudiante, estado__in=('activa', 'en_ruta'),
        colegio_id=estudiante.colegio_id,
        conductor_perfil__isnull=False,
    ).select_related('conductor_perfil__usuario').distinct()
    for ruta in rutas:
        crear_y_despachar_notificacion_usuario(
            ruta.conductor_perfil.usuario,
            'Personas autorizadas actualizadas',
            f'Se actualizó la información de recepción de {estudiante.nombre} {estudiante.apellido} para la ruta {ruta.nombre}.',
            estudiante=estudiante,
        )
