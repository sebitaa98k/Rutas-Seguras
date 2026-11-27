import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export type RutaEstado = 'activa' | 'en_ruta' | 'finalizada' | 'inactiva';
export type RutaSentido = 'hacia_colegio' | 'desde_colegio';

export interface Ruta {
  id?: number | string;
  nombre: string;
  conductor?: string;
  conductor_id?: number | null;
  conductor_nombre?: string;
  colegio: number;
  colegio_nombre?: string;
  sede: number | null;
  sede_nombre?: string;
  furgon: number;
  furgon_patente?: string;
  estudiantes: number[];
  estudiantes_count?: number;
  estudiantesCount?: number;
  paradas?: Array<{
    estudiante_id: number;
    estudiante_nombre: string;
    direccion: string;
    latitud?: number | string;
    longitud?: number | string;
    ubicacion_confirmada?: boolean;
  }>;
  sentido: RutaSentido;
  origen_direccion?: string;
  destino_direccion?: string;
  origen_latitud?: number | string;
  origen_longitud?: number | string;
  destino_latitud?: number | string;
  destino_longitud?: number | string;
  sede_direccion?: string;
  sede_latitud?: number | string;
  sede_longitud?: number | string;
  puntos_recorrido?: Array<{
    tipo: 'estudiante' | 'sede' | 'colegio';
    id: number;
    nombre: string;
    direccion: string;
    latitud: number | string;
    longitud: number | string;
  }>;
  /** Lo que le falta recorrer al furgón, en orden. Vacío si la ruta no está en curso. */
  puntos_trazado?: Array<{ latitud: number | string; longitud: number | string }>;
  estado: RutaEstado;
  hora_programada?: string | null;
  iniciada_en?: string | null;
  finalizada_en?: string | null;
  ultima_latitud?: number | string | null;
  ultima_longitud?: number | string | null;
  precision_gps_metros?: number | string | null;
  ubicacion_actualizada_en?: string | null;
  /** La ruta se puede simular (solo en modo demostración). */
  simulacion_activa?: boolean;
  /** El servidor está en modo demostración: existe el simulador. */
  modo_demostracion?: boolean;
}

export interface TrazadoRuta {
  distanciaMetros: number;
  duracionSegundos: number;
  puntosRuta: [number, number][];
}

export interface RutaOperacionResponse {
  message: string;
  ruta: Ruta;
  notificados: number;
}

@Injectable({ providedIn: 'root' })
export class RutasService {
  private readonly apiUrl = `${environment.apiBaseUrl}/rutas-admin/`;
  private readonly operacionesUrl = `${environment.apiBaseUrl}/rutas/`;
  private readonly geoApiUrl = environment.routingApiBaseUrl;

  constructor(private http: HttpClient) {}

  getRutas(): Observable<Ruta[]> {
    return this.http.get<Ruta[]>(this.apiUrl);
  }

  getRuta(id: string | number): Observable<Ruta> {
    return this.http.get<Ruta>(`${this.apiUrl}${id}/`);
  }

  crearRuta(ruta: Ruta): Observable<Ruta> {
    return this.http.post<Ruta>(this.apiUrl, ruta);
  }

  actualizarRuta(id: string | number, ruta: Ruta): Observable<Ruta> {
    return this.http.put<Ruta>(`${this.apiUrl}${id}/`, ruta);
  }

  eliminarRuta(id: string | number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}${id}/`);
  }

  iniciarRuta(id: string | number): Observable<RutaOperacionResponse> {
    return this.http.post<RutaOperacionResponse>(`${this.operacionesUrl}iniciar/`, { ruta_id: id });
  }

  cambiarSimulacion(id: string | number, activa: boolean): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}${id}/simulacion/`, { activa });
  }

  finalizarRuta(id: string | number): Observable<RutaOperacionResponse> {
    return this.http.post<RutaOperacionResponse>(`${this.operacionesUrl}finalizar/`, { ruta_id: id });
  }

  /** Trazado por calles (OSRM) a través de la Geo API; puntos en orden de recorrido. */
  trazarRecorrido(puntos: Array<{ latitud: number; longitud: number }>): Observable<TrazadoRuta> {
    const params = new HttpParams().set(
      'puntos',
      puntos.map(punto => `${punto.longitud},${punto.latitud}`).join(';')
    );
    return this.http.get<TrazadoRuta>(`${this.geoApiUrl}/ruta`, { params });
  }
}
