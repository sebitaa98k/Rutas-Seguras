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
