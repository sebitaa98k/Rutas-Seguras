import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom, timeout } from 'rxjs';

import {
  IonContent,
  IonInput,
  IonInputPasswordToggle,
  IonItem,
  IonButton,
  IonSpinner,
  IonIcon,
  NavController,
  AlertController
} from '@ionic/angular/standalone';

import { addIcons } from 'ionicons';
import {
  personOutline,
  lockClosedOutline,
  arrowBackOutline,
  settingsOutline
} from 'ionicons/icons';

import { AuthService } from '../../../services/auth.service';
import { PushNotificationService } from '../../../services/push-notification.service';
import { NotificationService } from '../../../services/notification.service';
import { FeedbackService, FeedbackType } from '../../../services/feedback.service';
import { rutaInicioDe } from '../../../guards/auth.guard';
import { environment } from '../../../../environments/environment';
import { guardarServidor, normalizarServidor, obtenerServidor } from '../../../utils/servidor.util';

addIcons({
  personOutline,
  lockClosedOutline,
  arrowBackOutline
});

@Component({
  selector: 'app-login',
  templateUrl: './login.page.html',
  styleUrls: ['./login.page.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    IonContent,
    IonInput,
    IonInputPasswordToggle,
    IonItem,
    IonButton,
    IonSpinner,
    IonIcon
  ]
})
export class LoginPage implements OnInit {

  rol: string = 'apoderado';

  email: string = '';
  password: string = '';

  cargando: boolean = false;
  errorMensaje: string = '';

  constructor(
    private route: ActivatedRoute,
    private authService: AuthService,
    private pushNotificationService: PushNotificationService,
    private notificationService: NotificationService,
    private feedback: FeedbackService,
    private navController: NavController,
    private alertController: AlertController,
    private http: HttpClient
  ) {
      addIcons({arrowBackOutline,personOutline,lockClosedOutline,settingsOutline});}

  /** Demo: el botón "Servidor" solo aparece si mobile-app/.env lo habilita (MOSTRAR_CAMPO_SERVIDOR=true). */
  readonly mostrarCampoServidor = environment.mostrarCampoServidor;

  ngOnInit() {

    this.route.queryParams.subscribe(params => {

      if (params['rol']) {
        this.rol = params['rol'];
      }

    });

  }

  // Ionic puede reutilizar la página: nunca debe mostrar datos de la sesión anterior.
  ionViewWillEnter() {
    this.limpiarCredenciales();
  }

  private limpiarCredenciales() {
    this.email = '';
    this.password = '';
    this.errorMensaje = '';
  }

  async onSubmit() {

    this.errorMensaje = '';

    if (!this.email.trim() || !this.password) {

      this.errorMensaje =
        'Por favor ingresa tu correo y contraseña.';

      await this.mostrarToast(
        this.errorMensaje,
        'warning'
      );

      return;
    }

    this.cargando = true;

    this.authService.login(
      this.email,
      this.password
    ).subscribe({

      next: async (res) => {

        this.cargando = false;

        if (this.rol && res.usuario.rol !== this.rol) {
          this.authService.logout();

          const mensajeError = 'Correo electrónico o contraseña incorrectos.';

          this.errorMensaje = mensajeError;
          await this.mostrarToast(mensajeError, 'danger');
          return;
        }

        await this.pushNotificationService.inicializarPushNotifications();
        // Alertas dentro de la app (no requieren Firebase): deben partir al iniciar sesión,
        // no solo al recargar la página.
        this.notificationService.iniciarPolling();

        await this.mostrarToast(
          `¡Bienvenido/a ${res.usuario.first_name}!`,
          'success'
        );

        // Como raíz: el login no queda en el historial de "volver".
        await this.navController.navigateRoot(rutaInicioDe(res.usuario.rol));
        this.limpiarCredenciales();

      },

      error: async (err) => {

        this.cargando = false;

        let mensaje =
          'Correo electrónico o contraseña incorrectos.';

        // Sin respuesta del servidor (sin internet, servidor apagado o IP equivocada) no es un
        // problema de la contraseña: se dice qué pasó para que la persona no la cambie sin motivo.
        if (!err?.status) {
          mensaje = 'No hay conexión con el servidor. Revisa tu internet y vuelve a intentarlo.';
        } else if (err.status >= 500) {
          mensaje = 'El servidor tuvo un problema. Intenta de nuevo en unos minutos.';
        }

        if (
          err?.status &&
          err.error &&
          err.error.errors
        ) {

          const keys =
            Object.keys(err.error.errors);

          if (keys.length > 0) {

            const primerError =
              err.error.errors[keys[0]];

            mensaje =
              Array.isArray(primerError)
                ? primerError[0]
                : primerError;
          }
        }

        this.errorMensaje = mensaje;

        await this.mostrarToast(
          mensaje,
          'danger'
        );

      }

    });

  }

  private async mostrarToast(
    mensaje: string,
    color: 'success' | 'danger' | 'warning'
  ) {

    await this.feedback.show(mensaje, color as FeedbackType);

  }

  /** Demo: indica a qué PC conectarse sin generar otro APK. */
  async configurarServidor() {
    const alerta = await this.alertController.create({
      header: 'Servidor',
      message: 'Escribe la IP del PC donde corre el backend.',
      inputs: [{
        name: 'servidor',
        type: 'text',
        placeholder: 'Ej: 192.168.43.20',
        value: obtenerServidor() || ''
      }],
      buttons: [
        { text: 'Cancelar', role: 'cancel' },
        {
          text: 'Restablecer',
          handler: () => {
            guardarServidor(null);
            void this.mostrarToast('Se usará el servidor que trae la app.', 'success');
          }
        },
        {
          text: 'Probar y guardar',
          handler: (datos: { servidor: string }) => this.probarYGuardarServidor(datos.servidor)
        }
      ]
    });
    await alerta.present();
  }

  /** Devuelve false para dejar abierta la ventana y poder corregir la dirección. */
  private async probarYGuardarServidor(texto: string): Promise<boolean> {
    const base = normalizarServidor(texto);
    if (!base) {
      await this.mostrarToast('Esa dirección no es válida.', 'warning');
      return false;
    }
    try {
      await firstValueFrom(this.http.get(`${base}/api/auth/login/`).pipe(timeout(5000)));
    } catch (err: any) {
      // Cualquier respuesta HTTP, como el 405 de este endpoint, confirma que el servidor contesta.
      if (!err?.status) {
        await this.mostrarToast(`No se pudo conectar con ${base}. Revisa la red y el firewall.`, 'danger');
        return false;
      }
    }
    guardarServidor(base);
    await this.mostrarToast(`Conectado a ${base}.`, 'success');
    return true;
  }

  // Va directo a elegir usuario: el historial puede estar vacío tras cerrar sesión o reabrir la app.
  volver() {
    void this.navController.navigateRoot('/home', { animationDirection: 'back' });
  }

}
