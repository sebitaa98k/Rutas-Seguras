import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface Furgon {
  id?: number | string;
  patente: string;
  marcaModelo?: string;
  marca_modelo?: string;
  capacidad: number;
  /** Conductor real, sacado de las rutas del furgón (no se edita aquí). */
  conductor?: string | null;
  estado: 'disponible' | 'en_ruta' | 'mantenimiento';
  colegio?: number;
  colegio_nombre?: string;
  sede?: number;
  sede_nombre?: string;
}

@Injectable({
  providedIn: 'root'
})
export class FurgonesService {
  private readonly apiUrl = `${environment.apiBaseUrl}/furgones/`;

  constructor(private http: HttpClient) {}

  getFurgones(): Observable<Furgon[]> {
    return this.http.get<Furgon[]>(this.apiUrl);
  }

  getFurgon(id: string | number): Observable<Furgon> {
    return this.http.get<Furgon>(`${this.apiUrl}${id}/`);
  }

  crearFurgon(furgon: Furgon): Observable<Furgon> {
    return this.http.post<Furgon>(this.apiUrl, this.toPayload(furgon));
  }

  actualizarFurgon(id: string | number, furgon: Furgon): Observable<Furgon> {
    return this.http.put<Furgon>(`${this.apiUrl}${id}/`, this.toPayload(furgon));
  }

  eliminarFurgon(id: string | number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}${id}/`);
  }

  private toPayload(furgon: Furgon): Record<string, unknown> {
    const payload: Record<string, unknown> = {
      patente: furgon.patente,
      marca_modelo: furgon.marcaModelo || furgon.marca_modelo || '',
      capacidad: furgon.capacidad,
      estado: furgon.estado
    };
    if (furgon.colegio !== undefined) payload['colegio'] = furgon.colegio;
    if (furgon.sede !== undefined) payload['sede'] = furgon.sede;
    return payload;
  }
}
