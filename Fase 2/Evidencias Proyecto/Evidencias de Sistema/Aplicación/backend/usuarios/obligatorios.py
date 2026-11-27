"""Campos obligatorios de los formularios, revisados también en el servidor (no solo en la pantalla)."""


def _vacio(valor):
    return valor is None or (isinstance(valor, str) and not valor.strip())


def campos_faltantes(attrs, instance, campos):
    """
    `campos` es {campo: mensaje}. Devuelve los errores de los que quedan vacíos, considerando lo que ya
    tiene guardado el registro cuando es una edición parcial.
    """
    errores = {}
    for campo, mensaje in campos.items():
        valor = attrs[campo] if campo in attrs else getattr(instance, campo, None)
        if _vacio(valor):
            errores[campo] = mensaje
    return errores
