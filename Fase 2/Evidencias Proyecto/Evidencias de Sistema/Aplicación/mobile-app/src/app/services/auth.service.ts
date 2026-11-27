import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';

export interface Usuario {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  rol: string;
  rut?: string;
  telefono?: string;
  licencia_conducir?: string;
  colegio_id?: number | null;
  colegio_nombre?: string | null;
  tipo_delegado?: 'autorizado' | 'inspector' | null;
  sedes_responsable?: { id: number; nombre: string }[];
  /** La cuenta entró con la contraseña inicial y debe cambiarla. */
  debe_cambiar_password?: boolean;
  /** El apoderado todavía no acepta los términos vigentes. */
  debe_aceptar_terminos?: boolean;
}

export interface AuthResponse {
  message: string;
  token: string;
  usuario: Usuario;
}

export interface RegistroApoderadoData {
  nombre: string;
  apellido: string;
  rut: string;
  email: string;
  telefono: string;
  password: string;
  colegio_id: number;
  acepta_terminos: boolean;
  version_terminos: string;
}

export interface ColegioRegistro {
  id: number;
  nombre: string;
  comuna?: string;
}

export interface TerminosVigentes {
  version: string;
  titulo: string;
  contenido: string;
}

export interface RegistroDelegadoData {
  nombre: string;
  apellido: string;
  rut: string;
  email: string;
  telefono: string;
  password: string;
}

export interface RecuperacionResponse {
  message: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {

  private apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  private getAuthHeaders(): HttpHeaders {
    const token = this.getToken();
    return new HttpHeaders({
      'Authorization': token ? `Token ${token}` : ''
    });
  }

  registrarApoderado(data: RegistroApoderadoData): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/auth/registro/`, data).pipe(
      tap(response => {
        if (response && response.token) {
          this.guardarSesion(response.token, response.usuario);
        }
      })
    );
  }

  obtenerColegiosRegistro(): Observable<ColegioRegistro[]> {
    return this.http.get<ColegioRegistro[]>(`${this.apiUrl}/auth/colegios-registro/`);
  }

  obtenerTerminos(): Observable<TerminosVigentes> {
    return this.http.get<TerminosVigentes>(`${this.apiUrl}/auth/terminos/`);
  }

  /** Términos 1.2: la biometría ya no se acepta aquí, se autoriza por cada hijo. */
  aceptarTerminos(version: string): Observable<{ message: string; usuario: Usuario }> {
    return this.http.post<{ message: string; usuario: Usuario }>(`${this.apiUrl}/auth/terminos/aceptar/`, {
      version,
      acepta_terminos: true
    }).pipe(
      tap(res => {
        if (res?.usuario) {
          localStorage.setItem('user', JSON.stringify(res.usuario));
        }
      })
    );
  }

  registrarDelegado(data: RegistroDelegadoData): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/auth/registro-delegado/`, data).pipe(
      tap(response => {
        if (response && response.token) {
          this.guardarSesion(response.token, response.usuario);
        }
      })
    );
  }

  getEstudiantesDelegado(): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/delegados/estudiantes/`, { headers: this.getAuthHeaders() });
  }

  getPerfilDelegado(): Observable<Usuario> {
    return this.http.get<Usuario>(`${this.apiUrl}/delegados/perfil/`, { headers: this.getAuthHeaders() }).pipe(
      tap(usuario => localStorage.setItem('user', JSON.stringify(usuario)))
    );
  }

  generarQREntrega(
    estudianteId?: number,
    proposito: 'abordaje' | 'entrega' = 'entrega'
  ): Observable<{ qr_payload: string; valido_hasta: number; estatico?: boolean }> {
    return this.http.post<{ qr_payload: string; valido_hasta: number; estatico?: boolean }>(
      `${this.apiUrl}/rutas/generar-qr-entrega/`,
      { ...(estudianteId ? { estudiante_id: estudianteId } : {}), proposito },
      { headers: this.getAuthHeaders() }
    );
  }

  actualizarPerfilDelegado(data: { first_name?: string; last_name?: string; telefono?: string }): Observable<any> {
    return this.http.patch<any>(`${this.apiUrl}/delegados/perfil/`, data, { headers: this.getAuthHeaders() }).pipe(
      tap((res: any) => {
        if (res && res.usuario) {
          localStorage.setItem('user', JSON.stringify(res.usuario));
        }
      })
    );
  }

  login(email: string, password: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/auth/login/`, { email, password }).pipe(
      tap(response => {
        if (response && response.token) {
          this.guardarSesion(response.token, response.usuario);
        }
      })
    );
  }

  /** `rol`: tipo de cuenta de la pantalla (apoderado, conductor o delegado); solo esas cuentas reciben el código. */
  solicitarRecuperacion(email: string, rol: string): Observable<RecuperacionResponse> {
    return this.http.post<RecuperacionResponse>(
      `${this.apiUrl}/auth/password-reset/`,
      { email, rol }
    );
  }

  confirmarRecuperacion(
    email: string,
    codigo: string,
    nuevaPassword: string
  ): Observable<RecuperacionResponse> {
    return this.http.post<RecuperacionResponse>(
      `${this.apiUrl}/auth/password-reset/confirm/`,
      {
        email,
        codigo,
        nueva_password: nuevaPassword
      }
    );
  }

  actualizarPerfilApoderado(data: { first_name?: string; last_name?: string; telefono?: string }): Observable<any> {
    return this.http.patch<any>(`${this.apiUrl}/apoderados/perfil/`, data).pipe(
      tap(res => {
        if (res?.usuario) {
          localStorage.setItem('user', JSON.stringify(res.usuario));
        }
      })
    );
  }

  cambiarPassword(id: number, passwordActual: string, nuevaPassword: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/apoderados/${id}/cambiar-password/`, {
      password_actual: passwordActual,
      nueva_password: nuevaPassword
    });
  }

  /** Cambio de contraseña propio, válido para cualquier rol. */
  cambiarPasswordPropia(passwordActual: string, nuevaPassword: string): Observable<{ message: string; usuario: Usuario }> {
    return this.http.post<{ message: string; usuario: Usuario }>(`${this.apiUrl}/auth/cambiar-password/`, {
      password_actual: passwordActual,
      nueva_password: nuevaPassword
    }).pipe(
      tap(res => {
        if (res?.usuario) {
          localStorage.setItem('user', JSON.stringify(res.usuario));
        }
      })
    );
  }

  guardarSesion(token: string, usuario: Usuario): void {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify(usuario));
  }

  getToken(): string | null {
    return localStorage.getItem('auth_token');
  }

  getUsuario(): Usuario | null {
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
  }

  logout(): void {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
  }
}
