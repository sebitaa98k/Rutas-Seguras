"""Contraseña inicial de las cuentas que crea un administrador."""
import unicodedata

LARGO_MINIMO_NUEVA = 8


def _inicial(texto):
    texto = (texto or '').strip()
    if not texto:
        return ''
    letra = texto[0].upper()
    # La Ñ es una letra propia del castellano y no se le quita la tilde.
    if letra == 'Ñ':
        return letra
    return unicodedata.normalize('NFD', letra)[0]


def generar_password_inicial(nombre, apellido, rut):
    """Iniciales de nombre y apellido en mayúscula + 4 primeros dígitos del RUT.

    Ej: Ñandú Pérez, 12.345.678-9 -> ÑP1234.
    """
    cuerpo = (rut or '').split('-')[0]
    digitos = ''.join(c for c in cuerpo if c.isdigit())[:4]
    return f'{_inicial(nombre)}{_inicial(apellido)}{digitos}'


def asignar_password_temporal(usuario, password):
    """Fija una contraseña que la persona deberá cambiar al ingresar."""
    usuario.set_password(password)
    usuario.debe_cambiar_password = True
    usuario.save(update_fields=['password', 'debe_cambiar_password'])


def password_provisoria():
    """Relleno para los serializers de registro; se reemplaza tras crear la cuenta."""
    import secrets
    return secrets.token_urlsafe(24)


def aplicar_password_inicial(usuario, rut):
    """Asigna la contraseña de la regla y devuelve el texto para mostrárselo al administrador."""
    password = generar_password_inicial(usuario.first_name, usuario.last_name, rut)
    asignar_password_temporal(usuario, password)
    return password
