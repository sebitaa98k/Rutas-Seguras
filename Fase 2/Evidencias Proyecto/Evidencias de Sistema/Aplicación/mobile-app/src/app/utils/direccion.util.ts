import { normalizarTexto } from './chile-territorio';

export interface CoincidenciaConPartes {
  nombreCompleto: string;
  calle?: string;
  numero?: string;
  comuna?: string;
}

// Número de casa al final del tramo de la calle, con depto/casa/block opcional.
// Ej: "Av. Matta 1234", "Matta #1234 depto 502", "Los Aromos N° 55 casa B".
const NUMERACION_FINAL = /(?:^|\s)(?:n[°º]?\.?\s*|#\s*)?(\d{1,6}[a-z]?)((?:\s*[,-]?\s*(?:depto|dpto|departamento|depart\.?|casa|block|blk|torre|of|oficina|piso|local|parcela|lote)\.?\s*[\w-]+)*)\s*$/i;

const DETALLE_INTERIOR = /^(?:depto|dpto|departamento|depart\.?|casa|block|blk|torre|of|oficina|piso|local|parcela|lote)\b/i;

/**
 * Extrae la numeración (y depto/casa si viene) que el usuario escribió en la
 * primera parte de la dirección, antes de la primera coma.
 */
export function extraerNumeracion(direccionEscrita: string): string {
  const [tramoCalle = '', ...otrosTramos] = (direccionEscrita || '').split(',').map(t => t.trim());
  if (!tramoCalle) return '';

  let numeracion = '';
  const exacta = tramoCalle.match(NUMERACION_FINAL);
  if (exacta) {
    numeracion = `${exacta[1]}${exacta[2] ? ' ' + exacta[2].replace(/^[\s,-]+/, '') : ''}`.trim();
  } else {
    // Ej: "Matta 1234 Santiago" (sin coma): se toma el último número del tramo.
    const numeros = tramoCalle.match(/(?:^|\s)#?(\d{1,6}[a-z]?)(?=\s|$)/gi);
    if (numeros?.length) {
      numeracion = numeros[numeros.length - 1].replace(/[\s#]/g, '');
    }
  }
  if (!numeracion) return '';

  // Ej: "Matta 1234, depto 502, Santiago": el depto se escribió en otro tramo.
  const interior = otrosTramos.filter(t => DETALLE_INTERIOR.test(t));
  return [numeracion, ...interior].join(' ');
}

/**
 * Arma "calle número" al elegir una coincidencia del buscador, sin perder la
 * numeración escrita por el usuario (el servicio de mapas suele ubicar solo la calle).
 * La comuna y la región se guardan en campos aparte.
 */
export function combinarDireccion(direccionEscrita: string, coincidencia: CoincidenciaConPartes): string {
  const numeracion = extraerNumeracion(direccionEscrita);
  const calle = (coincidencia.calle || '').trim();
  if (!calle) {
    // Sin calle reconocida se respeta lo que escribió el usuario.
    return (direccionEscrita || '').split(',')[0].trim() || coincidencia.nombreCompleto.split(',')[0].trim();
  }
  return numeracion ? `${calle} ${numeracion}` : calle;
}

/** Deja primero las coincidencias que pertenecen a la comuna elegida. */
export function ordenarPorComuna<T extends CoincidenciaConPartes>(coincidencias: T[], comuna: string): T[] {
  const buscada = normalizarTexto(comuna);
  if (!buscada) return coincidencias;
  const esDeLaComuna = (c: T) =>
    normalizarTexto(c.comuna) === buscada || normalizarTexto(c.nombreCompleto).includes(buscada);
  return [...coincidencias.filter(esDeLaComuna), ...coincidencias.filter(c => !esDeLaComuna(c))];
}
