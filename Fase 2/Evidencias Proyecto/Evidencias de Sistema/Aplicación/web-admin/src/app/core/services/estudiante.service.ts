import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom, Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface Estudiante {
  id: number;
  nombre: string;
  apellido: string;
  nombre_completo?: string;
  rut: string;
  fecha_nacimiento?: string;
  colegio?: number;
  colegio_nombre?: string;
  sede?: number;
  sede_nombre?: string;
  curso?: string;
  direccion_principal?: string;
  comuna?: string;
  region?: string;
  /** Calle y número, comuna y región en un solo texto (solo lectura). */
  direccion_completa?: string;
  latitud?: number | string | null;
  longitud?: number | string | null;
  ubicacion_confirmada?: boolean;
  direccion_alternativa?: string;
  persona_autorizada?: string;
  rut_persona_autorizada?: string;
  /** Quienes pueden retirarlo además del apoderado; no incluye inspectores. */
  personas_autorizadas?: { nombre: string; rut: string }[];
  /** Inspectores responsables del colegio o sede del estudiante. */
  inspectores?: string[];
  foto?: string;
  tiene_foto?: boolean;
  tiene_biometria?: boolean;
  /** Su apoderado autorizó el reconocimiento facial. Si no, sube y baja con QR o con el inspector. */
  biometria_autorizada?: boolean;
  datos_entrega_completos?: boolean;
  tiene_conductor_operacional?: boolean;
  apoderado?: number;
  apoderado_nombre?: string;
  apoderado_telefono?: string;
  conductor?: number;
  conductor_id?: number;
  conductor_nombre?: string;
  created_at?: string;
  updated_at?: string;
}

@Injectable({
  providedIn: 'root'
})
export class EstudianteService {
  private readonly apiUrl = environment.apiBaseUrl;

  private estudiantesListSignal = signal<Estudiante[]>([]);
  public readonly estudiantesList = this.estudiantesListSignal.asReadonly();

  constructor(private http: HttpClient) {}

  public async getEstudiantes(): Promise<Estudiante[]> {
    try {
      const data = await firstValueFrom(
        this.http.get<Estudiante[]>(`${this.apiUrl}/estudiantes/`)
      );
      this.estudiantesListSignal.set(data || []);
      return data || [];
    } catch (error) {
      console.error('Error al cargar estudiantes:', error);
      return [];
    }
  }

  public getEstudianteById(id: number): Observable<Estudiante> {
    return this.http.get<Estudiante>(`${this.apiUrl}/estudiantes/${id}/`);
  }

  public createEstudiante(data: Partial<Estudiante>): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/estudiantes/`, data);
  }

  public updateEstudiante(id: number, data: Partial<Estudiante>): Observable<any> {
    return this.http.patch<any>(`${this.apiUrl}/estudiantes/${id}/`, data);
  }

  public deleteEstudiante(id: number): Observable<any> {
    return this.http.delete<any>(`${this.apiUrl}/estudiantes/${id}/`);
  }
}
