import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface EventoAuditoria {
  id: number;
  tipo: string;
  tipo_nombre: string;
  estudiante_id: number | null;
  estudiante_nombre: string;
  metodo: string;
  persona_nombre: string;
  persona_rol: string;
  persona_rut: string;
  detalle: string;
  creado_en: string;
}

export interface AlumnoAuditoria {
  id: number | null;
  nombre: string;
  estado: 'pendiente' | 'a_bordo' | 'entregado' | 'ausente' | 'no_asiste' | 'no_recibido';
  estado_nombre: string;
  subida: EventoAuditoria | null;
  entrega: EventoAuditoria | null;
  observaciones: string[];
}

export interface RecorridoAuditoria {
  id: number;
  ruta_id: number | null;
  nombre_ruta: string;
  sentido: 'hacia_colegio' | 'desde_colegio';
  colegio_nombre: string;
  conductor_nombre: string;
  furgon_patente: string;
  hora_programada: string | null;
  iniciado_en: string | null;
  finalizado_en: string | null;
  creado_en: string;
  minutos_atraso: number | null;
  simulado: boolean;
  atrasado: boolean;
  estado: 'finalizado' | 'en_curso' | 'sin_iniciar';
  alumnos: AlumnoAuditoria[];
  eventos: EventoAuditoria[];
}

export interface RespuestaAuditoria {
  tolerancia_atraso_minutos: number;
  limite: number;
  recorridos: RecorridoAuditoria[];
}

export interface AceptacionTerminos {
  id: number;
  nombre: string;
  rut: string;
  email: string;
  colegio_nombre: string;
  version: string;
  huella_texto: string;
  /** Solo en las versiones 1.0 y 1.1 (casilla general). Desde la 1.2 la biometría es por hijo. */
  acepta_biometria: boolean;
  origen: 'registro' | 'ingreso';
  origen_nombre: string;
  ip: string | null;
  dispositivo: string;
  aceptado_en: string;
  /** La aceptación vale para todos sus hijos; cada uno con su colegio. */
  hijos?: {
    id: number;
    nombre: string;
    colegio_id: number | null;
    colegio_nombre: string;
    /** Consentimiento biométrico de este hijo, lo que rige hoy. */
    autoriza_biometria: boolean;
    autoriza_biometria_en: string | null;
  }[];
  /** Hijos en otros colegios (el admin de un colegio no ve sus nombres). */
  hijos_otros_colegios?: number;
}

export interface TerminosPendiente {
  id: number;
  nombre: string;
  rut: string;
  email: string;
  colegio_nombre: string;
  debe_cambiar_password: boolean;
}

/** Constancia inmutable: el apoderado otorgó o revocó la biometría de UN hijo (términos 1.2). */
export interface ConsentimientoBiometria {
  id: number;
  estudiante_id: number | null;
  estudiante_nombre: string;
  estudiante_rut: string;
  apoderado_nombre: string;
  apoderado_rut: string;
  apoderado_email: string;
  colegio_nombre: string;
  evento: 'otorgado' | 'revocado';
  evento_nombre: string;
  origen: 'agregar_hijo' | 'detalle_hijo' | 'desactivacion' | 'migracion';
  origen_nombre: string;
  version_terminos: string;
  datos_eliminados: boolean;
  ip: string | null;
  dispositivo: string;
  creado_en: string;
}

/** Historial ANTIGUO (términos 1.0 y 1.1): autorización general del apoderado para todos sus hijos. */
export interface CambioBiometria {
  id: number;
  nombre: string;
  rut: string;
  email: string;
  colegio_nombre: string;
  autoriza: boolean;
  origen: 'registro' | 'terminos' | 'perfil';
  origen_nombre: string;
  fotos_eliminadas: number;
  ip: string | null;
  dispositivo: string;
  creado_en: string;
}

export interface RespuestaAuditoriaTerminos {
  version_vigente: string;
  limite: number;
  aceptaciones: AceptacionTerminos[];
  pendientes: TerminosPendiente[];
  consentimientos_biometria?: ConsentimientoBiometria[];
  cambios_biometria?: CambioBiometria[];
}

export interface FiltrosAuditoria {
  desde?: string;
  hasta?: string;
  buscar?: string;
  soloAtrasos?: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class AuditoriaService {
  private readonly apiUrl = `${environment.apiBaseUrl}/auditoria/recorridos/`;
  private readonly terminosUrl = `${environment.apiBaseUrl}/auditoria/terminos/`;

  constructor(private http: HttpClient) {}

  getRecorridos(filtros: FiltrosAuditoria): Observable<RespuestaAuditoria> {
    let params = new HttpParams();
    if (filtros.desde) params = params.set('desde', filtros.desde);
    if (filtros.hasta) params = params.set('hasta', filtros.hasta);
    if (filtros.buscar?.trim()) params = params.set('buscar', filtros.buscar.trim());
    if (filtros.soloAtrasos) params = params.set('solo_atrasos', '1');
    return this.http.get<RespuestaAuditoria>(this.apiUrl, { params });
  }

  getTerminos(buscar: string): Observable<RespuestaAuditoriaTerminos> {
    let params = new HttpParams();
    if (buscar.trim()) params = params.set('buscar', buscar.trim());
    return this.http.get<RespuestaAuditoriaTerminos>(this.terminosUrl, { params });
  }
}
