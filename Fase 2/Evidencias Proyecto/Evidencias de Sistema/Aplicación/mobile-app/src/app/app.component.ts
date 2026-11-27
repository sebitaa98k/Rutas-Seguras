import { Component, OnInit, OnDestroy, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { Subscription } from 'rxjs';

import {
  IonApp,
  IonRouterOutlet,
  IonMenu,
  IonContent,
  IonMenuToggle,
  IonIcon,
  ToastController,
  MenuController,
  NavController,
  Platform
} from '@ionic/angular/standalone';
import { App } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';
import { addIcons } from 'ionicons';
import {
  documentTextOutline,
  homeOutline,
  logOutOutline,
  navigateOutline,
  notificationsOutline,
  peopleOutline,
  personAddOutline,
  personOutline,
  qrCodeOutline,
  scanOutline,
  shieldCheckmarkOutline,
  warningOutline
} from 'ionicons/icons';

import { AuthService, Usuario } from './services/auth.service';
import { PushNotificationService, rutaNotificaciones } from './services/push-notification.service';
import { NotificationService, NotificacionItem } from './services/notification.service';
import { FeedbackService, FeedbackType } from './services/feedback.service';
import { rutaInicioDe } from './guards/auth.guard';

interface BottomNavItem {
  label: string;
  icon: string;
  route: string;
  exact?: boolean;
  variant?: 'featured' | 'danger' | 'notifications';
}

const BOTTOM_NAV_BY_ROLE: Record<string, BottomNavItem[]> = {
  delegado: [
    { label: 'Inicio', icon: 'home-outline', route: '/delegado/inicio', exact: true },
    { label: 'Ruta', icon: 'navigate-outline', route: '/delegado/seguimiento' },
    { label: 'Mi QR', icon: 'qr-code-outline', route: '/delegado/mi-qr' },
    { label: 'Avisos', icon: 'notifications-outline', route: '/delegado/notificaciones', variant: 'notifications' },
    { label: 'Perfil', icon: 'person-outline', route: '/delegado/perfil' }
  ],
  apoderado: [
    { label: 'Inicio', icon: 'home-outline', route: '/apoderado/inicio', exact: true },
    { label: 'Mis hijos', icon: 'people-outline', route: '/apoderado/mis-hijos' },
    { label: 'Ruta', icon: 'navigate-outline', route: '/apoderado/seguimiento' },
    { label: 'Avisos', icon: 'notifications-outline', route: '/apoderado/notificaciones', variant: 'notifications' },
    { label: 'Perfil', icon: 'person-outline', route: '/apoderado/perfil' }
  ],
  conductor: [
    { label: 'Inicio', icon: 'home-outline', route: '/conductor/inicio', exact: true },
    { label: 'Ruta', icon: 'navigate-outline', route: '/conductor/ruta-activa' },
    { label: 'Facial', icon: 'scan-outline', route: '/conductor/escaneo-facial', variant: 'featured' },
    { label: 'Emergencia', icon: 'warning-outline', route: '/conductor/emergencia', variant: 'danger' },
    { label: 'Perfil', icon: 'person-outline', route: '/conductor/perfil' }
  ]
};

@Component({
  selector: 'app-root',
  templateUrl: 'app.component.html',
  styleUrls: ['app.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    RouterLinkActive,
    IonApp,
    IonRouterOutlet,
    IonMenu,
    IonContent,
    IonMenuToggle,
    IonIcon
  ]
})
export class AppComponent implements OnInit, OnDestroy {

  @ViewChild(IonRouterOutlet) private routerOutlet?: IonRouterOutlet;
  private alertSub?: Subscription;

  constructor(

    private authService: AuthService,
    private pushNotificationService: PushNotificationService,
    public notificationService: NotificationService,
    private router: Router,
    private toastController: ToastController,
    private feedback: FeedbackService,
    private menuController: MenuController,
    private navController: NavController,
    private platform: Platform
  ) {
    addIcons({
      documentTextOutline,
      homeOutline,
      logOutOutline,
      navigateOutline,
      notificationsOutline,
      peopleOutline,
      personAddOutline,
      personOutline,
      qrCodeOutline,
      scanOutline,
      shieldCheckmarkOutline,
      warningOutline
    });
  }

  ngOnInit() {
    this.configurarBotonVolver();

    if (this.estaAutenticado) {
      this.pushNotificationService.inicializarPushNotifications();
      this.notificationService.iniciarPolling();
    }

    // Escuchar alertas de notificaciones entrantes en tiempo real
    this.alertSub = this.notificationService.nuevaNotificacionAlert$.subscribe((notif: NotificacionItem) => {
      if (notif) {
        this.mostrarToastAlert(notif);
      }
    });
  }

  ngOnDestroy() {
    if (this.alertSub) {
      this.alertSub.unsubscribe();
    }
    this.notificationService.detenerPolling();
  }

  /**
   * Botón físico de Android: desde la pantalla principal minimiza la app en vez de
   * llegar al login. Los menús y ventanas abiertas se atienden antes (mayor prioridad).
   */
  private configurarBotonVolver(): void {
    if (!Capacitor.isNativePlatform()) return;

    // Sin un listener, Android usa el historial del WebView, que incluye el login.
    void App.addListener('backButton', () => {});
    this.platform.backButton.subscribeWithPriority(10, procesarSiguiente => {
      const ruta = this.router.url.split('?')[0].split('#')[0];
      const destino = this.estaAutenticado ? rutaInicioDe(this.usuario?.rol) : '/home';
      if (ruta === destino) {
        void App.minimizeApp();
      } else if (this.routerOutlet?.canGoBack()) {
        procesarSiguiente();
      } else {
        void this.navController.navigateRoot(destino, { animationDirection: 'back' });
      }
    });
  }

  get usuario(): Usuario | null {
    return this.authService.getUsuario();
  }

  get estaAutenticado(): boolean {
    return !!this.authService.getToken();
  }

  get mostrarNavegacionAutenticada(): boolean {
    if (!this.estaAutenticado) return false;
    const ruta = this.router.url.split('?')[0].split('#')[0];
    const rutasPublicas = new Set([
      '/',
      '/home',
      '/login',
      '/registro',
      '/recuperar-password',
      '/cambiar-password',
      '/delegado/registro',
    ]);
    return !rutasPublicas.has(ruta);
  }

  get bottomNavItems(): BottomNavItem[] {
    return BOTTOM_NAV_BY_ROLE[this.usuario?.rol || ''] || [];
  }

  get bottomNavLabel(): string {
    const rol = this.usuario?.rol || 'usuario';
    return `Navegación principal del ${rol}`;
  }

  async cerrarSesion() {
    this.notificationService.detenerPolling();
    await this.pushNotificationService.cerrarSesionPush();
    // Vuelve al inicio de sesión de su propio rol (conductor, delegado o apoderado).
    const rol = this.authService.getUsuario()?.rol;
    this.authService.logout();
    await this.menuController.close('main-menu');
    await this.mostrarToast('Has cerrado sesión correctamente.', 'success');
    await this.navController.navigateRoot('/login', rol ? { queryParams: { rol } } : undefined);
  }

  private async mostrarToast(mensaje: string, color: 'success' | 'danger' | 'warning') {
    await this.feedback.show(mensaje, color as FeedbackType, 3000);
  }

  private async mostrarToastAlert(notif: NotificacionItem) {
    const colorAlert = notif.tipo === 'emergencia' ? 'danger' : 'primary';
    const toast = await this.toastController.create({
      header: notif.titulo,
      message: notif.mensaje,
      duration: 4500,
      color: colorAlert,
      position: 'top',
      buttons: [
        {
          text: 'Ver',
          handler: () => {
            this.router.navigate([rutaNotificaciones(this.usuario?.rol)]);
          }
        }
      ]
    });
    await toast.present();
  }

}
