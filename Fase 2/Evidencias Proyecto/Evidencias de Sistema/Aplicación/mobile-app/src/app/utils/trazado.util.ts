export type Coordenada = [number, number];

export interface PosicionEnTrazado {
  /** Tramo del trazado (entre el punto `indice` y el siguiente) donde está el furgón. */
  indice: number;
  /** Punto del tramo más cercano al furgón. */
  punto: Coordenada;
  /** Distancia en metros entre el furgón y el trazado. */
  distancia: number;
}

const METROS_POR_GRADO = 111_320;
/** Hasta dónde se busca hacia adelante: evita saltar a un tramo posterior que pasa por la misma calle. */
const BUSQUEDA_ADELANTE_METROS = 500;

/** Proyección plana alrededor de `referencia`: precisa para distancias de pocos kilómetros. */
function enMetros(punto: Coordenada, referencia: Coordenada): [number, number] {
  const factor = Math.cos((referencia[0] * Math.PI) / 180);
  return [
    (punto[1] - referencia[1]) * METROS_POR_GRADO * factor,
    (punto[0] - referencia[0]) * METROS_POR_GRADO
  ];
}

/**
 * Ubica al furgón sobre el trazado, buscando solo desde el tramo en que ya iba hacia adelante,
 * para que la línea recorrida no vuelva a aparecer.
 */
export function ubicarEnTrazado(
  trazado: Coordenada[],
  posicion: Coordenada,
  desde: number,
  alcanceMetros = BUSQUEDA_ADELANTE_METROS
): PosicionEnTrazado | null {
  let mejor: PosicionEnTrazado | null = null;
  let recorrido = 0;

  for (let i = Math.max(0, desde); i < trazado.length - 1; i++) {
    const inicio = trazado[i];
    const fin = trazado[i + 1];
    const [fx, fy] = enMetros(fin, inicio);
    const [px, py] = enMetros(posicion, inicio);
    const largo2 = fx * fx + fy * fy;
    const t = largo2 === 0 ? 0 : Math.min(1, Math.max(0, (px * fx + py * fy) / largo2));
    const distancia = Math.hypot(px - t * fx, py - t * fy);

    if (!mejor || distancia < mejor.distancia) {
      mejor = {
        indice: i,
        punto: [inicio[0] + t * (fin[0] - inicio[0]), inicio[1] + t * (fin[1] - inicio[1])],
        distancia
      };
    }

    recorrido += Math.sqrt(largo2);
    if (recorrido > alcanceMetros) break;
  }
  return mejor;
}

/**
 * Como `ubicarEnTrazado`, pero si el furgón avanzó más que el tramo revisado (por ejemplo, porque la
 * pantalla se actualiza cada varios segundos), lo busca en todo lo que queda antes de darlo por desviado.
 */
export function ubicarConRespaldo(
  trazado: Coordenada[],
  posicion: Coordenada,
  desde: number,
  desvioMaximoMetros: number
): PosicionEnTrazado | null {
  const cercana = ubicarEnTrazado(trazado, posicion, desde);
  if (cercana && cercana.distancia <= desvioMaximoMetros) return cercana;
  const lejana = ubicarEnTrazado(trazado, posicion, desde, Number.POSITIVE_INFINITY);
  return lejana && lejana.distancia <= desvioMaximoMetros ? lejana : cercana;
}

/** La línea que queda por recorrer, empezando en la posición del furgón. */
export function trazadoRestante(trazado: Coordenada[], posicion: PosicionEnTrazado): Coordenada[] {
  return [posicion.punto, ...trazado.slice(posicion.indice + 1)];
}

/** Distancia aproximada en metros entre dos puntos cercanos. */
export function distanciaMetros(a: Coordenada, b: Coordenada): number {
  const [x, y] = enMetros(b, a);
  return Math.hypot(x, y);
}

export interface LlegadaEnTrazado {
  /** Metros que faltan por el camino hasta el punto del trazado más cercano a la parada. */
  metros: number;
  punto: Coordenada;
  indice: number;
}

/** Tolerancia para elegir la primera pasada del trazado junto a la parada y no una posterior. */
const TOLERANCIA_PUNTO_PARADA_METROS = 3;

/**
 * Cuánto falta, siguiendo el trazado, para llegar a la parada. Se mide por el camino y no en línea
 * recta: si el furgón pasa por el otro lado de una avenida, aún le falta la vuelta en U.
 */
export function distanciaHastaParada(
  trazado: Coordenada[],
  desde: PosicionEnTrazado,
  parada: Coordenada
): LlegadaEnTrazado | null {
  const candidatos: { distancia: number; punto: Coordenada; indice: number; metros: number }[] = [];
  let actual = desde.punto;
  let recorrido = 0;
  for (let i = Math.max(0, desde.indice); i < trazado.length - 1; i++) {
    const fin = trazado[i + 1];
    const [fx, fy] = enMetros(fin, actual);
    const [px, py] = enMetros(parada, actual);
    const largo2 = fx * fx + fy * fy;
    const t = largo2 === 0 ? 0 : Math.min(1, Math.max(0, (px * fx + py * fy) / largo2));
    candidatos.push({
      distancia: Math.hypot(px - t * fx, py - t * fy),
      punto: [actual[0] + t * (fin[0] - actual[0]), actual[1] + t * (fin[1] - actual[1])],
      indice: i,
      metros: recorrido + t * Math.sqrt(largo2)
    });
    recorrido += Math.sqrt(largo2);
    actual = fin;
  }
  if (!candidatos.length) return null;
  const minima = Math.min(...candidatos.map(c => c.distancia));
  const elegido = candidatos.find(c => c.distancia <= minima + TOLERANCIA_PUNTO_PARADA_METROS)!;
  return { metros: elegido.metros, punto: elegido.punto, indice: elegido.indice };
}

export interface Avance {
  punto: Coordenada;
  indice: number;
  /** Se llegó al final del trazado. */
  alFinal: boolean;
}

/** Avanza `metros` por el trazado desde `punto`, que está en el tramo `indice`. Lo usa el simulador de ruta. */
export function avanzarSobreTrazado(trazado: Coordenada[], indice: number, punto: Coordenada, metros: number): Avance {
  let actual = punto;
  let restante = metros;
  for (let i = Math.max(0, indice); i < trazado.length - 1; i++) {
    const fin = trazado[i + 1];
    const largo = distanciaMetros(actual, fin);
    if (largo >= restante) {
      const t = largo === 0 ? 0 : restante / largo;
      return {
        punto: [actual[0] + t * (fin[0] - actual[0]), actual[1] + t * (fin[1] - actual[1])],
        indice: i,
        alFinal: false
      };
    }
    restante -= largo;
    actual = fin;
  }
  return { punto: trazado[trazado.length - 1], indice: Math.max(0, trazado.length - 2), alFinal: true };
}
