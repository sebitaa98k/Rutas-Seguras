import { Injectable, signal, computed } from '@angular/core';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: 'ADMIN_PLATAFORMA' | 'ADMIN_COLEGIO' | 'CONDUCTOR' | 'APODERADO' | 'ADMIN';
  colegioId?: number | null;
  colegioNombre?: string | null;
  permissions: string[];
  /** La cuenta entró con la contraseña inicial y debe cambiarla. */
  debeCambiarPassword?: boolean;
}

export interface BackendAuthResponse {
  message: string;
  token: string;
  usuario: {
    id: number;
    email: string;
    first_name: string;
    last_name: string;
    rol: string;
    colegio_id?: number | null;
    colegio_nombre?: string | null;
    rut?: string;
    telefono?: string;
    debe_cambiar_password?: boolean;
  };
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly STORAGE_KEY = 'rutas_seguras_auth_session';
  private readonly TOKEN_KEY = 'rutas_seguras_auth_token';

  private readonly apiUrl = environment.apiBaseUrl;

  private currentUserSignal = signal<UserProfile | null>(this.getStoredUser());

  public readonly currentUser = this.currentUserSignal.asReadonly();
  public readonly isAuthenticated = computed(() => !!this.currentUserSignal());

  constructor(
    private router: Router,
    private http: HttpClient
  ) {}

  private getStoredUser(): UserProfile | null {
    try {
      const storedData = localStorage.getItem(this.STORAGE_KEY);
      if (storedData) {
        const user: UserProfile = JSON.parse(storedData);
        if (['ADMIN_PLATAFORMA', 'ADMIN_COLEGIO'].includes(user.role)) {
          return user;
        }
        this.logout();
      }
    } catch (error) {
      console.error('Error al recuperar sesión guardada:', error);
    }
    return null;
  }

  public async login(email: string, password: string): Promise<boolean> {
    const cleanEmail = email?.trim().toLowerCase();
    const cleanPassword = password?.trim();

    try {
      const response = await firstValueFrom(
        this.http.post<BackendAuthResponse>(`${this.apiUrl}/auth/login-admin/`, {
          email: cleanEmail,
          password: cleanPassword
        })
      );

      if (response && response.token && response.usuario) {
        const u = response.usuario;

        if (!['admin_plataforma', 'admin_colegio'].includes(u.rol)) {
          throw new Error('Acceso denegado. Este portal es exclusivo para usuarios administrativos.');
        }

        const mappedRole: 'ADMIN_PLATAFORMA' | 'ADMIN_COLEGIO' = u.rol === 'admin_colegio' ? 'ADMIN_COLEGIO' : 'ADMIN_PLATAFORMA';

        const mappedUser: UserProfile = {
          id: String(u.id),
          name: `${u.first_name} ${u.last_name}`.trim() || u.email,
          email: u.email,
          role: mappedRole,
          colegioId: u.colegio_id || null,
          colegioNombre: u.colegio_nombre || null,
          debeCambiarPassword: !!u.debe_cambiar_password,
          permissions: [
            'MANAGE_ALL',
            'CRUD_APODERADOS',
            'CRUD_CONDUCTORES',
            'CRUD_FURGONES',
            'CRUD_RUTAS',
            'CRUD_ESTUDIANTES'
          ]
        };

        localStorage.setItem(this.TOKEN_KEY, response.token);
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(mappedUser));
        this.currentUserSignal.set(mappedUser);
        return true;
      }
      throw new Error('Respuesta del servidor inválida');
    } catch (error: any) {
      const mensaje = error?.error?.message || error?.message || 'Credenciales incorrectas o acceso restringido a administradores.';
      throw new Error(mensaje);
    }
  }

  /** Pide el código de recuperación de una cuenta de administrador. El servidor responde lo mismo exista o no. */
  public async solicitarRecuperacion(email: string): Promise<string> {
    try {
      const respuesta = await firstValueFrom(
        this.http.post<{ message: string }>(`${this.apiUrl}/auth/password-reset/`, { email, rol: 'admin' })
      );
      return respuesta.message;
    } catch (error: any) {
      throw new Error(error?.error?.message || 'No se pudo solicitar el código.');
    }
  }

  public async confirmarRecuperacion(email: string, codigo: string, nuevaPassword: string): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(`${this.apiUrl}/auth/password-reset/confirm/`, {
          email,
          codigo,
          nueva_password: nuevaPassword
        })
      );
    } catch (error: any) {
      throw new Error(error?.error?.message || 'No se pudo cambiar la contraseña.');
    }
  }

  public async cambiarPassword(actual: string, nueva: string): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post(`${this.apiUrl}/auth/cambiar-password/`, {
          password_actual: actual,
          nueva_password: nueva
        })
      );
    } catch (error: any) {
      throw new Error(error?.error?.message || 'No se pudo cambiar la contraseña.');
    }
    const user = this.currentUserSignal();
    if (user) {
      const actualizado = { ...user, debeCambiarPassword: false };
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(actualizado));
      this.currentUserSignal.set(actualizado);
    }
  }

  public getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  public hasPermission(permission: string): boolean {
    const user = this.currentUserSignal();
    if (!user) return false;
    return user.permissions.includes('MANAGE_ALL') || user.permissions.includes(permission);
  }

  public logout(): void {
    localStorage.removeItem(this.STORAGE_KEY);
    localStorage.removeItem(this.TOKEN_KEY);
    this.currentUserSignal.set(null);
    this.router.navigate(['/login']);
  }
}
