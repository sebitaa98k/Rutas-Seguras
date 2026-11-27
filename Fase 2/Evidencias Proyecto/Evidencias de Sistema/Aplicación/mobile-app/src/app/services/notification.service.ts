import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { BehaviorSubject, Subject, Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';

export interface NotificacionItem {
  id: number;
  titulo: string;
  mensaje: string;
  tipo: 'ruta_iniciada' | 'estudiante_abordo' | 'estudiante_llego' | 'estudiante_ausente' | 'ruta_finalizada' | 'emergencia' | 'aviso_sistema';
  leido: boolean;
  creado_en: string;
  estudiante?: number;
  estudiante_nombre?: string;
}

export interface NotificacionesResponse {
  no_leidas_count: number;
  notificaciones: NotificacionItem[];
}

@Injectable({
  providedIn: 'root'
})
export class NotificationService {

  private apiUrl = environment.apiUrl;
  private unreadCountSubject = new BehaviorSubject<number>(0);
  public unreadCount$ = this.unreadCountSubject.asObservable();

  private nuevaNotificacionAlertSubject = new Subject<NotificacionItem>();
  public nuevaNotificacionAlert$ = this.nuevaNotificacionAlertSubject.asObservable();

  private pollingTimer: any = null;
  private knownIds: Set<number> = new Set();
  private inicializadoPrimeraVez: boolean = false;

  constructor(private http: HttpClient) {}

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem('auth_token');
    return new HttpHeaders({
      'Authorization': token ? `Token ${token}` : '',
      'Content-Type': 'application/json'
    });
  }

  /**
   * Obtiene la lista de notificaciones del apoderado/delegado y actualiza el contador de no leídas.
   */
  getNotificaciones(): Observable<NotificacionesResponse> {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      return new Observable(sub => {
        sub.next({ no_leidas_count: 0, notificaciones: [] });
        sub.complete();
      });
    }

    return this.http.get<NotificacionesResponse>(`${this.apiUrl}/notificaciones/`, { headers: this.getAuthHeaders() }).pipe(
      tap(res => {
        if (res && typeof res.no_leidas_count === 'number') {
          this.unreadCountSubject.next(res.no_leidas_count);
        }

        if (res && res.notificaciones) {
          res.notificaciones.forEach(notif => {
            if (this.inicializadoPrimeraVez && !notif.leido && !this.knownIds.has(notif.id)) {
              this.nuevaNotificacionAlertSubject.next(notif);
            }
            this.knownIds.add(notif.id);
          });
          this.inicializadoPrimeraVez = true;
        }
      })
    );
  }

  /**
   * Inicia el polling automático cada X segundos para mantener la lista y alertas actualizadas en tiempo real.
   */
  iniciarPolling(intervalMs: number = 8000): void {
    this.detenerPolling();
    // Cada sesión parte de cero: las notificaciones que ya existen no se muestran como nuevas.
    this.knownIds.clear();
    this.inicializadoPrimeraVez = false;
    const token = localStorage.getItem('auth_token');
    if (!token) return;

    this.getNotificaciones().subscribe({ error: () => {} });

    this.pollingTimer = setInterval(() => {
      const activeToken = localStorage.getItem('auth_token');
      if (activeToken) {
        this.getNotificaciones().subscribe({ error: () => {} });
      } else {
        this.detenerPolling();
      }
    }, intervalMs);
  }

  /**
   * Detiene el polling automático.
   */
  detenerPolling(): void {
    if (this.pollingTimer) {
      clearInterval(this.pollingTimer);
      this.pollingTimer = null;
    }
  }

  /**
   * Marca una notificación específica como leída.
   */
  marcarLeida(notificacionId: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/notificaciones/${notificacionId}/marcar-leido/`, {}, { headers: this.getAuthHeaders() }).pipe(
      tap(() => {
        const current = this.unreadCountSubject.value;
        if (current > 0) {
          this.unreadCountSubject.next(current - 1);
        }
      })
    );
  }

  /**
   * Marca todas las notificaciones como leídas.
   */
  marcarTodasLeidas(): Observable<any> {
    return this.http.post(`${this.apiUrl}/notificaciones/marcar-todas-leidas/`, {}, { headers: this.getAuthHeaders() }).pipe(
      tap(() => {
        this.unreadCountSubject.next(0);
      })
    );
  }

  /**
   * Elimina una notificación individual de la bandeja del usuario.
   */
  eliminarNotificacion(notificacionId: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/notificaciones/${notificacionId}/eliminar/`, { headers: this.getAuthHeaders() }).pipe(
      tap(() => {
        this.getNotificaciones().subscribe({ error: () => {} });
      })
    );
  }

  /**
   * Elimina todas las notificaciones de la bandeja del usuario.
   */
  eliminarTodasNotificaciones(): Observable<any> {
    return this.http.delete(`${this.apiUrl}/notificaciones/eliminar-todas/`, { headers: this.getAuthHeaders() }).pipe(
      tap(() => {
        this.unreadCountSubject.next(0);
        this.getNotificaciones().subscribe({ error: () => {} });
      })
    );
  }

  // ===============================================
  // ACCIONES DEL CONDUCTOR EN BACKEND (GENERAN PUSH)
  // ===============================================

  obtenerMiRuta(): Observable<any> {
    return this.http.get(`${this.apiUrl}/rutas/mi-ruta/`, { headers: this.getAuthHeaders() });
  }

  iniciarRuta(rutaId?: number, posicion?: { latitud: number; longitud: number }): Observable<any> {
    const payload = { ...(rutaId ? { ruta_id: rutaId } : {}), ...(posicion || {}) };
    return this.http.post(`${this.apiUrl}/rutas/iniciar/`, payload, { headers: this.getAuthHeaders() });
  }

  escanearQR(qrPayload: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/escanear-qr/`, {
      qr_payload: qrPayload
    }, { headers: this.getAuthHeaders() });
  }

  escaneoFacial(
    imagenBase64: string,
    modo: 'abordar' | 'entregar' = 'abordar',
    confirmar: boolean = false,
    contexto?: { rutaId: number; estudianteId: number }
  ): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/escaneo-facial/`, {
      imagen: imagenBase64,
      modo: modo,
      confirmar: confirmar,
      ...(contexto ? { ruta_id: contexto.rutaId, estudiante_id: contexto.estudianteId } : {})
    }, { headers: this.getAuthHeaders() });
  }

  private accionEstudiante(accion: string, rutaId: number, estudianteId: number, extra: object = {}): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/${accion}/`, {
      ruta_id: rutaId,
      estudiante_id: estudianteId,
      ...extra
    }, { headers: this.getAuthHeaders() });
  }

  contactosEstudiante(rutaId: number, estudianteId: number): Observable<any> {
    return this.accionEstudiante('contactos-estudiante', rutaId, estudianteId);
  }

  registrarLlamada(rutaId: number, estudianteId: number, contactoId: string): Observable<any> {
    return this.accionEstudiante('registrar-llamada', rutaId, estudianteId, { contacto_id: contactoId });
  }

  marcarNoRecibido(rutaId: number, estudianteId: number): Observable<any> {
    return this.accionEstudiante('no-recibido', rutaId, estudianteId);
  }

  marcarApoderadoDisponible(rutaId: number, estudianteId: number): Observable<any> {
    return this.accionEstudiante('apoderado-disponible', rutaId, estudianteId);
  }

  iniciarReparto(rutaId: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/iniciar-reparto/`, { ruta_id: rutaId }, { headers: this.getAuthHeaders() });
  }

  corregirAbordaje(rutaId: number, estudianteId: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/corregir-abordaje/`, {
      ruta_id: rutaId,
      estudiante_id: estudianteId
    }, { headers: this.getAuthHeaders() });
  }

  marcarAusente(rutaId: number, estudianteId: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/marcar-ausente/`, {
      ruta_id: rutaId,
      estudiante_id: estudianteId
    }, { headers: this.getAuthHeaders() });
  }

  avisarLlegada(rutaId: number, estudianteId: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/avisar-llegada/`, {
      ruta_id: rutaId,
      estudiante_id: estudianteId
    }, { headers: this.getAuthHeaders() });
  }

  actualizarUbicacionRuta(
    rutaId: number,
    latitud: number,
    longitud: number,
    precisionMetros?: number
  ): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/ubicacion/`, {
      ruta_id: rutaId,
      latitud,
      longitud,
      precision_metros: precisionMetros
    }, { headers: this.getAuthHeaders() });
  }

  finalizarRuta(rutaId?: number): Observable<any> {
    const payload = rutaId ? { ruta_id: rutaId } : {};
    return this.http.post(`${this.apiUrl}/rutas/finalizar/`, payload, { headers: this.getAuthHeaders() });
  }

  enviarEmergencia(datos: string | {
    categoria: string;
    tipo_emergencia: string;
    descripcion: string;
    estudiante_id?: number | null;
  }): Observable<any> {
    const payload = typeof datos === 'string' ? { detalle: datos } : datos;
    return this.http.post(`${this.apiUrl}/emergencias/`, payload, { headers: this.getAuthHeaders() });
  }

  consultarQREntrega(qrPayload: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/consultar-qr-entrega/`, {
      qr_payload: qrPayload
    }, { headers: this.getAuthHeaders() });
  }

  confirmarEntregaMultiple(estudianteIds: number[], qrPayload: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/confirmar-entrega-multiple/`, {
      estudiante_ids: estudianteIds,
      qr_payload: qrPayload
    }, { headers: this.getAuthHeaders() });
  }

  consultarValidacionInstitucional(rutaId: number, estudianteId: number, qrPayload: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/consultar-validacion-institucional/`, {
      ruta_id: rutaId,
      estudiante_id: estudianteId,
      qr_payload: qrPayload
    }, { headers: this.getAuthHeaders() });
  }

  confirmarAbordajeInstitucional(rutaId: number, estudianteId: number, qrPayload: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/rutas/confirmar-abordaje-institucional/`, {
      ruta_id: rutaId,
      estudiante_id: estudianteId,
      qr_payload: qrPayload
    }, { headers: this.getAuthHeaders() });
  }

}
