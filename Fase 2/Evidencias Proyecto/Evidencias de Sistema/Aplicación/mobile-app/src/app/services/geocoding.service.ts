import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface CoincidenciaDireccion {
  latitud: number;
  longitud: number;
  nombreCompleto: string;
  calle?: string;
  numero?: string;
  comuna?: string;
}

export interface CoincidenciasResponse {
  total: number;
  coincidencias: CoincidenciaDireccion[];
}

export interface PuntoRuta {
  latitud: number;
  longitud: number;
}

export interface RutaGeoResponse {
  distanciaMetros: number;
  duracionSegundos: number;
  puntosRuta: [number, number][];
  puntosAjustados?: Array<{
    latitud: number;
    longitud: number;
    distanciaAjusteMetros: number;
  }>;
}

@Injectable({
  providedIn: 'root'
})
export class GeocodingService {
  private readonly apiUrl = environment.apiUrl;
  private readonly geoApiUrl = environment.geoApiUrl;

  constructor(private http: HttpClient) {}

  buscarDirecciones(query: string, limite = 5): Observable<CoincidenciasResponse> {
    const params = new HttpParams()
      .set('query', query.trim())
      .set('limite', limite);
    return this.http.get<CoincidenciasResponse>(`${this.apiUrl}/geo/coincidencias/`, { params });
  }

  trazarRuta(puntos: PuntoRuta[]): Observable<RutaGeoResponse> {
    const valorPuntos = puntos
      .map(punto => `${punto.longitud},${punto.latitud}`)
      .join(';');

    const params = new HttpParams().set('puntos', valorPuntos);
    return this.http.get<RutaGeoResponse>(`${this.geoApiUrl}/ruta`, { params });
  }
}

