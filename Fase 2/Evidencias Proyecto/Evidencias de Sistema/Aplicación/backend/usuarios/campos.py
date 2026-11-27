"""Campos propios: vector facial cifrado y RUT con formato único."""
import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


@lru_cache(maxsize=4)
def _fernet_para(clave):
    try:
        return Fernet(clave)
    except ValueError as exc:
        raise ImproperlyConfigured('BIOMETRIA_CLAVE_CIFRADO no es una clave Fernet válida.') from exc


def _fernet():
    clave = settings.BIOMETRIA_CLAVE_CIFRADO
    if not clave:
        raise ImproperlyConfigured('Falta BIOMETRIA_CLAVE_CIFRADO en backend/.env.')
    return _fernet_para(clave)


def cifrar(valor):
    return _fernet().encrypt(json.dumps(valor).encode('utf-8')).decode('ascii')


def descifrar(token):
    """Un valor ilegible se trata como vector inexistente: se regenera desde la foto o se usa QR."""
    try:
        return json.loads(_fernet().decrypt(token.encode('ascii')))
    except (InvalidToken, ValueError):
        return None


class EmbeddingCifradoField(models.TextField):
    def from_db_value(self, value, expression, connection):
        return None if value is None else descifrar(value)

    def to_python(self, value):
        return descifrar(value) if isinstance(value, str) else value

    def get_prep_value(self, value):
        return None if value is None else cifrar(value)

    def value_to_string(self, obj):
        return self.get_prep_value(self.value_from_object(obj))


class RutField(models.CharField):
    """
    Guarda el RUT siempre como 12345678-9 (sin puntos, con guion y K mayúscula), venga como venga.
    La validación del dígito verificador se hace en los formularios (usuarios.rut.validar_rut).
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 12)
        super().__init__(*args, **kwargs)

    def pre_save(self, model_instance, add):
        from .rut import formatear_rut
        valor = getattr(model_instance, self.attname)
        if valor:
            valor = formatear_rut(valor)
            setattr(model_instance, self.attname, valor)
        return valor

