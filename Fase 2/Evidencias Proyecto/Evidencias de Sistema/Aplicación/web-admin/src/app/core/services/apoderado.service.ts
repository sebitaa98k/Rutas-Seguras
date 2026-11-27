import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface Estudiante {
  id?: number;
  apoderado_id?: number;
  rut: string;
  nombre?: string;
  apellido?: string;
  /** Lo arma el servidor al listar; al registrar se envían nombre y apellido por separado. */
  nombre_completo?: string;
  fecha_nacimiento?: string;
  curso?: string;
  colegio?: string;
  direccion_retiro?: string;
  comuna?: string;
  region?: string;
  latitud?: number;
  longitud?: number;
  foto_referencial?: string;
  dato_biometrico_huella?: string;
  estado_matricula?: 'pendiente' | 'aprobado' | 'rechazado';
  activo?: boolean;
  tiene_biometria?: boolean;
  /** Su apoderado autorizó el reconocimiento facial. Si no, sube y baja con QR o con el inspector. */
  biometria_autorizada?: boolean;
}

export interface Apoderado {
  id: number;
  perfil_id?: number;
  usuario: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  rut: string;
  nombre_completo: string;
  telefono: string;
  password?: string;
  estudiantes?: Estudiante[];
  /** Colegio dueño: el primero que lo registró y el único que edita su nombre, correo y teléfono. */
  colegio_id?: number;
  colegio_nombre?: string;
  /** Todos sus colegios (puede tener hijos en más de uno). */
  colegios_vinculados?: { id: number; nombre: string; es_dueno: boolean }[];
}

/** Estudiante que el colegio autorizó para que su apoderado lo inscriba desde la app. */
export interface EstudianteHabilitado {
  id: number;
  rut: string;
  rut_apoderado: string;
  colegio_id: number;
  colegio_nombre: string;
  estado: 'disponible' | 'usado';
  estudiante: { id: number; nombre: string } | null;
  apoderado: { nombre: string; email: string } | null;
  creado_en: string;
  usado_en: string | null;
}

export interface ResultadoCargaEstudiantes {
  message: string;
  agregados: number;
  cuentas_vinculadas: number;
  repetidos: string[];
  en_otro_colegio: string[];
  ya_registrados: string[];
  /** El RUT del estudiante o del apoderado ya se usa con otro rol (en cualquier colegio). */
  en_otro_rol?: string[];
  formato_invalido: string[];
}

export interface RutHabilitado {
  id: number;
  rut: string;
  colegio_id: number;
  colegio_nombre: string;
  estado: 'disponible' | 'usado';
  cuenta: { nombre: string; email: string; telefono: string; estudiantes: number } | null;
  usado_en: string | null;
  creado_en: string;
  liberado_en: string | null;
  cuenta_liberada: string;
}

export interface ResultadoCargaRuts {
  message: string;
  agregados: number;
  cuentas_vinculadas: number;
  repetidos: string[];
  formato_invalido: string[];
  en_otro_rol?: string[];
}

@Injectable({
  providedIn: 'root'
})
export class ApoderadoService {
  private readonly apiUrl = `${environment.apiBaseUrl}/apoderados/`;
  private readonly baseUrl = `${environment.apiBaseUrl}/`;

  constructor(private http: HttpClient) {}

  getApoderados(): Observable<Apoderado[]> {
    return this.http.get<Apoderado[]>(this.apiUrl);
  }

  getApoderadoById(id: number): Observable<Apoderado> {
    return this.http.get<Apoderado>(`${this.apiUrl}${id}/`);
  }

  crearApoderado(apoderadoData: {
    nombre: string;
    apellido: string;
    first_name?: string;
    last_name?: string;
    rut: string;
    usuario: string;
    telefono: string;
    password?: string;
    estudiantes?: Estudiante[];
    /** El RUT ya tiene cuenta en otro colegio: vincularla a este en vez de crear otra. */
    vincular?: boolean;
  }): Observable<any> {
    return this.http.post<any>(this.apiUrl, apoderadoData);
  }

  actualizarApoderado(id: number, apoderadoData: Partial<Apoderado>): Observable<any> {
    return this.http.patch<any>(`${this.apiUrl}${id}/`, apoderadoData);
  }

  deleteApoderado(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}${id}/`);
  }

  getRutsHabilitados(buscar: string, estado: string): Observable<{ limite: number; ruts: RutHabilitado[] }> {
    let params = new HttpParams();
    if (buscar.trim()) params = params.set('buscar', buscar.trim());
    if (estado) params = params.set('estado', estado);
    return this.http.get<{ limite: number; ruts: RutHabilitado[] }>(`${this.apiUrl}ruts-habilitados/`, { params });
  }

  agregarRutsHabilitados(ruts: string): Observable<ResultadoCargaRuts> {
    return this.http.post<ResultadoCargaRuts>(`${this.apiUrl}ruts-habilitados/`, { ruts });
  }

  eliminarRutHabilitado(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}ruts-habilitados/${id}/`);
  }

  liberarRutHabilitado(id: number): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}ruts-habilitados/${id}/liberar/`, {});
  }

  getEstudiantesHabilitados(buscar: string, estado: string): Observable<{ limite: number; estudiantes: EstudianteHabilitado[] }> {
    let params = new HttpParams();
    if (buscar.trim()) params = params.set('buscar', buscar.trim());
    if (estado) params = params.set('estado', estado);
    return this.http.get<{ limite: number; estudiantes: EstudianteHabilitado[] }>(
      `${this.apiUrl}estudiantes-habilitados/`, { params }
    );
  }

  /** Una línea por estudiante: "RUT apoderado, RUT estudiante". */
  habilitarEstudiantes(pares: string): Observable<ResultadoCargaEstudiantes> {
    return this.http.post<ResultadoCargaEstudiantes>(`${this.apiUrl}estudiantes-habilitados/`, { pares });
  }

  quitarEstudianteHabilitado(id: number): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}estudiantes-habilitados/${id}/`);
  }

  registrarBiometriaEstudiante(estudianteId: number, file: File): Observable<any> {
    const formData = new FormData();
    formData.append('foto', file);
    return this.http.post<any>(`${this.baseUrl}estudiantes/${estudianteId}/registrar-rostro/`, formData);
  }
}
