"""Correo con el código para recuperar la contraseña, enviado por Gmail."""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)

ASUNTO = 'Código para recuperar tu contraseña - Rutas Seguras'


def _texto(nombre, codigo):
    return (
        f'Hola {nombre},\n\n'
        'Recibimos una solicitud para recuperar tu contraseña.\n\n'
        f'Tu código de recuperación es: {codigo}\n\n'
        'Este código es válido durante 10 minutos.\n\n'
        'Si tú no solicitaste este cambio, puedes ignorar este correo.\n\n'
        'Tu ruta escolar, más segura.'
    )


def _html(nombre, codigo):
    return f'''
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 30px;">
            <h1 style="color: #0f766e;">Rutas Seguras</h1>
            <h2>Recuperar contraseña</h2>
            <p>Hola {nombre},</p>
            <p>Recibimos una solicitud para recuperar tu contraseña.</p>
            <p>Tu código de recuperación es:</p>
            <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #173330;
                        padding: 20px; text-align: center; background: #e8f5f3; border-radius: 12px;">
                {codigo}
            </div>
            <p>Este código es válido durante <strong>10 minutos</strong>.</p>
            <p>Si tú no solicitaste este cambio, puedes ignorar este correo.</p>
            <p>Tu ruta escolar, más segura. 🚌</p>
        </div>
    '''


def correo_configurado():
    return bool(settings.CORREO_USUARIO and settings.CORREO_PASSWORD)


def enviar_codigo_recuperacion(usuario, codigo):
    """
    Envía el código. Devuelve True si se envió (o, sin correo configurado en desarrollo, si se mostró
    en la terminal) y False si falló. El motivo del error solo queda en la terminal del servidor.
    """
    if not correo_configurado():
        if settings.DEBUG:
            print(f'[MODO DEV] Código de recuperación para {usuario.email}: {codigo}')
            return True
        logger.error('Recuperación de contraseña: falta EMAIL_HOST_USER o EMAIL_HOST_PASSWORD.')
        return False

    nombre = usuario.first_name or ''
    mensaje = EmailMultiAlternatives(
        subject=ASUNTO,
        body=_texto(nombre, codigo),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[usuario.email],
    )
    mensaje.attach_alternative(_html(nombre, codigo), 'text/html')
    try:
        mensaje.send()
    except Exception as error:  # noqa: BLE001 - cualquier falla de envío se informa igual al usuario
        print('Error enviando correo de recuperación:', error)
        return False
    return True
