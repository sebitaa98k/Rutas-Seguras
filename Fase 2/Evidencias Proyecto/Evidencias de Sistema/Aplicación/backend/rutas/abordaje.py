"""Abordaje de estudiantes durante el recorrido de ida (domicilio -> colegio).

En la ida, cada estudiante es una parada en orden. Cuando un estudiante sube
(verificado por rostro o QR) su parada queda completada automáticamente y el
conductor pasa al siguiente. Si sube alguien distinto al esperado, se acepta
igual, se saca su parada del recorrido y se avisa a su apoderado que subió
fuera de su domicilio.
"""
from datetime import timedelta

from django.db import transaction

from usuarios.planes import nombre_establecimiento
from usuarios.inasistencias import anular_por_abordaje, ids_no_asisten
from django.utils import timezone
from usuarios.autorizaciones import autorizado_para_estudiante, contactos_para_llamar
from usuarios.models import RegistroAbordaje, RegistroEntrega, Ruta
from usuarios.optimizacion_rutas import estudiantes_en_orden
from usuarios.push_service import crear_y_despachar_notificacion, notificar_receptores_del_estudiante

from .auditoria import ROLES_DELEGADO, ROLES_RECEPTOR, registrar_evento, registrar_salida_vuelta
from .ubicacion import (
    lugar_de_entrega,
    lugar_de_subida,
    punto_de_la_casa,
    unir_detalle,
    verificar_en_el_punto,
)

METODOS = {
    'facial': 'reconocimiento facial',
    'qr': 'código QR',
    'validacion_institucional': 'validación institucional',
}


def nombre_estudiante(estudiante):
    return f'{estudiante.nombre} {estudiante.apellido}'.strip()


def es_recorrido_de_ida(ruta):
    return ruta.sentido == 'hacia_colegio' and ruta.estado == 'en_ruta'


def ruta_en_curso_del_estudiante(conductor_perfil, estudiante):
    return Ruta.objects.filter(
        conductor_perfil=conductor_perfil,
        estudiantes=estudiante,
        estado__in=('activa', 'en_ruta'),
    ).order_by('id').first()


def ruta_iniciada_del_estudiante(conductor_perfil, estudiante):
    return Ruta.objects.filter(
        conductor_perfil=conductor_perfil,
        estudiantes=estudiante,
        estado='en_ruta',
    ).order_by('id').first()


def destino_entrega(ruta, estudiante):
    if ruta.sentido == 'hacia_colegio':
        establecimiento = ruta.sede if ruta.sede_id else ruta.colegio
        if establecimiento:
            return establecimiento.direccion_completa or establecimiento.nombre
        return ruta.destino_direccion or ruta.nombre
    if ruta.estudiantes_no_recibidos.filter(pk=estudiante.pk).exists():
        establecimiento = ruta.sede if ruta.sede_id else ruta.colegio
        if establecimiento:
            return establecimiento.direccion_completa or establecimiento.nombre
    return estudiante.direccion_completa or ruta.destino_direccion or ruta.nombre


def registrar_entrega(ruta, estudiante, receptor, metodo):
    """
    Autoriza, persiste y notifica una entrega por cualquier método. Sin `receptor`, la
    entrega se valida con el rostro del estudiante: no se identifica a quien lo recibe.
    """
    if receptor is None:
        autorizado = {
            'tipo': 'domicilio', 'nombre': 'Domicilio', 'rut': '', 'perfil': None, 'autorizacion': None,
        }
    else:
        autorizado = autorizado_para_estudiante(estudiante, receptor)
        if not autorizado:
            raise ValueError('La persona no está autorizada para recibir a este estudiante.')
    with transaction.atomic():
        ruta = Ruta.objects.select_for_update().select_related('colegio', 'sede', 'conductor_perfil').get(pk=ruta.pk)
        if ruta.estado != 'en_ruta':
            raise ValueError('La ruta no se encuentra en recorrido.')
        if ruta.sentido == 'desde_colegio' and not ruta.reparto_iniciado_en:
            raise ValueError('Primero debes iniciar el reparto.')
        if not ruta.estudiantes.filter(pk=estudiante.pk).exists():
            raise ValueError('El estudiante no pertenece a la ruta activa del conductor.')
        if not ruta.estudiantes_abordados.filter(pk=estudiante.pk).exists():
            raise ValueError('No se puede entregar un estudiante que no haya abordado.')
        if ruta.estudiantes_entregados.filter(pk=estudiante.pk).exists():
            raise ValueError('El estudiante ya fue entregado.')
        if ruta.sentido == 'desde_colegio':
            if autorizado['tipo'] != 'delegado_institucional':
                ordenar_entrega_vuelta(ruta, [estudiante.id])
            elif not ruta.estudiantes_no_recibidos.filter(pk=estudiante.pk).exists():
                raise ValueError('El inspector solo recibe a quienes vuelven al colegio.')
        nota_ubicacion = verificar_en_el_punto(
            ruta, lugar_de_entrega(ruta, estudiante, autorizado['tipo'] == 'delegado_institucional'),
        )

        ruta.estudiantes_entregados.add(estudiante)
        ruta.paradas_completadas.add(estudiante)
        if ruta.origen_recalculo_latitud is not None:
            # Desde esta entrega, el orden vuelve a partir de la última casa.
            ruta.origen_recalculo_latitud = ruta.origen_recalculo_longitud = None
            ruta.save(update_fields=['origen_recalculo_latitud', 'origen_recalculo_longitud', 'updated_at'])

        destino = destino_entrega(ruta, estudiante)
        registro = RegistroEntrega.objects.create(
            estudiante=estudiante,
            conductor=ruta.conductor_perfil,
            ruta=ruta,
            colegio=ruta.colegio,
            persona_autorizada=autorizado['autorizacion'],
            perfil_delegado=autorizado['perfil'] if autorizado['tipo'] != 'apoderado' else None,
            tipo_receptor=autorizado['tipo'],
            receptor_nombre=autorizado['nombre'],
            receptor_rut=autorizado['rut'],
            metodo_validacion=metodo,
            destino=destino,
        )
        registrar_evento(
            ruta, 'entrega', estudiante,
            metodo=registro.get_metodo_validacion_display(),
            persona_nombre=registro.receptor_nombre,
            persona_rol=ROLES_RECEPTOR.get(registro.tipo_receptor, ''),
            persona_rut=registro.receptor_rut,
            detalle=unir_detalle(f'Destino: {destino}', nota_ubicacion),
        )

    hora = timezone.localtime(registro.entregado_en).strftime('%H:%M')
    verbo = 'fue recibido por el delegado' if autorizado['tipo'] == 'delegado_institucional' else 'fue entregado a'
    mensaje = f"{nombre_estudiante(estudiante)} {verbo} {registro.receptor_nombre} en {destino} a las {hora}."
    if receptor is None:
        mensaje = f"{nombre_estudiante(estudiante)} fue entregado en {destino} a las {hora} (verificado con su rostro)."
    notificacion = crear_y_despachar_notificacion(
        apoderado=estudiante.apoderado,
        titulo='Estudiante entregado',
        mensaje=mensaje,
        tipo='estudiante_llego',
        estudiante=estudiante,
        ruta=ruta,
        excluir_delegado=registro.perfil_delegado,
    )

    return {
        'estudiante_id': estudiante.id,
        'estudiante_nombre': nombre_estudiante(estudiante),
        'mensaje': mensaje,
        'estado': 'entregado',
        'entregado': True,
        'registro_entrega_id': registro.id,
        'receptor': registro.receptor_nombre,
        'tipo_receptor': registro.tipo_receptor,
        'metodo_validacion': registro.metodo_validacion,
        'destino': registro.destino,
        'notificacion': notificacion,
    }


def paradas_pendientes(ruta):
    """
    Estudiantes que aún no suben, en el mismo orden óptimo en que se muestran las paradas.
    Quienes tienen aviso de inasistencia del apoderado no son parte del recorrido.
    """
    completadas = set(ruta.paradas_completadas.values_list('id', flat=True))
    no_asisten = ids_no_asisten(ruta)
    return [
        estudiante for estudiante in estudiantes_en_orden(ruta)
        if estudiante.id not in completadas and estudiante.id not in no_asisten
    ]


def cola_de_entrega(ruta):
    """Niños a bordo por entregar en su casa, en el orden obligatorio del reparto."""
    abordados = set(ruta.estudiantes_abordados.values_list('id', flat=True))
    no_recibidos = set(ruta.estudiantes_no_recibidos.values_list('id', flat=True))
    return [e for e in paradas_pendientes(ruta) if e.id in abordados and e.id not in no_recibidos]


def ordenar_entrega_vuelta(ruta, estudiante_ids):
    """Valida que sean los siguientes del reparto y los devuelve en el orden a entregar."""
    if ruta.estudiantes_no_recibidos.filter(id__in=estudiante_ids).exists():
        raise ValueError('Este estudiante vuelve al colegio. Si el apoderado ya está, marca "Apoderado disponible".')
    cola = cola_de_entrega(ruta)
    siguientes = cola[:len(estudiante_ids)]
    if {e.id for e in siguientes} != set(estudiante_ids):
        raise ValueError(
            f'Primero corresponde entregar a {nombre_estudiante(cola[0])}.' if cola
            else 'No hay estudiantes por entregar.'
        )
    return [e.id for e in siguientes]


def faltan_paradas_antes_del_colegio(ruta):
    if ruta.sentido == 'desde_colegio':
        return cola_de_entrega(ruta)
    return paradas_pendientes(ruta)


def _exigir_reparto_en_curso(ruta):
    if ruta.estado != 'en_ruta' or ruta.sentido != 'desde_colegio' or not ruta.reparto_iniciado_en:
        raise ValueError('Esta acción solo está disponible durante el reparto.')


def registrar_llamada(ruta, estudiante, contacto_id):
    """Deja constancia de la llamada. Solo la hecha en su turno habilita "No se recibió"."""
    contacto = next((c for c in contactos_para_llamar(estudiante) if c['id'] == contacto_id), None)
    if not contacto:
        raise ValueError('El contacto no corresponde a este estudiante.')
    with transaction.atomic():
        ruta = Ruta.objects.select_for_update().get(pk=ruta.pk)
        _exigir_reparto_en_curso(ruta)
        cola = cola_de_entrega(ruta)
        en_su_turno = bool(cola) and cola[0].id == estudiante.id
        if en_su_turno:
            ruta.estudiantes_llamados.add(estudiante)
        registrar_evento(
            ruta, 'llamada', estudiante,
            persona_nombre=contacto['nombre'],
            persona_rol=contacto['rol'],
            detalle='Al llegar a su casa.' if en_su_turno else 'Fuera de su turno de entrega.',
        )
    return {'habilita_no_recibido': en_su_turno}


def marcar_no_recibido(ruta, estudiante):
    """Nadie recibió al niño: sigue a bordo y vuelve al colegio al final del recorrido."""
    nombre = nombre_estudiante(estudiante)
    with transaction.atomic():
        ruta = Ruta.objects.select_for_update().select_related('colegio', 'sede').get(pk=ruta.pk)
        _exigir_reparto_en_curso(ruta)
        cola = cola_de_entrega(ruta)
        if not cola or cola[0].id != estudiante.id:
            raise ValueError('Solo se puede marcar al estudiante de la parada actual.')
        if not ruta.estudiantes_llamados.filter(pk=estudiante.pk).exists():
            raise ValueError('Primero debes llamar a su apoderado o persona autorizada.')
        nota_ubicacion = verificar_en_el_punto(ruta, punto_de_la_casa(estudiante))
        ruta.estudiantes_no_recibidos.add(estudiante)
        ruta.estudiantes_llamados.remove(estudiante)
        registrar_evento(
            ruta, 'no_recibido', estudiante,
            detalle=unir_detalle('Nadie lo recibió en su casa: vuelve al colegio.', nota_ubicacion),
        )
        destino = nombre_establecimiento(ruta)
    notificacion = crear_y_despachar_notificacion(
        apoderado=estudiante.apoderado,
        titulo='No se pudo entregar',
        mensaje=f'No había quien recibiera a {nombre} en su casa. Volverá a {destino} al final del recorrido.',
        tipo='estudiante_ausente',
        estudiante=estudiante,
    )
    notificar_receptores_del_estudiante(
        estudiante, 'Vuelve al colegio',
        f'{nombre} vuelve al colegio porque nadie lo recibió en su casa.',
        'estudiante_ausente',
    )
    return {'mensaje': f'{nombre} vuelve al colegio al final del recorrido.', 'notificacion': notificacion}


def _fijar_origen_en_el_furgon(ruta):
    """Toma la posición una sola vez, para que el orden no cambie mientras el furgón avanza."""
    gps_vigente = (
        ruta.ultima_latitud is not None and ruta.ultima_longitud is not None
        and ruta.ubicacion_actualizada_en is not None
        and timezone.now() - ruta.ubicacion_actualizada_en <= MAX_ANTIGUEDAD_GPS
    )
    ruta.origen_recalculo_latitud = float(ruta.ultima_latitud) if gps_vigente else None
    ruta.origen_recalculo_longitud = float(ruta.ultima_longitud) if gps_vigente else None
    ruta.save(update_fields=['origen_recalculo_latitud', 'origen_recalculo_longitud', 'updated_at'])


def marcar_apoderado_disponible(ruta, estudiante):
    """El apoderado apareció antes de llegar al colegio: su casa vuelve al recorrido."""
    nombre = nombre_estudiante(estudiante)
    with transaction.atomic():
        ruta = Ruta.objects.select_for_update().get(pk=ruta.pk)
        _exigir_reparto_en_curso(ruta)
        if (
            not ruta.estudiantes_no_recibidos.filter(pk=estudiante.pk).exists()
            or ruta.estudiantes_entregados.filter(pk=estudiante.pk).exists()
        ):
            raise ValueError('Este estudiante no está marcado para volver al colegio.')
        ruta.estudiantes_no_recibidos.remove(estudiante)
        _fijar_origen_en_el_furgon(ruta)
        registrar_evento(ruta, 'reincorporado', estudiante, detalle='El apoderado está disponible: vuelve al recorrido.')
    notificacion = crear_y_despachar_notificacion(
        apoderado=estudiante.apoderado,
        titulo='Entrega reprogramada',
        mensaje=f'{nombre} volvió al recorrido y será entregado en su casa.',
        tipo='estudiante_abordo',
        estudiante=estudiante,
    )
    notificar_receptores_del_estudiante(
        estudiante, 'Ya no vuelve al colegio',
        f'{nombre} ya no vuelve al colegio: será entregado en su casa.',
        'estudiante_abordo',
    )
    return {'mensaje': f'{nombre} volvió al recorrido.', 'notificacion': notificacion}


MAX_ANTIGUEDAD_GPS = timedelta(minutes=5)
MENSAJE_REPARTO_INICIADO = 'El reparto ya comenzó: no se pueden cambiar las subidas.'


def _exigir_antes_del_reparto(ruta):
    if ruta.sentido == 'desde_colegio' and ruta.reparto_iniciado_en:
        raise ValueError(MENSAJE_REPARTO_INICIADO)


def _aviso_al_apoderado_por_correccion(ruta, estudiante, via):
    nombre = nombre_estudiante(estudiante)
    return crear_y_despachar_notificacion(
        apoderado=estudiante.apoderado,
        titulo='Subió al furgón',
        mensaje=(
            f'Corrección: {nombre} sí subió al furgón (verificado por {via}), '
            'aunque antes se te avisó que no había subido.'
        ),
        tipo='estudiante_abordo',
        estudiante=estudiante,
        ruta=ruta,
        mensaje_delegado=f'{nombre} subió al furgón (verificado por {via}).',
    )


def iniciar_reparto(ruta):
    """Cierra la subida en el colegio: exige que cada estudiante esté a bordo o marcado "No subió"."""
    with transaction.atomic():
        ruta = Ruta.objects.select_for_update().get(pk=ruta.pk)
        if ruta.estado != 'en_ruta' or ruta.sentido != 'desde_colegio':
            raise ValueError('El reparto solo se inicia en una ruta de vuelta en recorrido.')
        if ruta.reparto_iniciado_en:
            return {'mensaje': 'El reparto ya estaba iniciado.'}
        abordados = set(ruta.estudiantes_abordados.values_list('id', flat=True))
        faltan = [e for e in paradas_pendientes(ruta) if e.id not in abordados]
        if faltan:
            nombres = ', '.join(nombre_estudiante(e) for e in faltan)
            raise ValueError(f'Falta indicar si subió o no: {nombres}.')
        if not abordados:
            raise ValueError('No hay estudiantes a bordo para repartir.')
        ruta.reparto_iniciado_en = timezone.now()
        ruta.save(update_fields=['reparto_iniciado_en', 'updated_at'])
        registrar_evento(ruta, 'inicio_reparto')
        registrar_salida_vuelta(ruta)
    return {'mensaje': 'Reparto iniciado.'}


def corregir_abordaje(ruta, estudiante):
    """Un estudiante quedó a bordo por error: pasa a "No subió" antes de iniciar el reparto."""
    nombre = nombre_estudiante(estudiante)
    with transaction.atomic():
        ruta = Ruta.objects.select_for_update().get(pk=ruta.pk)
        if ruta.estado != 'en_ruta' or ruta.sentido != 'desde_colegio':
            raise ValueError('Solo se puede corregir una subida en una ruta de vuelta en recorrido.')
        _exigir_antes_del_reparto(ruta)
        if not ruta.estudiantes_abordados.filter(pk=estudiante.pk).exists():
            raise ValueError('El estudiante no está a bordo.')
        ruta.estudiantes_abordados.remove(estudiante)
        ruta.paradas_completadas.add(estudiante)
        ruta.estudiantes_ausentes.add(estudiante)
        registrar_evento(ruta, 'ausente', estudiante, detalle='Corrección: había quedado a bordo por error.')
    notificacion = crear_y_despachar_notificacion(
        apoderado=estudiante.apoderado,
        titulo='No subió al furgón',
        mensaje=f'Corrección: {nombre} no subió al furgón en el colegio. El registro anterior fue un error.',
        tipo='estudiante_ausente',
        estudiante=estudiante,
    )
    return {'mensaje': f'{nombre} quedó como que no subió.', 'notificacion': notificacion}


def _aviso_al_apoderado_por_subida_con_aviso(ruta, estudiante, via):
    nombre = nombre_estudiante(estudiante)
    return crear_y_despachar_notificacion(
        apoderado=estudiante.apoderado,
        titulo='Subió al furgón',
        mensaje=(
            f'{nombre} subió al furgón (verificado por {via}) aunque habías avisado que hoy '
            'no lo usaría. Se anuló tu aviso de inasistencia.'
        ),
        tipo='estudiante_abordo',
        estudiante=estudiante,
        ruta=ruta,
        mensaje_delegado=f'{nombre} subió al furgón (verificado por {via}).',
    )


def info_parada(estudiante):
    if estudiante is None:
        return None
    return {
        'estudiante_id': estudiante.id,
        'estudiante_nombre': nombre_estudiante(estudiante),
        'direccion': estudiante.direccion_completa,
    }


def resumen_siguiente(ruta, pendientes=None):
    pendientes = paradas_pendientes(ruta) if pendientes is None else pendientes
    siguiente = pendientes[0] if pendientes else None
    return {
        'siguiente_parada': info_parada(siguiente),
        'todas_completadas': siguiente is None,
        'destino': nombre_establecimiento(ruta, por_defecto=''),
    }


def texto_siguiente(resumen):
    siguiente = resumen['siguiente_parada']
    if siguiente:
        return f"Siguiente: {siguiente['estudiante_nombre']}."
    destino = resumen.get('destino')
    return f'Dirigiéndose al colegio{f" ({destino})" if destino else ""}.'


def _registrar_auditoria_abordaje(ruta, estudiante, metodo, delegado=None, detalle=''):
    if not ruta.conductor_perfil_id or not ruta.colegio_id:
        raise ValueError('La ruta debe tener conductor y colegio para registrar el abordaje.')
    # Quien llama ya verificó que no esté a bordo en este recorrido.
    registro = RegistroAbordaje.objects.create(
        ruta=ruta,
        estudiante=estudiante,
        conductor=ruta.conductor_perfil,
        colegio=ruta.colegio,
        delegado=delegado,
        metodo_validacion=metodo,
    )
    registrar_evento(
        ruta, 'abordaje', estudiante,
        metodo=METODOS.get(metodo, metodo).capitalize(),
        persona_nombre=(delegado.usuario.get_full_name() or delegado.usuario.email) if delegado else '',
        persona_rol=ROLES_DELEGADO.get(delegado.tipo_delegado, '') if delegado else '',
        persona_rut=(delegado.rut or '') if delegado else '',
        detalle=detalle,
    )
    return registro


def registrar_abordaje(ruta, estudiante, metodo='facial', delegado=None):
    """
    Registra que el estudiante subió al furgón. En la ida además completa su
    parada, detecta si subió fuera de su domicilio y avisa a su apoderado.
    Devuelve el resumen que la app del conductor muestra en pantalla.
    """
    nombre = nombre_estudiante(estudiante)

    via = METODOS.get(metodo, metodo)

    if not es_recorrido_de_ida(ruta):
        # Vuelta, o ruta aún no iniciada: se mantiene el registro simple de abordaje.
        with transaction.atomic():
            ruta = Ruta.objects.select_for_update().select_related(
                'colegio', 'conductor_perfil'
            ).get(pk=ruta.pk)
            if ruta.estudiantes_abordados.filter(pk=estudiante.pk).exists():
                return {
                    'mensaje': f'{nombre} ya había subido al furgón.',
                    'estudiante_id': estudiante.id,
                    'estudiante_nombre': nombre,
                    'fuera_de_domicilio': False,
                    'tenia_aviso_inasistencia': False,
                    'ya_registrado': True,
                    'siguiente_parada': None,
                    'todas_completadas': False,
                    'notificacion': None,
                }
            _exigir_antes_del_reparto(ruta)
            nota_ubicacion = verificar_en_el_punto(ruta, lugar_de_subida(ruta, estudiante))
            ruta.estudiantes_abordados.add(estudiante)
            # Llegó atrasado después de marcarlo "No subió": vuelve a tener entrega pendiente.
            llego_atrasado = ruta.estudiantes_ausentes.filter(pk=estudiante.pk).exists()
            if llego_atrasado:
                ruta.estudiantes_ausentes.remove(estudiante)
                ruta.paradas_completadas.remove(estudiante)
            _registrar_auditoria_abordaje(
                ruta, estudiante, metodo, delegado,
                detalle=unir_detalle(
                    'Subió después de haber sido marcado "No subió".' if llego_atrasado else '',
                    nota_ubicacion,
                ),
            )
            tenia_aviso = anular_por_abordaje(ruta, estudiante)
        if llego_atrasado:
            notificacion = _aviso_al_apoderado_por_correccion(ruta, estudiante, via)
        elif tenia_aviso:
            notificacion = _aviso_al_apoderado_por_subida_con_aviso(ruta, estudiante, via)
        else:
            notificacion = None
        aviso = ' Tenía aviso de inasistencia: se anuló y se avisó a su apoderado.' if tenia_aviso else ''
        if llego_atrasado:
            aviso = ' Se avisó a su apoderado que finalmente subió.'
        return {
            'mensaje': f'{nombre} subió al furgón.{aviso}',
            'estudiante_id': estudiante.id,
            'estudiante_nombre': nombre,
            'fuera_de_domicilio': False,
            'tenia_aviso_inasistencia': tenia_aviso,
            'ya_registrado': False,
            'siguiente_parada': None,
            'todas_completadas': False,
            'notificacion': notificacion,
        }

    with transaction.atomic():
        # Bloquea la ruta para que dos escaneos simultáneos no calculen mal la siguiente parada.
        ruta = Ruta.objects.select_for_update().select_related('colegio', 'sede').get(pk=ruta.pk)
        pendientes = paradas_pendientes(ruta)
        ids_pendientes = {pendiente.id for pendiente in pendientes}

        if estudiante.id not in ids_pendientes and ruta.estudiantes_abordados.filter(pk=estudiante.pk).exists():
            resumen = resumen_siguiente(ruta, pendientes)
            return {
                'mensaje': f'{nombre} ya había subido al furgón. {texto_siguiente(resumen)}',
                'estudiante_id': estudiante.id,
                'estudiante_nombre': nombre,
                'fuera_de_domicilio': False,
                'ya_registrado': True,
                **resumen,
            }

        esperado = pendientes[0] if pendientes else None
        # También es "fuera de domicilio" si se había marcado ausente y luego sube en otro punto.
        fuera_de_domicilio = esperado is None or esperado.id != estudiante.id

        nota_ubicacion = verificar_en_el_punto(ruta, lugar_de_subida(ruta, estudiante))
        estaba_ausente = ruta.estudiantes_ausentes.filter(pk=estudiante.pk).exists()
        ruta.estudiantes_abordados.add(estudiante)
        ruta.paradas_completadas.add(estudiante)
        ruta.estudiantes_ausentes.remove(estudiante)
        if estaba_ausente:
            detalle_subida = 'Subió después de haber sido marcado ausente.'
        else:
            detalle_subida = 'Subió fuera de su domicilio o de su turno.' if fuera_de_domicilio else ''
        _registrar_auditoria_abordaje(
            ruta, estudiante, metodo, delegado, detalle=unir_detalle(detalle_subida, nota_ubicacion),
        )
        # Si el apoderado había avisado que no asistiría, el rostro/QR confirma que sí está.
        tenia_aviso = anular_por_abordaje(ruta, estudiante)
        pendientes = [pendiente for pendiente in pendientes if pendiente.id != estudiante.id]
        resumen = resumen_siguiente(ruta, pendientes)

    if tenia_aviso:
        notificacion = _aviso_al_apoderado_por_subida_con_aviso(ruta, estudiante, via)
        return {
            'mensaje': (
                f'{nombre} subió. Tenía aviso de inasistencia: se anuló y se avisó a su apoderado. '
                f'{texto_siguiente(resumen)}'
            ),
            'estudiante_id': estudiante.id,
            'estudiante_nombre': nombre,
            'fuera_de_domicilio': fuera_de_domicilio,
            'tenia_aviso_inasistencia': True,
            'ya_registrado': False,
            'notificacion': notificacion,
            **resumen,
        }

    if fuera_de_domicilio:
        titulo = 'Subió fuera de su domicilio'
        mensaje_apoderado = (
            f'{nombre} subió al furgón fuera de su domicilio (verificado por {via}). '
            'El conductor ya no pasará por su casa.'
        )
    else:
        titulo = 'Estudiante abordó'
        mensaje_apoderado = f'{nombre} subió al furgón en su domicilio (verificado por {via}).'

    notificacion = crear_y_despachar_notificacion(
        apoderado=estudiante.apoderado,
        titulo=titulo,
        mensaje=mensaje_apoderado,
        tipo='estudiante_abordo',
        estudiante=estudiante,
        ruta=ruta,
    )

    aviso = ' Se avisó a su apoderado que subió fuera de su domicilio.' if fuera_de_domicilio else ''
    return {
        'mensaje': f'{nombre} subió.{aviso} {texto_siguiente(resumen)}',
        'estudiante_id': estudiante.id,
        'estudiante_nombre': nombre,
        'fuera_de_domicilio': fuera_de_domicilio,
        'tenia_aviso_inasistencia': False,
        'ya_registrado': False,
        'notificacion': notificacion,
        **resumen,
    }


def registrar_ausencia(ruta, estudiante):
    """El estudiante no salió (ida) o no subió en el colegio (vuelta): se salta y se avisa a su apoderado."""
    nombre = nombre_estudiante(estudiante)
    with transaction.atomic():
        ruta = Ruta.objects.select_for_update().select_related('colegio', 'sede').get(pk=ruta.pk)
        _exigir_antes_del_reparto(ruta)
        # En la ida, en la casa del niño; en la vuelta, en el colegio.
        nota_ubicacion = verificar_en_el_punto(ruta, lugar_de_subida(ruta, estudiante))
        ruta.paradas_completadas.add(estudiante)
        ruta.estudiantes_ausentes.add(estudiante)
        registrar_evento(ruta, 'ausente', estudiante, detalle=nota_ubicacion)
        resumen = resumen_siguiente(ruta)

    es_ida = ruta.sentido == 'hacia_colegio'
    notificacion = crear_y_despachar_notificacion(
        apoderado=estudiante.apoderado,
        titulo='No se presentó al furgón' if es_ida else 'No subió al furgón',
        mensaje=(
            f'El conductor pasó por el domicilio de {nombre} y no se presentó. '
            'El furgón continuó su recorrido.'
            if es_ida
            else f'{nombre} no subió al furgón en el colegio. El furgón continuó su recorrido.'
        ),
        tipo='estudiante_ausente',
        estudiante=estudiante,
    )
    return {
        'mensaje': (
            f'{nombre} marcado como ausente. {texto_siguiente(resumen)}'
            if es_ida
            else f'{nombre} marcado como que no subió.'
        ),
        'estudiante_id': estudiante.id,
        'estudiante_nombre': nombre,
        'notificacion': notificacion,
        **resumen,
    }
