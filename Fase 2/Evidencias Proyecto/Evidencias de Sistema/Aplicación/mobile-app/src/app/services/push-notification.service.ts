import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable } from 'rxjs';
import { Capacitor, PluginListenerHandle } from '@capacitor/core';
import {
  ActionPerformed,
  PushNotifications,
  PushNotificationSchema,
  Token
} from '@capacitor/push-notifications';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

/** Bandeja de avisos de cada rol; el conductor ve los suyos en su ruta activa. */
/**
 * Canal de Android con importancia alta: así el aviso baja desde arriba de la pantalla
 * (heads-up) en vez de quedar solo en la barra. El servidor envía los push a este canal
 * y AndroidManifest.xml lo declara como canal por defecto.
 */
export const CANAL_AVISOS = 'avisos_rutas';

export function rutaNotificaciones(rol?: string | null): string {
  if (rol === 'delegado') return '/delegado/notificaciones';
  if (rol === 'conductor') return '/conductor/ruta-activa';
  return '/apoderado/notificaciones';
}

@Injectable({ providedIn: 'root' })
export class PushNotificationService {
  private apiUrl = environment.apiUrl;
  private tokenRegistrado$ = new BehaviorSubject<string | null>(null);
  private nuevaNotificacionReceived$ = new BehaviorSubject<PushNotificationSchema | null>(null);
  private inicializacionEnCurso?: Promise<void>;
  private inicializado = false;
  private listeners: PluginListenerHandle[] = [];
  private capacitor = Capacitor;
  private pushNotifications = PushNotifications;

  constructor(
    private http: HttpClient,
    private authService: AuthService,
    private router: Router
  ) {}

  private getAuthHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      'Authorization': token ? `Token ${token}` : '',
      'Content-Type': 'application/json'
    });
  }

  async inicializarPushNotifications(): Promise<void> {
    if (!this.capacitor.isNativePlatform()) {
      console.log('[PushNotificationService] Push disponible solo en la app nativa.');
      return;
    }
    if (this.inicializado) return;
    if (this.inicializacionEnCurso) return this.inicializacionEnCurso;

    this.inicializacionEnCurso = this.inicializarPushNativo();
    try {
      await this.inicializacionEnCurso;
    } finally {
      this.inicializacionEnCurso = undefined;
    }
  }

  private async inicializarPushNativo(): Promise<void> {
    try {
      // Los listeners deben existir antes de register para no perder el token.
      await this.configurarOyentes();

      let permisos = await this.pushNotifications.checkPermissions();
      if (permisos.receive === 'prompt') {
        permisos = await this.pushNotifications.requestPermissions();
      }
      if (permisos.receive !== 'granted') {
        console.warn('[PushNotificationService] Permiso de notificaciones denegado.');
        return;
      }

      await this.crearCanalAvisos();
      await this.pushNotifications.register();
      this.inicializado = true;
    } catch (error) {
      console.error('[PushNotificationService] Error inicializando Push Notifications:', error);
    }
  }

  private async crearCanalAvisos(): Promise<void> {
    if (this.capacitor.getPlatform() !== 'android') return;
    try {
      // Si el canal ya existe, Android conserva su configuración (no se puede bajar ni subir después).
      await this.pushNotifications.createChannel({
        id: CANAL_AVISOS,
        name: 'Avisos de Rutas Seguras',
        description: 'Subidas, llegadas, ausencias y emergencias de tus estudiantes',
        importance: 5,
        visibility: 1,
        vibration: true,
      });
    } catch (error) {
      console.warn('[PushNotificationService] No se pudo crear el canal de avisos:', error);
    }
  }

  private async configurarOyentes(): Promise<void> {
    if (this.listeners.length) return;

    this.listeners.push(await this.pushNotifications.addListener('registration', (token: Token) => {
      this.tokenRegistrado$.next(token.value);
      localStorage.setItem('fcm_token', token.value);
      this.enviarTokenAlBackend(token.value).subscribe({
        next: () => console.log('[PushNotificationService] Token FCM registrado en Django.'),
        error: err => console.error('[PushNotificationService] Error registrando token FCM:', err)
      });
    }));

    this.listeners.push(await this.pushNotifications.addListener('registrationError', error => {
      console.error('[PushNotificationService] Error de registro FCM:', error);
    }));

    this.listeners.push(await this.pushNotifications.addListener(
      'pushNotificationReceived',
      (notification: PushNotificationSchema) => this.nuevaNotificacionReceived$.next(notification)
    ));

    this.listeners.push(await this.pushNotifications.addListener(
      'pushNotificationActionPerformed',
      (_action: ActionPerformed) => this.router.navigate([rutaNotificaciones(this.authService.getUsuario()?.rol)])
    ));
  }

  enviarTokenAlBackend(fcmToken: string): Observable<unknown> {
    const deviceName = this.capacitor.getPlatform() === 'android' ? 'Android Device' : 'iOS Device';
    return this.http.post(`${this.apiUrl}/notificaciones/fcm-token/`, {
      token: fcmToken,
      device_name: deviceName
    }, { headers: this.getAuthHeaders() });
  }

  desactivarTokenEnBackend(fcmToken: string): Observable<unknown> {
    return this.http.delete(`${this.apiUrl}/notificaciones/fcm-token/`, {
      headers: this.getAuthHeaders(),
      body: { token: fcmToken }
    });
  }

  async cerrarSesionPush(): Promise<void> {
    const token = this.tokenRegistrado$.value || localStorage.getItem('fcm_token');
    if (token && this.authService.getToken()) {
      await new Promise<void>(resolve => {
        this.desactivarTokenEnBackend(token).subscribe({
          next: () => resolve(),
          error: err => {
            // El cierre de sesión local debe continuar aunque no haya red.
            console.error('[PushNotificationService] No se pudo desactivar el token FCM:', err);
            resolve();
          }
        });
      });
    }

    await Promise.all(this.listeners.map(listener => listener.remove()));
    this.listeners = [];
    this.inicializado = false;
    this.inicializacionEnCurso = undefined;
    this.tokenRegistrado$.next(null);
    localStorage.removeItem('fcm_token');
  }

  getNuevaNotificacionSubject(): Observable<PushNotificationSchema | null> {
    return this.nuevaNotificacionReceived$.asObservable();
  }

  getTokenActual(): string | null {
    return this.tokenRegistrado$.value;
  }
}
