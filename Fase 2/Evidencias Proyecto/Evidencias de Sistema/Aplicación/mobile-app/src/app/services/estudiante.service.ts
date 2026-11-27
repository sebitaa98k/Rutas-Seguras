import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

export interface ColegioItem {
  id: number;
  nombre: string;
  rbd?: string;
  activo?: boolean;
}

export interface HabilitacionEstudiante {
  habilitado: boolean;
  rut: string;
  colegio_id: number;
  colegio_nombre: string;
  es_multisede: boolean;
}

export interface SedeItem {
  id: number;
  colegio: number;
  nombre: string;
  activa?: boolean;
  /** Colegio que no es multisede: la sede existe, pero no se muestra. */
  oculta?: boolean;
  latitud?: number | string | null;
  longitud?: number | string | null;
}

export interface Estudiante {
  id?: number;
  nombre: string;
  apellido: string;
  rut: string;
  fecha_nacimiento: string;
  colegio?: string | number;
  colegio_id?: number;
  colegio_nombre?: string;
  sede?: number;
  sede_id?: number;
  sede_nombre?: string;
  curso: string;
  direccion_principal: string;
  comuna?: string;
  region?: string;
  /** Calle y número, comuna y región en un solo texto (solo lectura). */
  direccion_completa?: string;
  /** Aviso de inasistencia del apoderado para hoy. */
  asistencia_hoy?: { no_asiste_ida: boolean; no_asiste_vuelta: boolean };
  latitud?: number | string | null;
  longitud?: number | string | null;
  ubicacion_confirmada?: boolean;
  direccion_alternativa?: string;
  persona_autorizada?: string;
  rut_persona_autorizada?: string;
  tiene_foto?: boolean;
  tiene_biometria?: boolean;
  /** Su apoderado autorizó el reconocimiento facial de ESTE hijo. Si no, sube y baja con QR o con el inspector. */
  biometria_autorizada?: boolean;
  /** Solo al inscribirlo: el apoderado enciende el interruptor de reconocimiento facial. */
  autoriza_biometria?: boolean;
  apoderado_nombre?: string;
  apoderado_telefono?: string;
  conductor?: number;
  conductor_nombre?: string;
  created_at?: string;
  updated_at?: string;
}

export interface EstudianteCreateResponse {
  message: string;
  estudiante: Estudiante;
}

export interface PersonaAutorizada {
  id: number;
  nombre: string;
  rut: string;
  telefono?: string;
  activa: boolean;
  tiene_cuenta: boolean;
}

export type TramoAsistencia = 'ida' | 'vuelta';

export interface EstadoTramoAsistencia {
  no_asiste: boolean;
  tiene_ruta: boolean;
  /** Motivo por el que hoy ya no se puede cambiar (null = se puede). */
  bloqueo: string | null;
}

export interface DiaAsistencia {
  fecha: string;
  etiqueta: string;
  motivo: string;
  ida: EstadoTramoAsistencia;
  vuelta: EstadoTramoAsistencia;
}

export interface EstadoAsistencia {
  estudiante_id: number;
  estudiante_nombre: string;
  dias: DiaAsistencia[];
  message?: string;
}

export interface EstudianteUpdateResponse {
  message: string;
  estudiante: Estudiante;
}

@Injectable({
  providedIn: 'root'
})
export class EstudianteService {

  private apiUrl = environment.apiUrl;

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) { }

  private getAuthHeaders(contentType: 'json' | 'multipart' = 'json'): HttpHeaders {
    const token = this.authService.getToken();
    let headers = new HttpHeaders({
      'Authorization': token ? `Token ${token}` : ''
    });
    if (contentType === 'json') {
      headers = headers.set('Content-Type', 'application/json');
    }
    return headers;
  }

  obtenerColegiosActivos(): Observable<ColegioItem[]> {
    return this.http.get<ColegioItem[]>(
      `${this.apiUrl}/colegios/`,
      { headers: this.getAuthHeaders() }
    );
  }

  /**
   * A qué colegio va el hijo: lo decide el colegio que lo habilitó con el RUT del apoderado, no el apoderado
   * (puede tener hijos en varios colegios). Responde 404 si ese estudiante no está habilitado para la cuenta.
   */
  consultarHabilitacion(rutEstudiante: string): Observable<HabilitacionEstudiante> {
    return this.http.get<HabilitacionEstudiante>(
      `${this.apiUrl}/apoderado/habilitacion-estudiante/`,
      { headers: this.getAuthHeaders(), params: { rut: rutEstudiante } }
    );
  }

  obtenerSedesActivas(colegioId: number): Observable<SedeItem[]> {
    return this.http.get<SedeItem[]>(
      `${this.apiUrl}/colegios/${colegioId}/sedes/`,
      { headers: this.getAuthHeaders() }
    );
  }

  obtenerEstudiantes(): Observable<Estudiante[]> {
    return this.http.get<Estudiante[]>(
      `${this.apiUrl}/estudiantes/`,
      {
        headers: this.getAuthHeaders()
      }
    );
  }

  obtenerEstudiantesConductor(conductorId: number): Observable<Estudiante[]> {
    return this.http.get<Estudiante[]>(
      `${this.apiUrl}/conductores/${conductorId}/estudiantes/`,
      {
        headers: this.getAuthHeaders()
      }
    );
  }

  /** Avisos de inasistencia de hoy y mañana ("no lo envío en el furgón"). */
  obtenerAsistencia(id: number): Observable<EstadoAsistencia> {
    return this.http.get<EstadoAsistencia>(
      `${this.apiUrl}/estudiantes/${id}/inasistencias/`,
      { headers: this.getAuthHeaders() }
    );
  }

  avisarInasistencia(
    id: number,
    fecha: string,
    tramo: TramoAsistencia | 'ambos',
    motivo = ''
  ): Observable<EstadoAsistencia> {
    return this.http.post<EstadoAsistencia>(
      `${this.apiUrl}/estudiantes/${id}/inasistencias/`,
      { fecha, tramo, motivo },
      { headers: this.getAuthHeaders() }
    );
  }

  cancelarInasistencia(
    id: number,
    fecha: string,
    tramo: TramoAsistencia | 'ambos'
  ): Observable<EstadoAsistencia> {
    return this.http.delete<EstadoAsistencia>(
      `${this.apiUrl}/estudiantes/${id}/inasistencias/`,
      { headers: this.getAuthHeaders(), params: { fecha, tramo } }
    );
  }

  obtenerEstudiante(id: number): Observable<Estudiante> {
    return this.http.get<Estudiante>(
      `${this.apiUrl}/estudiantes/${id}/`,
      {
        headers: this.getAuthHeaders()
      }
    );
  }

  obtenerPersonasAutorizadas(estudianteId: number): Observable<PersonaAutorizada[]> {
    return this.http.get<PersonaAutorizada[]>(`${this.apiUrl}/estudiantes/${estudianteId}/personas-autorizadas/`, { headers: this.getAuthHeaders() });
  }

  agregarPersonaAutorizada(estudianteId: number, datos: { nombre: string; rut: string; telefono?: string }): Observable<PersonaAutorizada> {
    return this.http.post<PersonaAutorizada>(`${this.apiUrl}/estudiantes/${estudianteId}/personas-autorizadas/`, datos, { headers: this.getAuthHeaders() });
  }

  eliminarPersonaAutorizada(estudianteId: number, personaId: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/estudiantes/${estudianteId}/personas-autorizadas/${personaId}/`, { headers: this.getAuthHeaders() });
  }

  actualizarEstudiante(
    id: number,
    estudiante: Partial<Estudiante>
  ): Observable<EstudianteUpdateResponse> {
    return this.http.patch<EstudianteUpdateResponse>(
      `${this.apiUrl}/estudiantes/${id}/`,
      estudiante,
      { headers: this.getAuthHeaders() }
    );
  }

  crearEstudiante(estudiante: Estudiante, foto?: File): Observable<EstudianteCreateResponse> {
    const datos = new FormData();
    Object.entries(estudiante).forEach(([clave, valor]) => {
      if (valor !== undefined && valor !== null) {
        datos.append(clave, String(valor));
      }
    });
    if (foto) {
      datos.append('foto', foto, foto.name);
    }
    return this.http.post<EstudianteCreateResponse>(`${this.apiUrl}/estudiantes/`, datos, {
      // El navegador agrega el boundary correcto de multipart/form-data.
      headers: this.getAuthHeaders('multipart')
    });
  }

  /**
   * Autoriza o revoca el reconocimiento facial de UN hijo (Ley 21.719). Al revocar, el servidor borra
   * al tiro su foto y sus datos faciales, y deja una constancia que no se puede borrar.
   */
  cambiarBiometria(id: number, autoriza: boolean): Observable<{
    message: string;
    datos_eliminados: boolean;
    estudiante: Estudiante;
  }> {
    return this.http.post<{ message: string; datos_eliminados: boolean; estudiante: Estudiante }>(
      `${this.apiUrl}/estudiantes/${id}/biometria/`, { autoriza }, { headers: this.getAuthHeaders() }
    );
  }

  registrarBiometriaEstudiante(id: number, foto: File): Observable<{
    message: string;
    estudiante_id: number;
    tiene_biometria: boolean;
  }> {
    const datos = new FormData();
    datos.append('foto', foto, foto.name || 'rostro.jpg');
    return this.http.post<{
      message: string;
      estudiante_id: number;
      tiene_biometria: boolean;
    }>(`${this.apiUrl}/estudiantes/${id}/registrar-rostro/`, datos, {
      headers: this.getAuthHeaders('multipart')
    });
  }
}
