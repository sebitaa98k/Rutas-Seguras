import { AfterViewInit, Component, OnDestroy, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { NotificationService } from '../../../services/notification.service';
import { environment } from '../../../../environments/environment';
import jsQR from 'jsqr';
import { aplicarEspejo, restriccionOtraCamara } from '../../../utils/camara.util';
import { ConfirmarNinosComponent } from '../../../components/confirmar-ninos/confirmar-ninos.component';

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
  cameraOutline,
  cameraReverseOutline,
  flashOutline,
  flashOffOutline,
  checkmarkCircleOutline,
  alertCircleOutline,
  personOutline,
  schoolOutline,
  locationOutline,
  arrowBackOutline,
  refreshOutline,
  closeCircleOutline,
  busOutline,
  createOutline,
  checkmarkDoneCircleOutline,
  timeOutline,
  checkboxOutline,
  squareOutline,
  peopleOutline,
  shieldCheckmarkOutline
} from 'ionicons/icons';

addIcons({
  menuOutline,
  qrCodeOutline,
  cameraOutline,
  cameraReverseOutline,
  flashOutline,
  flashOffOutline,
  checkmarkCircleOutline,
  alertCircleOutline,
  personOutline,
  schoolOutline,
  locationOutline,
  arrowBackOutline,
  refreshOutline,
  closeCircleOutline,
  busOutline,
  createOutline,
  checkmarkDoneCircleOutline,
  timeOutline,
  checkboxOutline,
  squareOutline,
  peopleOutline,
  shieldCheckmarkOutline
});

// Tiempo para leer el resultado antes de volver solo a la ruta (igual que el escaneo facial).
const ESPERA_VOLVER_MS = 3500;

const VIDEO_QR: MediaTrackConstraints = { width: { ideal: 1280 }, height: { ideal: 720 } };

export interface QrDataEscaneado {
  tipo: 'APODERADO' | 'ESTUDIANTE' | 'DELEGADO_AUTORIZADO' | 'RUTAS_SEGURAS_ABORDAJE' | 'RUTAS_SEGURAS_ENTREGA';
  token?: string;
  id_usuario?: number;
  id_estudiante?: number;
  rut?: string;
  rut_estudiante?: string;
  nombre?: string;
  nombre_estudiante?: string;
  apoderado_nombre?: string;
  email?: string;
  colegio?: string;
  curso?: string;
  ts?: number;
  valido_hasta?: number;
  codigo_seguridad?: string;
}

export interface EstudianteEntregaItem {
  id: number;
  nombre: string;
  rut: string;
  colegio?: string;
  curso?: string;
  estado?: string;
  seleccionado: boolean;
}

export interface PersonaEntregaInfo {
  id_usuario?: number;
  rut: string;
  nombre: string;
  tipo: string;
  rol?: string;
}

@Component({
  selector: 'app-escanear-qr',
  templateUrl: './escanear-qr.page.html',
  styleUrls: ['./escanear-qr.page.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    IonContent,
    IonButton,
    IonSpinner,
    IonMenuToggle,
    IonIcon,
    IonToast,
    ConfirmarNinosComponent
  ]
})
export class EscanearQrPage implements AfterViewInit, OnDestroy {

  @ViewChild('videoElement') videoElement!: ElementRef<HTMLVideoElement>;

  camaraActiva: boolean = false;
  flashEncendido: boolean = false;
  cargandoCamara: boolean = false;
  errorCamara: string = '';

  codigoManual: string = '';
  readonly mostrarHerramientasDesarrollo = !environment.production;

  qrEscaneado: QrDataEscaneado | null = null;
  qrEsValido: boolean = false;
  errorValidacion: string = '';

  tipoAccion: 'RECEPCION' | 'ENTREGA' = 'RECEPCION';
  notaAdicional: string = '';

  // Flujo entrega múltiple Apoderado / Delegado
  modoEntregaMultiple: boolean = false;
  cargandoConsultaEntrega: boolean = false;
  personaEntrega: PersonaEntregaInfo | null = null;
  estudiantesEntrega: EstudianteEntregaItem[] = [];
  entregaInstitucional: boolean = false;
  /** Ida: la persona autorizada manda al estudiante al furgón. */
  abordajeAutorizado: boolean = false;
  modoValidacionInstitucional: boolean = false;
  /** Vuelta: el estudiante ya va a bordo y se entrega a quien lo recibe en su casa. */
  modoEntregaDomicilio: boolean = false;
  estudianteIdInstitucional: number | null = null;
  recepcionInstitucionalRequerida: boolean = false;
  finalizarRutaDespuesRecepcion: boolean = false;
  rutaIdParaFinalizar: number | null = null;
  finalizandoRuta: boolean = false;

  confirmacionExitosa: boolean = false;
  mensajeToast: string = '';
  mostrarToast: boolean = false;
  colorToast: string = 'success';

  private stream: MediaStream | null = null;
  private restriccionCamara: MediaTrackConstraints = { ...VIDEO_QR, facingMode: { ideal: 'environment' } };
  private detectorQR: any = null;
  // Respaldo cuando el WebView no trae BarcodeDetector (muchos Android y Chrome de escritorio).
  private lienzoQR: HTMLCanvasElement | null = null;
  private frameEscaneo: number | null = null;
  private detectandoQR = false;
  private volverTimer?: ReturnType<typeof setTimeout>;
  private ultimoAbordaje: { mensaje: string; advertencia: boolean } | null = null;

  constructor(
    private router: Router,
    private route: ActivatedRoute,
    private notificationService: NotificationService
  ) {
    const params = this.route.snapshot.queryParamMap;
    this.recepcionInstitucionalRequerida = params.get('recepcion_institucional') === '1';
    this.modoValidacionInstitucional = params.get('validacion_institucional') === '1';
    this.modoEntregaDomicilio = params.get('entrega_domicilio') === '1';
    this.finalizarRutaDespuesRecepcion = params.get('finalizar_ruta') === '1';
    const rutaId = Number(params.get('ruta_id'));
    this.rutaIdParaFinalizar = Number.isInteger(rutaId) && rutaId > 0 ? rutaId : null;
    const estudianteId = Number(params.get('estudiante_id'));
    this.estudianteIdInstitucional = Number.isInteger(estudianteId) && estudianteId > 0
      ? estudianteId : null;
  }

  ngAfterViewInit() {
    this.iniciarCamara();
  }

  ionViewDidEnter() {
    this.iniciarCamara();
  }

  ngOnDestroy() {
    this.cancelarRegresoAutomatico();
    this.detenerCamara();
  }

  ionViewWillLeave() {
    this.cancelarRegresoAutomatico();
    this.detenerCamara();
  }

  // Ionic reutiliza la página: el próximo estudiante no debe ver el resultado del anterior.
  ionViewDidLeave() {
    this.limpiarEscaneo();
  }

  async iniciarCamara() {
    if (this.cargandoCamara || this.stream) {
      await this.conectarStreamAlVideo();
      return;
    }

    this.cargandoCamara = true;
    this.errorCamara = '';

    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        this.stream = await navigator.mediaDevices.getUserMedia({
          video: this.restriccionCamara,
          audio: false
        });

        await this.conectarStreamAlVideo();
        this.camaraActiva = true;
        this.iniciarLecturaQR();
      } else {
        this.errorCamara = 'El dispositivo no permite acceder a la cámara.';
      }
    } catch (err: any) {
      console.warn('Cámara no accesible o permiso denegado:', err);
      const permisoDenegado = err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError';
      this.errorCamara = permisoDenegado
        ? 'El permiso de cámara está desactivado. Habilítalo en Ajustes > Aplicaciones > Rutas Seguras > Permisos.'
        : 'No se pudo iniciar la cámara trasera. Cierra otras aplicaciones que puedan estar utilizándola y reintenta.';
      this.detenerCamara();
    } finally {
      this.cargandoCamara = false;
    }
  }

  async alternarCamara() {
    if (this.cargandoCamara) return;

    const restriccion = await restriccionOtraCamara(this.stream?.getVideoTracks()[0], VIDEO_QR);
    if (!restriccion) {
      this.lanzarToast('Este dispositivo tiene una sola cámara.', 'warning');
      return;
    }
    this.restriccionCamara = restriccion;
    this.flashEncendido = false;
    // Android no abre una cámara mientras otra sigue activa.
    this.detenerCamara();
    await this.iniciarCamara();
  }

  private async conectarStreamAlVideo(): Promise<void> {
    if (!this.stream || !this.videoElement?.nativeElement) return;

    const video = this.videoElement.nativeElement;
    video.srcObject = this.stream;
    aplicarEspejo(video, this.stream);
    video.muted = true;
    video.playsInline = true;
    await video.play();
  }

  private iniciarLecturaQR(): void {
    const BarcodeDetector = (window as any).BarcodeDetector;
    this.detectorQR = BarcodeDetector
      ? new BarcodeDetector({ formats: ['qr_code'] })
      : { detect: (video: HTMLVideoElement) => this.detectarConJsQR(video) };
    this.programarSiguienteLectura();
  }

  private detectarConJsQR(video: HTMLVideoElement): { rawValue: string }[] {
    // Se reduce el fotograma: jsQR es más lento que el detector nativo y un QR en pantalla se lee igual.
    const escala = Math.min(1, 640 / (video.videoWidth || 640));
    const ancho = Math.round(video.videoWidth * escala);
    const alto = Math.round(video.videoHeight * escala);
    if (!ancho || !alto) return [];

    this.lienzoQR ??= document.createElement('canvas');
    this.lienzoQR.width = ancho;
    this.lienzoQR.height = alto;
    const contexto = this.lienzoQR.getContext('2d', { willReadFrequently: true });
    if (!contexto) return [];

    contexto.drawImage(video, 0, 0, ancho, alto);
    const imagen = contexto.getImageData(0, 0, ancho, alto);
    const codigo = jsQR(imagen.data, ancho, alto, { inversionAttempts: 'dontInvert' });
    return codigo?.data ? [{ rawValue: codigo.data }] : [];
  }

  private programarSiguienteLectura(): void {
    if (!this.camaraActiva || !this.detectorQR) return;

    this.frameEscaneo = requestAnimationFrame(async () => {
      const video = this.videoElement?.nativeElement;
      if (video && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && !this.detectandoQR) {
        this.detectandoQR = true;
        try {
          const codigos = await this.detectorQR.detect(video);
          const contenido = codigos?.[0]?.rawValue;
          if (contenido) {
            this.procesarTextoQR(contenido);
            return;
          }
        } catch (error) {
          console.warn('[EscanearQR] No se pudo analizar este fotograma:', error);
        } finally {
          this.detectandoQR = false;
        }
      }
      this.programarSiguienteLectura();
    });
  }

  detenerCamara() {
    if (this.frameEscaneo !== null) {
      cancelAnimationFrame(this.frameEscaneo);
      this.frameEscaneo = null;
    }
    this.detectorQR = null;
    this.detectandoQR = false;
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    this.camaraActiva = false;
  }

  async toggleFlash() {
    const track = this.stream?.getVideoTracks()[0];
    const capacidades = track?.getCapabilities?.() as MediaTrackCapabilities & { torch?: boolean };
    if (!track || !capacidades?.torch) {
      this.lanzarToast('La linterna no está disponible en esta cámara.', 'warning');
      return;
    }

    this.flashEncendido = !this.flashEncendido;
    try {
      await track.applyConstraints({ advanced: [{ torch: this.flashEncendido } as any] });
      this.lanzarToast(`Flash ${this.flashEncendido ? 'encendido' : 'apagado'}`, 'medium');
    } catch {
      this.flashEncendido = false;
      this.lanzarToast('No fue posible controlar la linterna.', 'warning');
    }
  }

  procesarTextoQR(textoQR: string) {
    this.errorValidacion = '';
    this.qrEscaneado = null;
    this.modoEntregaMultiple = false;
    this.personaEntrega = null;
    this.estudiantesEntrega = [];
    this.entregaInstitucional = false;
    this.abordajeAutorizado = false;

    try {
      const data: QrDataEscaneado = JSON.parse(textoQR);

      if (
        !data.token
        || !['RUTAS_SEGURAS_ABORDAJE', 'RUTAS_SEGURAS_ENTREGA'].includes(data.tipo)
      ) {
        throw new Error('Formato de código QR inválido');
      }

      this.detenerCamara();

      const ahora = Date.now();
      if (data.valido_hasta && ahora > data.valido_hasta) {
        this.qrEsValido = false;
        this.errorValidacion = 'El código QR ha expirado (duración máxima: 5 min). Pídele a la persona que lo renueve.';
        this.qrEscaneado = data;
        return;
      }

      this.qrEscaneado = data;

      if (this.modoEntregaDomicilio && data.tipo === 'RUTAS_SEGURAS_ABORDAJE') {
        this.qrEsValido = false;
        this.errorValidacion = 'Este es un QR antiguo de subida. Para entregar, escanea el QR del apoderado o de la persona autorizada.';
        return;
      }

      // Si falla la biometría en la vuelta, la subida la valida el inspector con su propio QR.
      if (this.modoValidacionInstitucional) {
        if (
          data.tipo !== 'RUTAS_SEGURAS_ENTREGA'
          || !this.rutaIdParaFinalizar
          || !this.estudianteIdInstitucional
        ) {
          this.qrEsValido = false;
          this.errorValidacion = 'Escanea el QR del inspector, no el del estudiante.';
          return;
        }
        this.cargandoConsultaEntrega = true;
        this.notificationService.consultarValidacionInstitucional(
          this.rutaIdParaFinalizar,
          this.estudianteIdInstitucional,
          textoQR
        ).subscribe({
          next: (res: any) => {
            this.cargandoConsultaEntrega = false;
            this.qrEsValido = !!res.valido;
            this.modoEntregaMultiple = true;
            this.entregaInstitucional = true;
            this.tipoAccion = 'RECEPCION';
            this.personaEntrega = res.delegado;
            this.estudiantesEntrega = [{ ...res.estudiante, seleccionado: true }];
            this.lanzarToast('QR institucional validado correctamente.', 'success');
          },
          error: (err: any) => {
            this.cargandoConsultaEntrega = false;
            this.qrEsValido = false;
            this.errorValidacion = err?.error?.message || 'No se pudo validar el QR institucional.';
          }
        });
        return;
      }

      // Si es Apoderado o Delegado, realizamos la consulta multi-estudiante al backend
      if (data.tipo === 'RUTAS_SEGURAS_ENTREGA') {
        this.cargandoConsultaEntrega = true;
        this.notificationService.consultarQREntrega(textoQR).subscribe({
          next: (res: any) => {
            this.cargandoConsultaEntrega = false;
            if (res.valido) {
              if (this.recepcionInstitucionalRequerida && !res.entrega_institucional) {
                this.qrEsValido = false;
                this.errorValidacion = 'Para finalizar esta ruta debes escanear el QR del delegado o inspector institucional del colegio.';
                return;
              }
              this.qrEsValido = true;
              this.modoEntregaMultiple = true;
              this.tipoAccion = 'ENTREGA';
              this.personaEntrega = res.persona;
              this.entregaInstitucional = !!res.entrega_institucional;
              this.abordajeAutorizado = !!res.abordaje_autorizado;
              // Si viene de una parada y ese niño está en la lista, se preselecciona solo a él;
              // si no, quedan todos marcados (p. ej. hermanos que suben juntos).
              const lista = res.estudiantes || [];
              const preferido = this.estudianteIdInstitucional;
              const preferidoEnLista = !!preferido && lista.some((e: any) => e.id === preferido);
              this.estudiantesEntrega = lista.map((e: any) => ({
                ...e,
                seleccionado: !preferidoEnLista || e.id === preferido
              }));
              this.lanzarToast(this.abordajeAutorizado ? 'QR validado: elige quién sube.' : '¡QR de Recepción validado correctamente!', 'success');
            } else {
              this.qrEsValido = false;
              this.errorValidacion = res.error || 'Código QR no válido o expirado.';
            }
          },
          error: (err: any) => {
            this.cargandoConsultaEntrega = false;
            console.warn('[EscanearQR] Error consultando QR en backend:', err);
            const msgError = err.error?.message
              || err.error?.error
              || (err.status === 0
                ? 'No se pudo conectar con el servidor. Verifica la red y la URL de la API.'
                : 'No se pudo consultar el QR con el servidor.');
            this.qrEsValido = false;
            this.errorValidacion = msgError;
          }
        });
      } else {
        // El backend validará firma, vigencia y pertenencia antes de abordar.
        this.qrEsValido = true;
        this.modoEntregaMultiple = false;
        this.tipoAccion = 'RECEPCION';
        this.lanzarToast('¡Código QR escaneado con éxito!', 'success');
      }

    } catch (e) {
      this.qrEsValido = false;
      this.errorValidacion = 'Código QR no reconocido. Asegúrate de escanear un código generado por Rutas Seguras.';
    }
  }

  toggleEstudianteEntrega(estId: number) {
    if (this.entregaInstitucional) return;
    const item = this.estudiantesEntrega.find(e => e.id === estId);
    if (item) {
      item.seleccionado = !item.seleccionado;
    }
  }

  toggleTodosEstudiantes() {
    if (this.entregaInstitucional) return;
    const todosSeleccionados = this.estudiantesEntrega.every(e => e.seleccionado);
    this.estudiantesEntrega.forEach(e => e.seleccionado = !todosSeleccionados);
  }

  get validandoInstitucional(): boolean {
    return this.modoValidacionInstitucional;
  }

  get totalSeleccionadosCount(): number {
    return this.estudiantesEntrega.filter(e => e.seleccionado).length;
  }

  get todosSeleccionadosState(): boolean {
    return this.estudiantesEntrega.length > 0 && this.estudiantesEntrega.every(e => e.seleccionado);
  }

  procesarManual() {
    if (!this.codigoManual.trim()) return;
    this.procesarTextoQR(this.codigoManual.trim());
  }

  /** Ventana "¿Seguro que son estos niños?" antes de registrar una subida o entrega con QR. */
  confirmandoSeleccion = false;
  /** Evita registrar dos veces si se toca "Sí, confirmar" seguido. */
  enviandoEntrega = false;

  get estudiantesSeleccionados(): EstudianteEntregaItem[] {
    return this.estudiantesEntrega.filter(e => e.seleccionado);
  }

  get estudiantesNoSeleccionados(): EstudianteEntregaItem[] {
    return this.estudiantesEntrega.filter(e => !e.seleccionado);
  }

  /** Solo cuando el conductor elige niños del QR de un apoderado o persona autorizada. */
  get pideConfirmarSeleccion(): boolean {
    return this.modoEntregaMultiple && !this.modoValidacionInstitucional && !this.entregaInstitucional;
  }

  revisarSeleccion() {
    this.confirmandoSeleccion = false;
  }

  aceptarSeleccion() {
    this.confirmandoSeleccion = false;
    this.confirmarEntregaMultiple();
  }

  confirmarRecepcion() {
    if (!this.qrEscaneado || !this.qrEsValido) return;

    if (this.modoEntregaMultiple) {
      if (this.pideConfirmarSeleccion) {
        if (this.totalSeleccionadosCount === 0) {
          this.lanzarToast('Debes seleccionar al menos un estudiante.', 'warning');
          return;
        }
        this.confirmandoSeleccion = true;
        return;
      }
      this.confirmarEntregaMultiple();
      return;
    }

    this.notificationService.escanearQR(JSON.stringify(this.qrEscaneado)).subscribe({
      next: (res: any) => {
        this.fechaConfirmacion = Date.now();
        this.estudianteConfirmado = res?.estudiante || res?.abordaje?.estudiante_nombre || '';
        this.confirmacionExitosa = true;
        // En la ida el backend indica quién subió y quién es el siguiente.
        const abordaje = res?.abordaje;
        const advertencia = !!(abordaje?.fuera_de_domicilio || abordaje?.tenia_aviso_inasistencia);
        this.lanzarToast(
          abordaje?.mensaje || '¡Abordaje / Entrega registrado exitosamente!',
          advertencia ? 'warning' : 'success'
        );
        // Igual que la biometría: tras el abordaje se vuelve sola a la ruta con el aviso.
        if (abordaje?.mensaje) {
          this.ultimoAbordaje = { mensaje: abordaje.mensaje, advertencia };
          this.volverTimer = setTimeout(() => this.volverARuta(), ESPERA_VOLVER_MS);
        }
      },
      error: (err: any) => {
        console.warn('[EscanearQR] Error enviando escaneo a Backend:', err);
        // Se muestra en la tarjeta (ej: "ya subió al furgón") para que no parezca un registro exitoso.
        this.qrEsValido = false;
        this.errorValidacion = err?.error?.message || 'No se pudo registrar el escaneo.';
        this.lanzarToast(this.errorValidacion, err?.status === 409 ? 'warning' : 'danger');
      }
    });
  }

  confirmarEntregaMultiple() {
    if (this.modoValidacionInstitucional) {
      this.confirmarValidacionInstitucional();
      return;
    }
    const seleccionados = this.estudiantesEntrega.filter(e => e.seleccionado);
    if (seleccionados.length === 0) {
      this.lanzarToast('Debes seleccionar al menos un estudiante para confirmar la entrega.', 'warning');
      return;
    }

    if (this.enviandoEntrega) return;
    this.enviandoEntrega = true;
    const estIds = seleccionados.map(e => e.id);
    this.notificationService.confirmarEntregaMultiple(estIds, JSON.stringify(this.qrEscaneado)).subscribe({
      next: (res: any) => {
        this.enviandoEntrega = false;
        if (this.entregaInstitucional && this.finalizarRutaDespuesRecepcion) {
          this.finalizarRutaTrasRecepcion(seleccionados.length);
          return;
        }
        this.fechaConfirmacion ??= Date.now();
        this.confirmacionExitosa = true;
        const mensaje = this.abordajeAutorizado
          ? (res?.message || 'Subida al furgón registrada.')
          : `¡Entrega de ${seleccionados.length} estudiante(s) confirmada exitosamente!`;
        this.lanzarToast(mensaje, 'success');
        this.ultimoAbordaje = { mensaje, advertencia: false };
        this.volverTimer = setTimeout(() => this.volverARuta(), ESPERA_VOLVER_MS);
      },
      error: (err: any) => {
        this.enviandoEntrega = false;
        console.error('[EscanearQR] Error al confirmar entrega múltiple:', err);
        const errorMsg = err.error?.message || err.error?.error || 'Ocurrió un error al registrar la entrega.';
        this.lanzarToast(errorMsg, 'danger');
      }
    });
  }

  confirmarValidacionInstitucional() {
    if (
      !this.qrEscaneado
      || !this.rutaIdParaFinalizar
      || !this.estudianteIdInstitucional
      || this.finalizandoRuta
    ) return;

    this.finalizandoRuta = true;
    this.notificationService.confirmarAbordajeInstitucional(
      this.rutaIdParaFinalizar,
      this.estudianteIdInstitucional,
      JSON.stringify(this.qrEscaneado)
    ).subscribe({
      next: (res: any) => {
        this.finalizandoRuta = false;
        this.fechaConfirmacion ??= Date.now();
        this.confirmacionExitosa = true;
        this.lanzarToast(res?.abordaje?.mensaje || 'Abordaje institucional registrado.', 'success');
      },
      error: (err: any) => {
        this.finalizandoRuta = false;
        this.lanzarToast(err?.error?.message || 'No se pudo registrar el abordaje institucional.', 'danger');
      }
    });
  }

  private finalizarRutaTrasRecepcion(cantidad: number): void {
    this.finalizandoRuta = true;
    this.notificationService.finalizarRuta(this.rutaIdParaFinalizar || undefined).subscribe({
      next: (res: any) => {
        this.finalizandoRuta = false;
        this.fechaConfirmacion ??= Date.now();
        this.confirmacionExitosa = true;
        this.lanzarToast(
          res?.message || `Recepción de ${cantidad} estudiante(s) registrada y ruta finalizada.`,
          'success'
        );
        setTimeout(() => this.router.navigate(['/conductor/inicio']), 1000);
      },
      error: (err: any) => {
        this.finalizandoRuta = false;
        this.fechaConfirmacion ??= Date.now();
        this.confirmacionExitosa = true;
        this.lanzarToast(
          err?.error?.message || 'La recepción fue registrada, pero no se pudo finalizar la ruta. Reintenta desde la ruta activa.',
          'danger'
        );
      }
    });
  }

  resetearEscaneo() {
    this.limpiarEscaneo();
    setTimeout(() => this.iniciarCamara());
  }

  private limpiarEscaneo() {
    this.cancelarRegresoAutomatico();
    this.ultimoAbordaje = null;
    this.fechaConfirmacion = null;
    this.estudianteConfirmado = '';
    this.qrEscaneado = null;
    this.qrEsValido = false;
    this.errorValidacion = '';
    this.confirmacionExitosa = false;
    this.codigoManual = '';
    this.notaAdicional = '';
    this.modoEntregaMultiple = false;
    this.personaEntrega = null;
    this.estudiantesEntrega = [];
    this.entregaInstitucional = false;
    this.abordajeAutorizado = false;
    this.cargandoConsultaEntrega = false;
    this.confirmandoSeleccion = false;
    this.enviandoEntrega = false;
  }

  volverARuta() {
    this.cancelarRegresoAutomatico();
    const abordaje = this.ultimoAbordaje;
    this.ultimoAbordaje = null;
    this.router.navigate(['/conductor/ruta-activa'], {
      state: abordaje ? { avisoAbordaje: abordaje.mensaje, fueraDeDomicilio: abordaje.advertencia } : {}
    });
  }

  private cancelarRegresoAutomatico() {
    if (this.volverTimer) {
      clearTimeout(this.volverTimer);
      this.volverTimer = undefined;
    }
  }

  /** Hora fija del registro: un getter con Date.now() cambiaría en cada detección de cambios (NG0100). */
  fechaConfirmacion: number | null = null;
  /** El QR solo trae un token firmado: el nombre lo informa el backend al confirmar. */
  estudianteConfirmado = '';

  private lanzarToast(mensaje: string, color: string = 'success') {
    this.mensajeToast = mensaje;
    this.colorToast = color;
    this.mostrarToast = true;
  }
}
