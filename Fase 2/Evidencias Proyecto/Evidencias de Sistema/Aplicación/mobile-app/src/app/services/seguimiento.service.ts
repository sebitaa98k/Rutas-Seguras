import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

export interface DondeEsta {
  lugar: 'casa' | 'colegio' | 'furgon' | null;
  detalle: string;
  hora: string | null;
}

export interface Seguimiento {
  estudiante: {
    id: number;
    nombre: string;
    /** Aviso del apoderado: hoy no usa el furgón en este tramo. */
    no_asiste_hoy?: boolean;
    /** Dónde quedó hoy según sus recorridos. `lugar` es null si no hay información. */
    donde_esta?: DondeEsta;
  };
  /** Última ruta del estudiante que terminó hoy, si hubo alguna. */
  ultima_ruta_terminada?: { nombre: string; sentido: 'hacia_colegio' | 'desde_colegio'; hora: string } | null;
  conductor: {
    id: number;
    nombre: string;
    telefono: string | null;
  };
  ruta: {
    id: number;
    nombre: string;
    sentido?: 'hacia_colegio' | 'desde_colegio';
    estado:
      | 'no_iniciada'
      | 'en_camino'
      | 'finalizada'
      | 'pausada';
    puntos_recorrido: Array<{
      tipo: 'estudiante' | 'sede' | 'colegio';
      id: number;
      nombre: string;
      direccion: string;
      latitud: number | string;
      longitud: number | string;
    }>;
    /** Lo que le falta recorrer al furgón, en orden. Vacío si la ruta no está en curso. */
    puntos_trazado?: Array<{ latitud: number | string; longitud: number | string }>;
  };
  ubicacion: {
    latitud: number | null;
    longitud: number | null;
    precision_metros: number | null;
    ultima_actualizacion: string | null;
  };
  llegada_estimada: string | null;
}

@Injectable({
  providedIn: 'root'
})
export class SeguimientoService {
  private apiUrl = environment.apiUrl;

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) { }

  private getAuthHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      'Authorization': token ? `Token ${token}` : '',
      'Content-Type': 'application/json'
    });
  }

  obtenerSeguimiento(estudianteId?: number): Observable<Seguimiento> {
    let params = new HttpParams();
    if (estudianteId != null) {
      params = params.set('estudiante_id', estudianteId.toString());
    }
    return this.http.get<Seguimiento>(
      `${this.apiUrl}/seguimiento/`,
      { headers: this.getAuthHeaders(), params }
    );
  }
}
