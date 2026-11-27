"""Orden óptimo de las paradas de una ruta.

Las paradas pendientes se ordenan para recorrer la menor distancia posible:
- Ida: desde la posición actual del conductor (GPS), pasando por todas las casas,
  hasta el colegio o sede.
- Vuelta: desde el colegio (o desde la última casa entregada) hasta la última casa.
  No usa GPS: el recorrido parte siempre en el colegio y se continúa desde cada entrega.

Se usa distancia en línea recta (haversine): es instantánea, no depende de servicios
externos y para recorridos urbanos dentro de unas pocas comunas da el mismo orden
que la distancia por calles en la gran mayoría de los casos.
"""
from itertools import combinations
from math import asin, cos, radians, sin, sqrt

from .inasistencias import ids_no_asisten

# Hasta este número de paradas se calcula el orden exacto (Held-Karp).
MAX_PARADAS_EXACTO = 10


def distancia_km(a, b):
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


def _largo(orden, puntos, origen, destino):
    total = 0.0
    previo = origen
    for indice in orden:
        if previo is not None:
            total += distancia_km(previo, puntos[indice])
        previo = puntos[indice]
    if destino is not None and previo is not None:
        total += distancia_km(previo, destino)
    return total


def _orden_exacto(puntos, origen, destino):
    """Held-Karp para camino abierto: origen y destino son opcionales (None = libre)."""
    n = len(puntos)

    def costo_inicio(i):
        return distancia_km(origen, puntos[i]) if origen is not None else 0.0

    # mejor[(conjunto, ultimo)] = (costo, anterior)
    mejor = {(1 << i, i): (costo_inicio(i), None) for i in range(n)}
    for tamano in range(2, n + 1):
        for subconjunto in combinations(range(n), tamano):
            mascara = sum(1 << i for i in subconjunto)
            for ultimo in subconjunto:
                previa = mascara & ~(1 << ultimo)
                mejor[(mascara, ultimo)] = min(
                    (mejor[(previa, k)][0] + distancia_km(puntos[k], puntos[ultimo]), k)
                    for k in subconjunto if k != ultimo
                )

    completo = (1 << n) - 1
    ultimo = min(
        range(n),
        key=lambda i: mejor[(completo, i)][0] + (distancia_km(puntos[i], destino) if destino is not None else 0.0),
    )
    orden = []
    mascara = completo
    while ultimo is not None:
        orden.append(ultimo)
        _, anterior = mejor[(mascara, ultimo)]
        mascara &= ~(1 << ultimo)
        ultimo = anterior
    return list(reversed(orden))


def _orden_aproximado(puntos, origen, destino):
    """Vecino más cercano y luego mejora 2-opt, para rutas con muchas paradas."""
    pendientes = set(range(len(puntos)))
    orden = []
    actual = origen
    while pendientes:
        if actual is None:
            # Sin origen: se parte por la parada más lejana al destino (o la primera).
            siguiente = max(pendientes, key=lambda i: distancia_km(puntos[i], destino)) if destino else min(pendientes)
        else:
            siguiente = min(pendientes, key=lambda i: distancia_km(actual, puntos[i]))
        orden.append(siguiente)
        pendientes.remove(siguiente)
        actual = puntos[siguiente]

    mejoro = True
    while mejoro:
        mejoro = False
        for i in range(len(orden) - 1):
            for j in range(i + 1, len(orden)):
                candidato = orden[:i] + orden[i:j + 1][::-1] + orden[j + 1:]
                if _largo(candidato, puntos, origen, destino) + 1e-9 < _largo(orden, puntos, origen, destino):
                    orden = candidato
                    mejoro = True
    return orden


def ordenar_paradas(paradas, origen=None, destino=None):
    """
    Ordena `paradas` (lista de (elemento, (lat, lng))) para minimizar el recorrido.
    `origen` y `destino` son tuplas (lat, lng) o None si quedan libres.
    Devuelve la lista de elementos en el orden a visitar.
    """
    if len(paradas) <= 1:
        return [elemento for elemento, _ in paradas]
    puntos = [coordenadas for _, coordenadas in paradas]
    if len(paradas) <= MAX_PARADAS_EXACTO:
        orden = _orden_exacto(puntos, origen, destino)
    else:
        orden = _orden_aproximado(puntos, origen, destino)
    return [paradas[i][0] for i in orden]


def _coordenadas(objeto, campo_lat='latitud', campo_lng='longitud'):
    lat = getattr(objeto, campo_lat, None) if objeto is not None else None
    lng = getattr(objeto, campo_lng, None) if objeto is not None else None
    if lat is None or lng is None:
        return None
    return (float(lat), float(lng))


def estudiantes_en_orden(ruta):
    """
    Estudiantes de la ruta en el orden en que se muestran y visitan: primero los que
    ya subieron o fueron marcados ausentes, luego los pendientes en orden óptimo
    desde la posición actual del conductor y al final los que hoy no asisten
    (aviso del apoderado), que no forman parte del recorrido.
    """
    if not ruta.pk:
        return []
    estudiantes = list(ruta.estudiantes.all().order_by('id'))
    por_id = {estudiante.id: estudiante for estudiante in estudiantes}
    # Paradas resueltas en el orden en que se completaron (id de la tabla intermedia).
    orden_resueltos = list(
        ruta.paradas_completadas.through.objects
        .filter(ruta_id=ruta.pk)
        .order_by('id')
        .values_list('estudiante_id', flat=True)
    )
    hechos = [por_id[i] for i in orden_resueltos if i in por_id]
    resueltos = set(orden_resueltos)
    no_asisten = ids_no_asisten(ruta)
    sin_resolver = [estudiante for estudiante in estudiantes if estudiante.id not in resueltos]
    # Los que nadie recibió vuelven al colegio: van después de todas las casas.
    no_recibidos = set(ruta.estudiantes_no_recibidos.values_list('id', flat=True))
    vuelven = [estudiante for estudiante in sin_resolver if estudiante.id in no_recibidos]
    pendientes = [
        estudiante for estudiante in sin_resolver
        if estudiante.id not in no_asisten and estudiante.id not in no_recibidos
    ]
    ausentes_por_aviso = [estudiante for estudiante in sin_resolver if estudiante.id in no_asisten]

    establecimiento = _coordenadas(ruta.sede) if ruta.sede_id else _coordenadas(ruta.colegio)
    if ruta.sentido == 'desde_colegio':
        # Parte en el colegio; tras cada entrega, se sigue desde esa casa.
        entregados = set(ruta.estudiantes_entregados.values_list('id', flat=True))
        ultima_casa = next(
            (_coordenadas(e) for e in reversed(hechos) if e.id in entregados and _coordenadas(e)), None,
        )
        # Al reincorporar a un niño se fijó la posición del furgón: no se sigue su GPS en vivo.
        origen_fijado = _coordenadas(ruta, 'origen_recalculo_latitud', 'origen_recalculo_longitud')
        origen, destino = origen_fijado or ultima_casa or establecimiento, None
    else:
        gps = _coordenadas(ruta, 'ultima_latitud', 'ultima_longitud') if ruta.estado == 'en_ruta' else None
        origen, destino = gps, establecimiento

    clave = (tuple(e.id for e in pendientes), origen, destino)
    cache = getattr(ruta, '_orden_paradas_cache', None)
    if cache and cache[0] == clave:
        return hechos + cache[1] + vuelven + ausentes_por_aviso

    con_ubicacion = [(e, _coordenadas(e)) for e in pendientes if _coordenadas(e)]
    sin_ubicacion = [e for e in pendientes if not _coordenadas(e)]
    ordenados = ordenar_paradas(con_ubicacion, origen=origen, destino=destino) + sin_ubicacion
    ruta._orden_paradas_cache = (clave, ordenados)
    return hechos + ordenados + vuelven + ausentes_por_aviso
