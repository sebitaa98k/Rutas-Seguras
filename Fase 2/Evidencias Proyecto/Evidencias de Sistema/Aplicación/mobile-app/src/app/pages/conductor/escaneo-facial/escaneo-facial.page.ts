import { Component, OnInit, OnDestroy, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { NotificationService } from '../../../services/notification.service';
import {
  IonContent,
  IonSpinner,
  IonMenuToggle,
  IonIcon,
  IonToast,
  AlertController
} from '@ionic/angular/standalone';
import { aplicarEspejo, restriccionOtraCamara } from '../../../utils/camara.util';
import { addIcons } from 'ionicons';
import {
  menuOutline,
  scanOutline,
  cameraOutline,
  cameraReverseOutline,
  checkmarkCircleOutline,
  alertCircleOutline,
  personOutline,
  schoolOutline,
  arrowBackOutline,
  refreshOutline,
  closeCircleOutline,
  busOutline,
  checkmarkDoneCircleOutline,
  swapHorizontalOutline,
  shieldCheckmarkOutline,
  fingerPrintOutline
} from 'ionicons/icons';

addIcons({
  menuOutline,
  scanOutline,
  cameraOutline,
  cameraReverseOutline,
  checkmarkCircleOutline,
  alertCircleOutline,
  personOutline,
  schoolOutline,
  arrowBackOutline,
  refreshOutline,
  closeCircleOutline,
  busOutline,
  checkmarkDoneCircleOutline,
  swapHorizontalOutline,
  shieldCheckmarkOutline,
  fingerPrintOutline
});

export interface ResultadoFacial {
  coincidencia: boolean;
  score?: number;
  similitud_porcentaje?: number;
  tipo_identificado?: string;
  nombre_identificado?: string;
  rut_identificado?: string;
  estudiante_id?: number;
  estudiante_nombre?: string;
  colegio?: string;
  curso?: string;
  relacion?: string;
  mensaje: string;
  motivo?: string;
  evento_registrado?: boolean;
  requiere_verificacion_alternativa?: boolean;
  abordaje?: ResultadoAbordaje;
  entrega?: { estudiante_nombre: string; mensaje: string };
}

export interface ResultadoAbordaje {
  mensaje: string;
  estudiante_nombre: string;
  fuera_de_domicilio: boolean;
  tenia_aviso_inasistencia?: boolean;
  ya_registrado: boolean;
  todas_completadas: boolean;
  siguiente_parada: { estudiante_id: number; estudiante_nombre: string; direccion: string } | null;
}

// Tiempo que se muestra "Juan subió" antes de volver solo a la ruta.
const ESPERA_VOLVER_MS = 3500;
const VIDEO_FACIAL: MediaTrackConstraints = { width: { ideal: 640 }, height: { ideal: 480 } };

@Component({
  selector: 'app-escaneo-facial',
  templateUrl: './escaneo-facial.page.html',
  styleUrls: ['./escaneo-facial.page.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    IonContent,
    IonSpinner,
    IonMenuToggle,
    IonIcon,
    IonToast
  ]
})
export class EscaneoFacialPage implements OnInit, OnDestroy {

  @ViewChild('videoElement') videoElement!: ElementRef<HTMLVideoElement>;
  @ViewChild('canvasElement') canvasElement!: ElementRef<HTMLCanvasElement>;

  camaraActiva: boolean = false;
  cargandoCamara: boolean = false;
  procesandoEscaneo: boolean = false;
  errorCamara: string = '';

  tipoAccion: 'abordar' | 'entregar' = 'abordar';

  resultadoBackend: ResultadoFacial | null = null;
  confirmado: boolean = false;
  ultimaCapturaBase64: string = '';
  /** Vuelta: último niño registrado; la cámara sigue abierta para el siguiente. */
  ultimaSubida: string = '';

  mensajeToast: string = '';
  mostrarToast: boolean = false;
  colorToast: string = 'success';

  private stream: MediaStream | null = null;
  private restriccionCamara: MediaTrackConstraints = { ...VIDEO_FACIAL, facingMode: 'environment' };
  private volverTimer?: ReturnType<typeof setTimeout>;
  readonly rutaId: number | null;
  readonly estudianteId: number | null;
  readonly estudianteNombre: string;
  /** Vuelta: sin niño elegido, se confirma a quién reconoció antes de registrarlo. */
  readonly subidaGeneral: boolean;

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private notificationService: NotificationService,
    private alertController: AlertController
  ) {
    this.subidaGeneral = this.route.snapshot.queryParamMap.get('subida_general') === '1';
    const rutaId = Number(this.route.snapshot.queryParamMap.get('ruta_id'));
    const estudianteId = Number(this.route.snapshot.queryParamMap.get('estudiante_id'));
    this.rutaId = Number.isInteger(rutaId) && rutaId > 0 ? rutaId : null;
    this.estudianteId = Number.isInteger(estudianteId) && estudianteId > 0 ? estudianteId : null;
    this.estudianteNombre = this.route.snapshot.queryParamMap.get('estudiante_nombre') || '';
    const modo = this.route.snapshot.queryParamMap.get('modo');
    if (modo === 'entregar') this.tipoAccion = 'entregar';
  }

  private get contextoSeleccionado(): { rutaId: number; estudianteId: number } | undefined {
    return this.rutaId && this.estudianteId
      ? { rutaId: this.rutaId, estudianteId: this.estudianteId }
      : undefined;
  }

  ngOnInit() {
    this.iniciarCamara();
  }

  ionViewWillEnter() {
    this.iniciarCamara();
  }

  ngOnDestroy() {
    this.detenerCamara();
    this.cancelarRegresoAutomatico();
  }

  ionViewWillLeave() {
    this.detenerCamara();
    this.cancelarRegresoAutomatico();
  }

  // Ionic reutiliza la página: el próximo estudiante no debe ver el resultado del anterior.
  ionViewDidLeave() {
    this.resetearEscaneo();
  }

  async iniciarCamara() {
    // ngOnInit e ionViewWillEnter llaman ambos: una segunda cámara dejaría la primera encendida.
    if (this.cargandoCamara || this.stream) return;

    this.cargandoCamara = true;
    this.errorCamara = '';

    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        this.stream = await navigator.mediaDevices.getUserMedia({ video: this.restriccionCamara });

        if (this.videoElement && this.videoElement.nativeElement) {
          this.videoElement.nativeElement.srcObject = this.stream;
          aplicarEspejo(this.videoElement.nativeElement, this.stream);
          await this.videoElement.nativeElement.play();
        }
        this.camaraActiva = true;
      } else {
        this.errorCamara = 'El dispositivo o navegador no soporta acceso directo a cámara web.';
      }
    } catch (err: any) {
      console.warn('[EscaneoFacial] Cámara no accesible:', err);
      this.errorCamara = 'No se pudo acceder a la cámara. Revisa los permisos del navegador.';
    } finally {
      this.cargandoCamara = false;
    }
  }

  async alternarCamara() {
    if (this.cargandoCamara || this.procesandoEscaneo) return;

    const restriccion = await restriccionOtraCamara(this.stream?.getVideoTracks()[0], VIDEO_FACIAL);
    if (!restriccion) {
      this.lanzarToast('Este dispositivo tiene una sola cámara.', 'warning');
      return;
    }
    this.restriccionCamara = restriccion;
    // Android no abre una cámara mientras otra sigue activa.
    this.detenerCamara();
    await this.iniciarCamara();
  }

  detenerCamara() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    this.camaraActiva = false;
  }

  capturarYProcesarRostro() {
    if (!this.camaraActiva || !this.videoElement || !this.canvasElement) {
      this.lanzarToast('La cámara debe estar activa para realizar la captura biométrica.', 'warning');
      return;
    }

    const video = this.videoElement.nativeElement;
    const canvas = this.canvasElement.nativeElement;

    if (video.videoWidth === 0 || video.videoHeight === 0) {
      this.lanzarToast('Esperando transmisión de video de cámara...', 'warning');
      return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imagenBase64 = canvas.toDataURL('image/jpeg', 0.85);
    this.ultimaCapturaBase64 = imagenBase64;

    this.procesandoEscaneo = true;
    this.resultadoBackend = null;

    // Un rostro aprobado registra la subida o la entrega de inmediato (sin pasos extra).
    this.registrarEscaneo(imagenBase64);
  }

  private registrarEscaneo(imagenBase64: string, confirmar: boolean = !this.subidaGeneral) {
    this.notificationService.escaneoFacial(imagenBase64, this.tipoAccion, confirmar, this.contextoSeleccionado).subscribe({
      next: (res: ResultadoFacial) => {
        this.procesandoEscaneo = false;
        if (this.subidaGeneral && res.coincidencia && res.abordaje) {
          const abordaje = res.abordaje;
          this.resetearEscaneo();
          this.ultimaSubida = abordaje.ya_registrado ? `${abordaje.estudiante_nombre} ya estaba a bordo.` : abordaje.mensaje;
          this.lanzarToast(this.ultimaSubida, abordaje.ya_registrado || abordaje.tenia_aviso_inasistencia ? 'warning' : 'success');
          return;
        }
        this.resultadoBackend = res;
        // Falta que el conductor confirme a quién reconoció.
        if (this.subidaGeneral && res.coincidencia && !res.evento_registrado) return;
        if (!res.coincidencia) {
          this.lanzarToast(res.mensaje || 'Rostro no identificado.', 'danger');
          return;
        }
        this.confirmado = !!res.evento_registrado;
        const abordaje = res.abordaje;
        if (abordaje) {
          const advertencia = abordaje.fuera_de_domicilio || abordaje.tenia_aviso_inasistencia;
          this.lanzarToast(abordaje.mensaje, advertencia ? 'warning' : 'success');
        } else if (res.entrega) {
          this.lanzarToast(res.entrega.mensaje, 'success');
        }
        if (abordaje || res.entrega) {
          this.volverTimer = setTimeout(() => this.volverARuta(), ESPERA_VOLVER_MS);
        }
      },
      error: (err) => {
        this.procesandoEscaneo = false;
        console.error('[EscaneoFacial] Error al registrar el escaneo:', err);
        this.lanzarToast(err?.error?.message || 'No se pudo registrar el escaneo.', 'danger');
      }
    });
  }

  confirmarSubida() {
    if (!this.ultimaCapturaBase64 || this.procesandoEscaneo) return;
    this.procesandoEscaneo = true;
    this.registrarEscaneo(this.ultimaCapturaBase64, true);
  }

  noEsEl() {
    this.resetearEscaneo();
    this.lanzarToast('Escaneo descartado. No se registró nada.', 'warning');
  }

  private cancelarRegresoAutomatico() {
    if (this.volverTimer) {
      clearTimeout(this.volverTimer);
      this.volverTimer = undefined;
    }
  }

  resetearEscaneo() {
    this.cancelarRegresoAutomatico();
    this.resultadoBackend = null;
    this.confirmado = false;
    this.ultimaCapturaBase64 = '';
  }

  /** Sin niño elegido, primero se indica quién sube y después se escanea el QR del inspector. */
  private elegirEstudianteParaQR() {
    this.notificationService.obtenerMiRuta().subscribe({
      next: async (ruta: any) => {
        const pendientes = (ruta?.paradas || []).filter((parada: any) => !parada.abordo);
        if (!pendientes.length) {
          this.lanzarToast('No quedan estudiantes por subir.', 'warning');
          return;
        }
        const alerta = await this.alertController.create({
          header: '¿Quién sube?',
          inputs: pendientes.map((parada: any) => ({
            type: 'radio' as const,
            label: parada.estudiante_nombre,
            value: parada.estudiante_id
          })),
          buttons: [
            { text: 'Cancelar', role: 'cancel' },
            {
              text: 'Escanear QR',
              handler: (estudianteId: number) => {
                if (!estudianteId) return false;
                this.detenerCamara();
                this.router.navigate(['/conductor/escanear-qr'], {
                  queryParams: { validacion_institucional: 1, ruta_id: this.rutaId, estudiante_id: estudianteId }
                });
                return true;
              }
            }
          ]
        });
        await alerta.present();
      },
      error: () => this.lanzarToast('No se pudo cargar la lista de estudiantes.', 'danger')
    });
  }

  usarCodigoQR() {
    if (this.subidaGeneral) {
      this.elegirEstudianteParaQR();
      return;
    }
    this.cancelarRegresoAutomatico();
    this.detenerCamara();
    // En la ida no hay estudiante preseleccionado: el QR indica quién sube.
    if (!this.rutaId || !this.estudianteId) {
      this.router.navigate(['/conductor/escanear-qr']);
      return;
    }
    this.router.navigate(['/conductor/escanear-qr'], {
      queryParams: this.tipoAccion === 'entregar' ? {
        entrega_domicilio: 1,
        estudiante_id: this.estudianteId,
      } : {
        validacion_institucional: 1,
        ruta_id: this.rutaId,
        estudiante_id: this.estudianteId,
      }
    });
  }

  volverARuta() {
    this.cancelarRegresoAutomatico();
    const abordaje = this.resultadoBackend?.abordaje;
    const entrega = this.resultadoBackend?.entrega;
    this.router.navigate(['/conductor/ruta-activa'], {
      state: abordaje
        ? {
            avisoAbordaje: abordaje.mensaje,
            fueraDeDomicilio: abordaje.fuera_de_domicilio || !!abordaje.tenia_aviso_inasistencia
          }
        : entrega
          ? { avisoAbordaje: entrega.mensaje }
          : {}
    });
  }

  private lanzarToast(mensaje: string, color: string = 'success') {
    this.mensajeToast = mensaje;
    this.colorToast = color;
    this.mostrarToast = true;
  }
}
