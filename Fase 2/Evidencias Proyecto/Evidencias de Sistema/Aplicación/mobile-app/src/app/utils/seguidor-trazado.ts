import * as L from 'leaflet';
import { Observable, Subscription } from 'rxjs';

import { Coordenada, trazadoRestante, ubicarConRespaldo } from './trazado.util';

export interface PuntoTrazado {
  latitud: number;
  longitud: number;
}

export interface PosicionFurgon extends PuntoTrazado {
  /** Precisión del GPS en metros, si se conoce. */
  precision?: number | null;
}

export type TrazarRuta = (puntos: PuntoTrazado[]) => Observable<{ puntosRuta: [number, number][] }>;

/** Distancia al trazado desde la que se considera que el furgón tomó otro camino. */
const DESVIO_MAXIMO_METROS = 50;
/** Lecturas del GPS menos precisas que esto no cuentan como desvío. */
const PRECISION_GPS_MAXIMA_METROS = 40;
/** Evita pedir trazados nuevos seguidos al servicio de rutas. */
const ESPERA_ENTRE_RECALCULOS_MS = 15000;

/**
 * Línea del recorrido que sigue al furgón, igual que en la app del conductor: parte en su posición,
 * borra lo ya recorrido y se recalcula si el furgón se sale del camino.
 */
export class SeguidorTrazado {
  private mapa?: L.Map;
  private capa?: L.Polyline;
  private trazado: Coordenada[] = [];
  private indice = 0;
  private destinos: PuntoTrazado[] = [];
  private firmaDestinos = '';
  private dibujadoSinGps = false;
  private solicitud?: Subscription;
  private ultimoRecalculoMs = 0;

  constructor(private readonly trazar: TrazarRuta, private readonly estilo: L.PolylineOptions) {}

  /**
   * Se llama con cada actualización de la ruta. `alDibujar` se ejecuta cuando cambian las paradas,
   * para que la pantalla ajuste la vista.
   */
  actualizar(mapa: L.Map, destinos: PuntoTrazado[], furgon: PosicionFurgon | null, alDibujar?: () => void): void {
    if (mapa !== this.mapa) {
      this.destruir();
      this.mapa = mapa;
    }
    const firma = destinos.map(punto => `${punto.latitud},${punto.longitud}`).join('|');
    if (!destinos.length) {
      this.quitarLinea();
      this.firmaDestinos = '';
      return;
    }
    if (firma !== this.firmaDestinos) {
      this.firmaDestinos = firma;
      this.destinos = destinos;
      this.dibujar(furgon, alDibujar);
      return;
    }
    if (!furgon || this.solicitud) return;
    if (this.dibujadoSinGps) {
      this.dibujar(furgon);
      return;
    }
    this.seguir(furgon);
  }

  destruir(): void {
    this.solicitud?.unsubscribe();
    this.solicitud = undefined;
    this.capa?.remove();
    this.capa = undefined;
    this.trazado = [];
    this.indice = 0;
    this.destinos = [];
    this.firmaDestinos = '';
    this.dibujadoSinGps = false;
    this.mapa = undefined;
  }

  get capaLinea(): L.Polyline | undefined {
    return this.capa;
  }

  private seguir(furgon: PosicionFurgon): void {
    if (!this.capa || this.trazado.length < 2) return;
    const posicion = ubicarConRespaldo(this.trazado, [furgon.latitud, furgon.longitud], this.indice, DESVIO_MAXIMO_METROS);
    if (!posicion) return;
    if (posicion.distancia > DESVIO_MAXIMO_METROS) {
      const precisa = (furgon.precision ?? 0) <= PRECISION_GPS_MAXIMA_METROS;
      if (precisa && Date.now() - this.ultimoRecalculoMs >= ESPERA_ENTRE_RECALCULOS_MS) {
        this.dibujar(furgon);
      }
      return;
    }
    this.indice = posicion.indice;
    this.capa.setLatLngs(trazadoRestante(this.trazado, posicion));
  }

  private dibujar(furgon: PosicionFurgon | null, alDibujar?: () => void): void {
    const puntos = [...(furgon ? [{ latitud: furgon.latitud, longitud: furgon.longitud }] : []), ...this.destinos];
    this.solicitud?.unsubscribe();
    if (puntos.length < 2) {
      this.solicitud = undefined;
      this.quitarLinea();
      alDibujar?.();
      return;
    }
    this.ultimoRecalculoMs = Date.now();
    const mapa = this.mapa;
    this.solicitud = this.trazar(puntos).subscribe({
      next: respuesta => {
        this.solicitud = undefined;
        if (!this.mapa || this.mapa !== mapa) return;
        this.trazado = respuesta.puntosRuta;
        this.indice = 0;
        this.dibujadoSinGps = !furgon;
        if (this.capa) {
          this.capa.setLatLngs(respuesta.puntosRuta);
        } else {
          this.capa = L.polyline(respuesta.puntosRuta, this.estilo).addTo(this.mapa);
        }
        alDibujar?.();
      },
      error: err => {
        this.solicitud = undefined;
        // Si falla, no se reintenta en cada lectura: queda la regla de desvío, con su espera.
        this.dibujadoSinGps = false;
        console.error('No fue posible trazar la ruta por calles:', err);
        alDibujar?.();
      }
    });
  }

  private quitarLinea(): void {
    this.capa?.remove();
    this.capa = undefined;
    this.trazado = [];
    this.indice = 0;
  }
}
