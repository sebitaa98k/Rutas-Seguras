"""RUT: formato único (12345678-9), validación del dígito verificador y RUT que cada colegio habilita."""
import re

from django.utils import timezone
from rest_framework import serializers

_FORMATO_RUT = re.compile(r'^\d{7,8}-[\dK]$')
MENSAJE_RUT_NO_HABILITADO = 'Este RUT no está habilitado en este colegio. Contacta al establecimiento.'


def formatear_rut(valor):
    """Deja el RUT como 12345678-9. No valida el dígito verificador."""
    limpio = re.sub(r'[\s.\-]', '', str(valor or '')).upper()
    if len(limpio) < 2:
        return limpio
    return f'{limpio[:-1]}-{limpio[-1]}'


def rut_tiene_formato(rut):
    return bool(_FORMATO_RUT.match(rut or ''))


MENSAJE_RUT_INVALIDO = 'El RUT no es válido. Revisa los números y el dígito verificador (ejemplo: 12345678-5).'


def digito_verificador(cuerpo):
    """Dígito verificador chileno (módulo 11) del número del RUT."""
    suma, factor = 0, 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return {11: '0', 10: 'K'}.get(resto, str(resto))


def rut_valido(rut):
    """El RUT ya formateado tiene forma 12345678-9 y su dígito verificador es correcto."""
    if not rut_tiene_formato(rut):
        return False
    cuerpo, dv = rut.split('-')
    return digito_verificador(cuerpo) == dv


def validar_rut(valor):
    """Para formularios: devuelve el RUT como 12345678-9 o un error si no es un RUT real."""
    rut = formatear_rut(valor)
    if not rut_valido(rut):
        raise serializers.ValidationError(MENSAJE_RUT_INVALIDO)
    return rut


def reservar_rut_habilitado(perfil, colegio, exigir_disponible=False, creado_por=None):
    """Marca el RUT como usado por la cuenta. Un administrador no necesita cargarlo antes."""
    from .models import RutHabilitado

    if colegio is None:
        return None
    entrada = RutHabilitado.objects.select_for_update().filter(colegio=colegio, rut=perfil.rut).first()
    # Un RUT en la papelera ya no sirve para registrarse.
    if exigir_disponible and (entrada is None or entrada.apoderado_id or not entrada.activo):
        raise serializers.ValidationError({'rut': MENSAJE_RUT_NO_HABILITADO})
    if entrada is None:
        entrada = RutHabilitado(colegio=colegio, rut=perfil.rut, creado_por=creado_por)
    entrada.apoderado = perfil
    entrada.usado_en = timezone.now()
    entrada.activo = True
    entrada.desactivado_en = None
    entrada.save()
    return entrada
