"""Nombres de personas con un formato parejo: "juan  carlos DE la fuente" -> "Juan Carlos de la Fuente".

Se aplica al guardar (Usuario, Estudiante y PersonaAutorizada), así vale para todos los formularios
del panel web, la app y la carga de datos.
"""
import re

# Partículas que van en minúscula salvo que sean la primera palabra.
PARTICULAS = {'de', 'del', 'la', 'las', 'los', 'y', 'e', 'van', 'von', 'da', 'di'}


def _capitalizar_palabra(palabra):
    # Respeta los compuestos con guion o apóstrofe: "maría-josé" -> "María-José", "o'higgins" -> "O'Higgins".
    return re.sub(r"[^\W\d_]+", lambda m: m.group(0)[:1].upper() + m.group(0)[1:].lower(), palabra)


def normalizar_nombre(valor):
    """Devuelve el nombre con mayúscula inicial en cada palabra y sin espacios de más."""
    if not valor:
        return valor
    palabras = str(valor).split()
    resultado = []
    for indice, palabra in enumerate(palabras):
        minuscula = palabra.lower()
        if indice > 0 and minuscula in PARTICULAS:
            resultado.append(minuscula)
        else:
            resultado.append(_capitalizar_palabra(palabra))
    return ' '.join(resultado)
