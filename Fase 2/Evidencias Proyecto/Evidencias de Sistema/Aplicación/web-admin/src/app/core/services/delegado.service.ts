import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface DelegadoEstudiante {
  id: number;
  rut: string;
  nombre: string;
  apellido: string;
  nombre_completo: string;
  colegio?: number | string;
  colegio_nombre?: string;
  curso?: string;
  direccion_principal?: string;
  persona_autorizada?: string;
  rut_persona_autorizada?: string;
  apoderado_nombre?: string;
  apoderado_telefono?: string;
  conductor_nombre?: string;
  conductor_telefono?: string;
}

export interface Delegado {
  id: number;
  usuario: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  rut: string;
  nombre_completo: string;
  telefono: string;
  rol?: string;
  tipo_delegado?: 'autorizado' | 'inspector';
  estudiantes?: DelegadoEstudiante[];
  sedes_responsable?: { id: number; nombre: string; colegio_id: number }[];
}

@Injectable({
  providedIn: 'root'
})
export class DelegadoService {
  private readonly apiUrl = `${environment.apiBaseUrl}/delegados/`;

  constructor(private http: HttpClient) {}

  getDelegados(): Observable<Delegado[]> {
    return this.http.get<Delegado[]>(this.apiUrl);
  }

  getDelegadoById(id: number): Observable<Delegado> {
    return this.http.get<Delegado>(`${this.apiUrl}${id}/`);
  }

  crearDelegado(delegadoData: {
    nombre: string;
    apellido?: string;
    rut: string;
    email: string;
    telefono?: string;
    password?: string;
    tipo_delegado?: 'autorizado' | 'sede';
    sede_id?: number | null;
  }): Observable<any> {
    return this.http.post<any>(this.apiUrl, delegadoData);
  }

  actualizarDelegado(id: number, delegadoData: Partial<Delegado>): Observable<any> {
    return this.http.patch<any>(`${this.apiUrl}${id}/`, delegadoData);
  }

  deleteDelegado(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}${id}/`);
  }

  desvincularEstudiante(estudianteId: number, delegadoId: number): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}desvincular-estudiante/`, {
      estudiante_id: estudianteId,
      delegado_id: delegadoId
    });
  }
}
