import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import * as QRCode from 'qrcode';
import { firstValueFrom } from 'rxjs';

import {
  IonContent,
  IonButton,
  IonSpinner,
  IonMenuToggle,
  IonIcon,
  IonToast
} from '@ionic/angular/standalone';

import { addIcons } from 'ionicons';
import {
  menuOutline,
  qrCodeOutline,
  refreshOutline,
  copyOutline,
  downloadOutline,
  informationCircleOutline,
  personOutline,
  schoolOutline,
  checkmarkCircleOutline,
  swapHorizontalOutline,
  sparklesOutline,
  arrowBackOutline,
  shieldCheckmarkOutline,
  flashOutline,
  peopleOutline,
  timeOutline,
  alertCircleOutline
} from 'ionicons/icons';

import { AuthService, Usuario } from '../../../services/auth.service';
import { EstudianteService, Estudiante } from '../../../services/estudiante.service';

addIcons({
  menuOutline,
  qrCodeOutline,
  refreshOutline,
  copyOutline,
  downloadOutline,
  informationCircleOutline,
  personOutline,
  schoolOutline,
  checkmarkCircleOutline,
  swapHorizontalOutline,
  sparklesOutline,
  arrowBackOutline,
  shieldCheckmarkOutline,
  flashOutline,
  peopleOutline,
  timeOutline,
  alertCircleOutline
});

@Component({
  selector: 'app-mi-qr',
  templateUrl: './mi-qr.page.html',
  styleUrls: ['./mi-qr.page.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    IonContent,
    IonButton,
    IonSpinner,
    IonMenuToggle,
    IonIcon,
    IonToast
  ]
})
export class MiQrPage implements OnInit, OnDestroy {

  usuario: Usuario | null = null;
  estudiantes: Estudiante[] = [];

  /** Hay un solo QR, el del apoderado: sirve para la subida (ida) y para recibir (vuelta). */
  readonly modo = 'apoderado' as const;
  cargandoEstudiantes: boolean = false;

  qrPayload: string = '';
  qrSvgSafe: SafeHtml = '';
  qrImageUrl: string = '';

  timestampHash: number = Date.now();
  duracionMinutos: number = 5; // lo disminui a 5min en vez de 15
  expiracionTs: number = 0;
  tiempoRestanteTexto: string = '15:00';
  esValido: boolean = true;
  private timerInterval: any = null;

  toastMensaje: string = '';
  toastColor: string = 'success';
  mostrarToast: boolean = false;

  constructor(
    private authService: AuthService,
    private estudianteService: EstudianteService,
    private sanitizer: DomSanitizer
  ) { }

  ngOnInit() {
    this.usuario = this.authService.getUsuario();
    this.cargarEstudiantes();
    this.generarQR();
  }

  ionViewWillEnter() {
    this.usuario = this.authService.getUsuario();
    this.cargarEstudiantes();
    this.generarQR();
  }

  ngOnDestroy() {
    this.detenerTimer();
  }

  ionViewWillLeave() {
    this.detenerTimer();
  }

  cargarEstudiantes() {
    this.cargandoEstudiantes = true;
    this.estudianteService.obtenerEstudiantes().subscribe({
      next: (data) => {
        this.estudiantes = data;
        this.cargandoEstudiantes = false;
      },
      error: (err) => {
        this.cargandoEstudiantes = false;
        console.error('Error cargando estudiantes para QR:', err);
      }
    });
  }

  get nombresHijos(): string {
    return this.estudiantes.map(est => est.nombre).join(', ');
  }

  regenerarQR() {
    this.generarQR();
    this.lanzarNotificacion('Código QR actualizado por 5 minutos', 'primary');
  }

  async generarQR() {
    try {
      const respuesta = await firstValueFrom(
        this.authService.generarQREntrega(undefined, 'entrega')
      );
      this.timestampHash = Date.now();
      this.expiracionTs = respuesta.valido_hasta;
      this.esValido = true;
      this.qrPayload = respuesta.qr_payload;
      const opciones = { margin: 2, color: { dark: '#244642', light: '#ffffff' } };
      const svgMarkup = await QRCode.toString(this.qrPayload, { ...opciones, type: 'svg' });
      this.qrSvgSafe = this.sanitizer.bypassSecurityTrustHtml(svgMarkup);
      this.qrImageUrl = await QRCode.toDataURL(this.qrPayload, { ...opciones, width: 400 });
      this.iniciarTimer();
    } catch (err) {
      this.esValido = false;
      this.lanzarNotificacion('No se pudo generar el QR seguro', 'danger');
      console.error('[MiQR] Error solicitando QR firmado:', err);
    }
  }

  private iniciarTimer() {
    this.detenerTimer();
    this.actualizarConteo();
    this.timerInterval = setInterval(() => {
      this.actualizarConteo();
    }, 1000);
  }

  private detenerTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }

  private actualizarConteo() {
    const ahora = Date.now();
    const diffMs = this.expiracionTs - ahora;

    if (diffMs <= 0) {
      this.esValido = false;
      this.tiempoRestanteTexto = '00:00';
      this.detenerTimer();
    } else {
      const min = Math.floor(diffMs / 60000);
      const sec = Math.floor((diffMs % 60000) / 1000);
      this.tiempoRestanteTexto = `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
    }
  }

  copiarPayload() {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(this.qrPayload).then(() => {
        this.lanzarNotificacion('Código QR copiado al portapapeles', 'success');
      }).catch(() => {
        this.lanzarNotificacion('No se pudo copiar automáticamente', 'danger');
      });
    } else {
      this.lanzarNotificacion('Copia no soportada en este navegador', 'warning');
    }
  }

  descargarQR() {
    const a = document.createElement('a');
    a.href = this.qrImageUrl;
    a.download = `QR_Apoderado_${this.usuario?.first_name || 'Apoderado'}.png`;
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    this.lanzarNotificacion('Descargando imagen QR...', 'success');
  }

  get codigoSeguridadActual(): string {
    return `APOD-${(this.usuario?.id || 1).toString().padStart(4, '0')}-${this.timestampHash.toString().slice(-4)}`;
  }

  private lanzarNotificacion(mensaje: string, color: string = 'success') {
    this.toastMensaje = mensaje;
    this.toastColor = color;
    this.mostrarToast = true;
  }
}
