import logging
import os
from typing import List, Optional

import firebase_admin
from firebase_admin import messaging

from .models import PerfilApoderado, Estudiante, Notificacion, FCMToken

logger = logging.getLogger(__name__)
# Canal de Android que crea la app con importancia alta (ver push-notification.service.ts).
CANAL_ANDROID_AVISOS = 'avisos_rutas'


def obtener_firebase_app():
    """Inicializa Firebase de forma perezosa sin impedir el arranque local."""
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        logger.warning(
            'FCM no configurado: falta GOOGLE_APPLICATION_CREDENTIALS. '
            'La notificacion se conservara solamente en la base de datos.'
        )
        return None

    try:
        return firebase_admin.get_app()
    except ValueError:
        try:
            return firebase_admin.initialize_app()
        except Exception as exc:
            logger.error('No fue posible inicializar Firebase Admin: %s', exc)
            return None


def _es_error_token_invalido(exc: Exception) -> bool:
    tipos_token_invalido = tuple(
        tipo for tipo in (
            getattr(messaging, 'UnregisteredError', None),
            getattr(messaging, 'SenderIdMismatchError', None),
        ) if isinstance(tipo, type)
    )
    if tipos_token_invalido and isinstance(exc, tipos_token_invalido):
        return True
    mensaje = str(exc).lower()
    return any(indicio in mensaje for indicio in (
        'unregistered', 'invalid-registration-token',
        'requested entity was not found', 'sender id mismatch',
    ))


# Eventos del recorrido que también le interesan a quien recibe al estudiante.
TIPOS_PARA_DELEGADOS = {'ruta_iniciada', 'estudiante_abordo', 'estudiante_llego', 'ruta_finalizada', 'emergencia'}


def _delegado_recibe(perfil, tipo, ruta):
    """
    El inspector recibe a los estudiantes en el colegio (ida) y la persona autorizada
    los recibe en casa (vuelta). Las emergencias les llegan a ambos en cualquier tramo.
    """
    if tipo not in TIPOS_PARA_DELEGADOS:
        return False
    if tipo == 'emergencia':
        return True
    if ruta is None:
        return False
    sentido_que_recibe = 'hacia_colegio' if perfil.tipo_delegado == 'inspector' else 'desde_colegio'
    return ruta.sentido == sentido_que_recibe


def notificar_delegados(estudiantes, titulo, mensaje, tipo, ruta=None, excluir=None):
    """
    Crea una notificación propia para cada delegado (persona autorizada o inspector)
    que recibe a alguno de los estudiantes, sin duplicar si recibe a varios.
    `excluir` es el perfil que generó el evento (ej: quien recibió al estudiante).
    Devuelve la cantidad de delegados notificados.
    """
    from .autorizaciones import perfiles_receptores_autorizados

    estudiantes = list(estudiantes)
    por_perfil = {}
    for estudiante in estudiantes:
        try:
            perfiles = perfiles_receptores_autorizados(estudiante)
        except Exception as e:
            logger.error(f"Error buscando delegados del estudiante {estudiante.pk}: {e}")
            continue
        for perfil in perfiles:
            if perfil != excluir and _delegado_recibe(perfil, tipo, ruta):
                por_perfil.setdefault(perfil.id, (perfil, estudiante))

    for perfil, estudiante in por_perfil.values():
        try:
            crear_y_despachar_notificacion_usuario(
                perfil.usuario, titulo, mensaje, tipo=tipo,
                estudiante=estudiante if len(estudiantes) == 1 else None,
            )
        except Exception as e:
            logger.error(f"Error notificando al delegado {perfil.pk}: {e}")
    return len(por_perfil)


def notificar_receptores_del_estudiante(estudiante, titulo, mensaje, tipo):
    """Avisa a todas las personas autorizadas e inspectores del estudiante, sin importar el tramo."""
    from .autorizaciones import perfiles_receptores_autorizados

    try:
        perfiles = perfiles_receptores_autorizados(estudiante)
    except Exception as e:
        logger.error(f"Error buscando delegados del estudiante {estudiante.pk}: {e}")
        return
    for perfil in perfiles:
        try:
            crear_y_despachar_notificacion_usuario(perfil.usuario, titulo, mensaje, tipo=tipo, estudiante=estudiante)
        except Exception as e:
            logger.error(f"Error notificando al delegado {perfil.pk}: {e}")


def crear_y_despachar_notificacion(
    apoderado: Optional[PerfilApoderado],
    titulo: str,
    mensaje: str,
    tipo: str,
    estudiante: Optional[Estudiante] = None,
    ruta=None,
    mensaje_delegado: Optional[str] = None,
    excluir_delegado=None,
) -> Optional[Notificacion]:
    """
    1. Registra la notificación en la base de datos de Django para el apoderado (si existe).
    2. Si el estudiante tiene un apoderado no pasado explícitamente, lo recupera de estudiante.apoderado.
    3. Notifica a los FCMTokens del apoderado.
    4. Los delegados que reciben al estudiante obtienen su propia notificación según su rol
       (ver notificar_delegados); `mensaje_delegado` reemplaza el texto si el del apoderado no aplica.
    5. Maneja excepciones para evitar que errores en notificaciones rompan la acción del conductor.
    """
    if not apoderado and estudiante and hasattr(estudiante, 'apoderado'):
        apoderado = estudiante.apoderado

    notificacion = None
    if apoderado:
        try:
            notificacion = Notificacion.objects.create(
                apoderado=apoderado,
                destinatario=apoderado.usuario,
                estudiante=estudiante,
                titulo=titulo,
                mensaje=mensaje,
                tipo=tipo
            )
        except Exception as e:
            logger.error(f"Error registrando Notificacion en BD: {e}")

        try:
            fcm_tokens = FCMToken.objects.filter(usuario=apoderado.usuario, is_active=True)
            for token_obj in fcm_tokens:
                despachar_fcm_push(token_obj, titulo, mensaje, tipo, notificacion.id if notificacion else 0)
        except Exception as e:
            logger.error(f"Error despachando FCM Tokens para apoderado: {e}")

    if estudiante:
        notificar_delegados([estudiante], titulo, mensaje_delegado or mensaje, tipo, ruta, excluir_delegado)

    return notificacion


def crear_y_despachar_notificacion_usuario(usuario, titulo, mensaje, tipo='aviso_sistema', estudiante=None):
    """Persiste y envía una notificación informativa a cualquier usuario."""
    notificacion = Notificacion.objects.create(
        destinatario=usuario, titulo=titulo, mensaje=mensaje,
        tipo=tipo, estudiante=estudiante,
    )
    for token_obj in FCMToken.objects.filter(usuario=usuario, is_active=True):
        despachar_fcm_push(token_obj, titulo, mensaje, tipo, notificacion.id)
    return notificacion


def despachar_fcm_push(
    token_obj: FCMToken,
    titulo: str,
    mensaje: str,
    tipo: str,
    notificacion_id: int
) -> bool:
    """
    Despacha la notificación Push al FCM Token.
    Si se detecta que el token caducó o fue anulado en el dispositivo,
    se desactiva automáticamente (is_active=False).
    """
    try:
        # Intenta usar firebase_admin si está configurado en el proyecto
        firebase_app = obtener_firebase_app()
        if firebase_app is None:
            return False

        message = messaging.Message(
            notification=messaging.Notification(
                title=titulo,
                body=mensaje,
            ),
            data={
                'notificacion_id': str(notificacion_id),
                'tipo': tipo,
                'click_action': 'FLUTTER_NOTIFICATION_CLICK'
            },
            # Prioridad alta y canal "avisos_rutas" (lo crea la app con importancia alta):
            # el aviso aparece flotando arriba de la pantalla aunque la app esté cerrada.
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(channel_id=CANAL_ANDROID_AVISOS),
            ),
            token=token_obj.token,
        )
        messaging.send(message, app=firebase_app)
        logger.info(f"Push enviado exitosamente a {token_obj.usuario.email}")
        return True

    except ImportError as exc:
        logger.error('Firebase Admin no esta disponible: %s', exc)
        return False

    except Exception as exc:
        if _es_error_token_invalido(exc):
            logger.warning(f"Desactivando token de dispositivo inactivo/expirado para {token_obj.usuario.email}")
            token_obj.is_active = False
            token_obj.save(update_fields=['is_active'])
        else:
            logger.error(f"Error despachando Push a {token_obj.usuario.email}: {exc}")
        return False


def notificar_apoderados_de_estudiantes(
    estudiantes: List[Estudiante],
    titulo: str,
    mensaje_template: str,
    tipo: str,
    ruta=None,
):
    """
    Notifica automáticamente a los apoderados de una lista de estudiantes.
    `mensaje_template` puede incluir `{nombre_estudiante}` si aplica.
    """
    apoderados_procesados = set()

    for est in estudiantes:
        apoderado = est.apoderado
        mensaje_personalizado = mensaje_template.format(
            nombre_estudiante=f"{est.nombre} {est.apellido}".strip()
        ) if '{nombre_estudiante}' in mensaje_template else mensaje_template

        crear_y_despachar_notificacion(
            apoderado=apoderado,
            titulo=titulo,
            mensaje=mensaje_personalizado,
            tipo=tipo,
            estudiante=est,
            ruta=ruta,
        )
        apoderados_procesados.add(apoderado.id)

    return len(apoderados_procesados)


def notificar_inicio_ruta_agrupado(ruta, estudiantes):
    """Un solo aviso por apoderado, aunque tenga varios hijos en la ruta.

    Se avisa a todos los apoderados de la ruta, salvo los hijos marcados "no asiste hoy".
    Ida: el furgón va a buscarlos. Vuelta: el furgón comenzó la salida desde el colegio.
    """
    grupos = {}
    for estudiante in estudiantes:
        if estudiante.apoderado_id:
            grupos.setdefault(estudiante.apoderado_id, []).append(estudiante)

    for grupo in grupos.values():
        nombres = [f'{est.nombre} {est.apellido}'.strip() for est in grupo]
        sujetos = nombres[0] if len(nombres) == 1 else ', '.join(nombres[:-1]) + f' y {nombres[-1]}'
        if ruta.sentido == 'hacia_colegio':
            # Ida: nadie va a bordo al partir; se avisa que el furgón va camino a buscarlos.
            mensaje = f'El furgón de la ruta {ruta.nombre} comenzó su recorrido y va a buscar a {sujetos}.'
        else:
            # Vuelta: al iniciar todavía están subiendo en el colegio; la subida se avisa aparte.
            mensaje = (
                f'El furgón de la ruta {ruta.nombre} comenzó la vuelta y llevará a '
                f'{sujetos} a casa. Te avisaremos cuando suba{"n" if len(nombres) > 1 else ""} y al llegar.'
            )

        crear_y_despachar_notificacion(
            apoderado=grupo[0].apoderado,
            titulo='Ruta iniciada',
            mensaje=mensaje,
            tipo='ruta_iniciada',
        )

    notificar_delegados(
        estudiantes, 'Ruta iniciada',
        f'El furgón de la ruta {ruta.nombre} comenzó su recorrido.',
        'ruta_iniciada', ruta,
    )
    return len(grupos)
