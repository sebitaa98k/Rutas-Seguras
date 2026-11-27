import { Injectable, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom, Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

/** Básico y Estándar tienen una sola sede (oculta). Avanzado es multisede. */
export type PlanColegio = 'basico' | 'estandar' | 'avanzado';

export const PLANES_COLEGIO: { valor: PlanColegio; nombre: string; detalle: string }[] = [
  { valor: 'basico', nombre: 'Básico', detalle: 'Hasta 150 estudiantes · una sede' },
  { valor: 'estandar', nombre: 'Estándar', detalle: '151 a 500 estudiantes · una sede' },
  { valor: 'avanzado', nombre: 'Avanzado', detalle: 'Más de 500 estudiantes · multisede' },
];

export interface Colegio {
  id: number;
  nombre: string;
  rbd?: string;
  plan?: PlanColegio;
  plan_nombre?: string;
  /** Solo los colegios multisede muestran y administran sedes. */
  es_multisede?: boolean;
  direccion?: string;
  comuna?: string;
  region?: string;
  latitud?: number | string | null;
  longitud?: number | string | null;
  telefono?: string;
  email_contacto?: string;
  activo: boolean;
  total_estudiantes?: number;
  total_conductores?: number;
  total_sedes?: number;
  created_at?: string;
  updated_at?: string;
}

export interface Sede {
  id: number;
  colegio: number;
  colegio_nombre?: string;
  nombre: string;
  direccion?: string;
  comuna?: string;
  region?: string;
  latitud?: number | null;
  longitud?: number | null;
  telefono?: string;
  activa: boolean;
  /** Se crea con el colegio y copia sus datos (dirección, ubicación y teléfono). */
  es_principal?: boolean;
  /** Colegio que no es multisede: la sede existe, pero no se muestra. */
  oculta?: boolean;
  created_at?: string;
  updated_at?: string;
  /** Inspectores de la sede: puede tener varios. */
  inspectores?: { id: number; nombre: string; rut?: string }[];
}

export interface CoincidenciaGeo {
  latitud: number;
  longitud: number;
  nombreCompleto: string;
  calle?: string;
  numero?: string;
  comuna?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ColegioService {
  private readonly apiUrl = environment.apiBaseUrl;
  private readonly geoApiUrl = `${this.apiUrl}/geo`;
  private readonly SELECTED_COLEGIO_KEY = 'rutas_seguras_selected_colegio';

  private selectedColegioIdSignal = signal<number | null>(this.getStoredSelectedColegio());
  public readonly selectedColegioId = this.selectedColegioIdSignal.asReadonly();

  private colegiosListSignal = signal<Colegio[]>([]);
  public readonly colegiosList = this.colegiosListSignal.asReadonly();

  constructor(private http: HttpClient) {}

  private getStoredSelectedColegio(): number | null {
    try {
      const stored = localStorage.getItem(this.SELECTED_COLEGIO_KEY);
      if (stored) {
        const parsed = parseInt(stored, 10);
        return isNaN(parsed) ? null : parsed;
      }
    } catch (error) {
      console.error('Error al recuperar colegio seleccionado:', error);
    }
    return null;
  }

  public setSelectedColegioId(id: number | null): void {
    // Un valor que no es un id válido se trata como "Todos los colegios".
    if (id !== null && !Number.isInteger(id)) id = null;
    this.selectedColegioIdSignal.set(id);
    if (id !== null) {
      localStorage.setItem(this.SELECTED_COLEGIO_KEY, String(id));
    } else {
      localStorage.removeItem(this.SELECTED_COLEGIO_KEY);
    }
  }

  public async getColegios(soloActivos?: boolean): Promise<Colegio[]> {
    try {
      const url = soloActivos ? `${this.apiUrl}/colegios/?solo_activos=true` : `${this.apiUrl}/colegios/`;
      const colegios = await firstValueFrom(
        this.http.get<Colegio[]>(url)
      );
      if (!soloActivos) {
        this.colegiosListSignal.set(colegios || []);
        const seleccionado = this.selectedColegioIdSignal();
        if (seleccionado !== null && !colegios.some(colegio => colegio.id === seleccionado)) {
          this.setSelectedColegioId(null);
        }
      }
      return colegios || [];
    } catch (error) {
      console.error('Error al obtener colegios:', error);
      if (!soloActivos) {
        this.colegiosListSignal.set([]);
      }
      throw error;
    }
  }

  public getColegio(id: number): Observable<Colegio> {
    return this.http.get<Colegio>(`${this.apiUrl}/colegios/${id}/`);
  }

  public createColegio(colegioData: Partial<Colegio>): Observable<Colegio> {
    return this.http.post<Colegio>(`${this.apiUrl}/colegios/`, colegioData);
  }

  public updateColegio(id: number, colegioData: Partial<Colegio>): Observable<Colegio> {
    return this.http.patch<Colegio>(`${this.apiUrl}/colegios/${id}/`, colegioData);
  }

  public deleteColegio(id: number): Observable<any> {
    return this.http.delete<any>(`${this.apiUrl}/colegios/${id}/`);
  }

  public buscarDirecciones(query: string, limite = 6): Observable<{ total: number; coincidencias: CoincidenciaGeo[] }> {
    const params = new HttpParams().set('query', query.trim()).set('limite', limite);
    return this.http.get<{ total: number; coincidencias: CoincidenciaGeo[] }>(
      `${this.geoApiUrl}/coincidencias/`,
      { params }
    );
  }

  // Sedes
  public getSedes(colegioId: number): Observable<Sede[]> {
    return this.http.get<Sede[]>(`${this.apiUrl}/colegios/${colegioId}/sedes/`);
  }

  public createSede(colegioId: number, sedeData: Partial<Sede>): Observable<Sede> {
    return this.http.post<Sede>(`${this.apiUrl}/colegios/${colegioId}/sedes/`, sedeData);
  }

  public updateSede(id: number, sedeData: Partial<Sede>): Observable<Sede> {
    return this.http.patch<Sede>(`${this.apiUrl}/sedes/${id}/`, sedeData);
  }

  public deleteSede(id: number): Observable<any> {
    return this.http.delete<any>(`${this.apiUrl}/sedes/${id}/`);
  }

  // Administradores de Colegio
  public getAdministradoresColegio(colegioId: number): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/colegios/${colegioId}/administradores/`);
  }

  public createAdministradorColegio(colegioId: number, adminData: { nombre: string; apellido: string; email: string; password: string }): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/colegios/${colegioId}/administradores/`, adminData);
  }

  /** Solo el administrador de plataforma. La contraseña es opcional: si se envía, debe cambiarla al ingresar. */
  public updateAdministradorColegio(
    colegioId: number,
    usuarioId: number,
    adminData: { nombre: string; apellido: string; email: string; password?: string }
  ): Observable<any> {
    return this.http.patch<any>(`${this.apiUrl}/colegios/${colegioId}/administradores/${usuarioId}/`, adminData);
  }
}

/**
 * Colegio que no es multisede: tiene una sola sede, que no se muestra. Los formularios la usan
 * sin pedirla. Devuelve null si el colegio es multisede.
 */
export function sedeUnicaOculta(sedes: Sede[]): Sede | null {
  return sedes.length === 1 && sedes[0].oculta ? sedes[0] : null;
}
