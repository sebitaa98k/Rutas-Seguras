"""Almacenamiento de las fotos de estudiantes: se guardan cifradas y se entregan descifradas."""
from io import BytesIO

from cryptography.fernet import InvalidToken
from django.core.files.base import ContentFile, File
from django.core.files.storage import FileSystemStorage

from .campos import _fernet

# Encabezados de los formatos de foto aceptados: una foto guardada antes del cifrado empieza así.
_ENCABEZADOS_DE_IMAGEN = (b'\xff\xd8\xff', b'\x89PNG', b'RIFF')


class FotoIlegibleError(OSError):
    """La foto está cifrada con otra clave o el archivo está dañado."""


def es_imagen_sin_cifrar(datos):
    return datos.startswith(_ENCABEZADOS_DE_IMAGEN)


def cifrar_bytes(datos):
    return _fernet().encrypt(datos)


def descifrar_bytes(datos):
    """Devuelve la imagen original. Una foto aún sin cifrar se entrega tal cual."""
    try:
        return _fernet().decrypt(datos)
    except InvalidToken:
        if es_imagen_sin_cifrar(datos):
            return datos
        raise FotoIlegibleError('La foto no se puede descifrar con la clave actual.') from None


class AlmacenamientoFotosCifradas(FileSystemStorage):
    """Igual que el almacenamiento en disco de Django, pero el archivo en disco queda cifrado."""

    def _save(self, name, content):
        if hasattr(content, 'seek'):
            content.seek(0)
        return super()._save(name, ContentFile(cifrar_bytes(content.read())))

    def _open(self, name, mode='rb'):
        with super()._open(name, 'rb') as archivo:
            datos = archivo.read()
        return File(BytesIO(descifrar_bytes(datos)), name=name)


def almacenamiento_fotos_estudiantes():
    return AlmacenamientoFotosCifradas()
