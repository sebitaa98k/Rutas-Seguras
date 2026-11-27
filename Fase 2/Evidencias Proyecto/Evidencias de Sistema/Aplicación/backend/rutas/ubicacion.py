"""Regla de "estar en el punto": subidas, entregas y ausencias se registran cerca del lugar que corresponde."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from usuarios.planes import nombre_establecimiento
from usuarios.optimizacion_rutas import distancia_km

DISTANCIA_MAXIMA_METROS = 100
# Una posición más antigua o menos precisa que esto no permite verificar dónde está el furgón.
ANTIGUEDAD_MAXIMA_GPS = timedelta(minutes=2)
PRECISION_MAXIMA_METROS = 100

SIN_UBICACION = 'Sin ubicación verificada: el furgón no tenía una posición GPS reciente y precisa.'
SIN_COORDENADAS = 'Sin ubicación verificada: el lugar no tiene su ubicación registrada.'
DEPURACION_VUELTA = 'Sin ubicación verificada: modo depuración de la vuelta (DEPURACION_VUELTA_SIN_DISTANCIA).'


def _coordenadas(objeto):
    if objeto is None or objeto.latitud is None or objeto.longitud is None:
        return None
    return (float(objeto.latitud), float(objeto.longitud))


def punto_del_colegio(ruta):
    """La sede de la ruta o, si no tiene, el colegio."""
    nombre = nombre_establecimiento(ruta)
    return _coordenadas(ruta.sede if ruta.sede_id else ruta.colegio), nombre


def punto_de_la_casa(estudiante):
    nombre = f'la casa de {estudiante.nombre} {estudiante.apellido}'.strip()
    return _coordenadas(estudiante), nombre


def lugar_de_subida(ruta, estudiante):
    """En la ida sube en su casa; en la vuelta, en el colegio."""
    return punto_de_la_casa(estudiante) if ruta.sentido == 'hacia_colegio' else punto_del_colegio(ruta)


def lugar_de_entrega(ruta, estudiante, por_el_inspector=False):
    """En la ida y con el inspector se entrega en el colegio; en la vuelta, en la casa."""
    if ruta.sentido == 'hacia_colegio' or por_el_inspector:
        return punto_del_colegio(ruta)
    return punto_de_la_casa(estudiante)


def _posicion_del_furgon(ruta):
    """La última posición GPS del furgón, si es reciente y suficientemente precisa."""
    if ruta.ultima_latitud is None or ruta.ultima_longitud is None or not ruta.ubicacion_actualizada_en:
        return None
    if timezone.now() - ruta.ubicacion_actualizada_en > ANTIGUEDAD_MAXIMA_GPS:
        return None
    if ruta.precision_gps_metros is not None and float(ruta.precision_gps_metros) > PRECISION_MAXIMA_METROS:
        return None
    return (float(ruta.ultima_latitud), float(ruta.ultima_longitud))


def verificar_en_el_punto(ruta, lugar):
    """
    `lugar` es (coordenadas, nombre). Si el furgón está lejos, impide la acción.
    Si no se puede verificar (sin GPS reciente o lugar sin ubicación), la permite y devuelve
    una nota para la auditoría. Si está en el punto, devuelve ''.
    """
    coordenadas, nombre = lugar
    if settings.DEPURACION_VUELTA_SIN_DISTANCIA and ruta.sentido != 'hacia_colegio':
        # Depuración: en la vuelta se puede marcar lejos del colegio o de la casa.
        return DEPURACION_VUELTA
    if coordenadas is None:
        return SIN_COORDENADAS
    furgon = _posicion_del_furgon(ruta)
    if furgon is None:
        return SIN_UBICACION
    metros = distancia_km(furgon, coordenadas) * 1000
    if metros > DISTANCIA_MAXIMA_METROS:
        raise ValueError(
            f'Debes estar a menos de {DISTANCIA_MAXIMA_METROS} m de {nombre} para registrarlo. '
            f'Estás a unos {round(metros)} m.'
        )
    return ''


def unir_detalle(*partes):
    return ' '.join(parte for parte in partes if parte)
