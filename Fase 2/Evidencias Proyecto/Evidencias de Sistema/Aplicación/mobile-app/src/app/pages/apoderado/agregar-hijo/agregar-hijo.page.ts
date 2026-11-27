import { Component, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import {
  IonContent,
  IonInput,
  IonItem,
  IonButton,
  IonSpinner,
  IonIcon,
  IonSelect,
  IonSelectOption,
  IonMenuToggle,
  IonToggle
} from '@ionic/angular/standalone';
import { ConsentimientoBiometricoComponent } from '../../../components/consentimiento-biometrico/consentimiento-biometrico.component';

import { addIcons } from 'ionicons';
import { FeedbackService, FeedbackType } from '../../../services/feedback.service';
import { AuthService } from '../../../services/auth.service';

import {
  menuOutline,
  alertCircleOutline,
  cameraOutline,
  cameraReverseOutline,
  imagesOutline,
  closeOutline,
  qrCodeOutline
} from 'ionicons/icons';

import {
  EstudianteService,
  Estudiante,
  SedeItem
} from '../../../services/estudiante.service';
import {
  SelectorUbicacionComponent,
  UbicacionSeleccionada
} from '../../../components/selector-ubicacion/selector-ubicacion.component';
import { extraerNumeracion } from '../../../utils/direccion.util';
import { aplicarEspejo, restriccionOtraCamara } from '../../../utils/camara.util';
import { REGION_METROPOLITANA } from '../../../utils/chile-territorio';

addIcons({
  menuOutline,
  alertCircleOutline,
  cameraOutline,
  cameraReverseOutline,
  imagesOutline,
  closeOutline
});

@Component({
  selector: 'app-agregar-hijo',
  templateUrl: './agregar-hijo.page.html',
  styleUrls: ['./agregar-hijo.page.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    IonContent,
    IonInput,
    IonItem,
    IonButton,
    IonSpinner,
    IonIcon,
    IonSelect,
    IonSelectOption,
    IonMenuToggle,
    IonToggle,
    ConsentimientoBiometricoComponent,
    SelectorUbicacionComponent
  ]
})
export class AgregarHijoPage {

  readonly cursosDisponibles = [
    'Prekínder', 'Kínder',
    '1° Básico', '2° Básico', '3° Básico', '4° Básico',
    '5° Básico', '6° Básico', '7° Básico', '8° Básico',
    '1° Medio', '2° Medio', '3° Medio', '4° Medio'
  ];

  nombre = '';
  apellido = '';
  rut = '';
  fechaNacimiento = '';
  colegioId?: number;
  sedeId?: number;
  curso = '';

  sedesList: SedeItem[] = [];

  /** Colegio que habilitó a este hijo (sale de su RUT; el apoderado no lo elige). */
  colegioNombre = '';
  verificandoRut = false;
  errorRut = '';
  private rutVerificado = '';

  direccionPrincipal = '';
  comunaPrincipal = '';
  regionPrincipal = REGION_METROPOLITANA;
  latitud?: number;
  longitud?: number;
  ubicacionConfirmada = false;

  personaAutorizada = '';
  apellidoPersonaAutorizada = '';
  rutPersonaAutorizada = '';

  cargando = false;
  cargandoSedes = false;
  errorMensaje = '';
  fotoSeleccionada?: File;
  vistaPreviaFoto = '';
  private capturaPendienteDeGuardar = false;
  camaraAbierta = false;
  camarasDisponibles: MediaDeviceInfo[] = [];
  camaraSeleccionada = '';
  private flujoCamara?: MediaStream;
  @ViewChild('cameraPreview') private cameraPreview?: ElementRef<HTMLVideoElement>;

  /**
   * Consentimiento biométrico de ESTE hijo (términos 1.2): parte apagado. Si el apoderado lo enciende
   * se pide la foto; si no, el hijo sube y baja con el QR del apoderado o con el inspector.
   */
  usaBiometria = false;

  constructor(
    private router: Router,
    private estudianteService: EstudianteService,
    private feedback: FeedbackService,
    private authService: AuthService
  ) {
    addIcons({ menuOutline, alertCircleOutline, cameraOutline, cameraReverseOutline, imagesOutline, closeOutline, qrCodeOutline });
  }

  /** Al apagar el interruptor se descarta la foto que se hubiera tomado. */
  cambiarUsoBiometria(activo: boolean): void {
    this.usaBiometria = activo;
    if (!activo) {
      this.cancelarCaptura();
      this.quitarFoto();
    }
  }

  /**
   * Con el RUT del hijo se sabe en qué colegio va: el que lo habilitó para esta cuenta. Así, un apoderado con
   * hijos en dos colegios no puede inscribir a uno en el equivocado.
   */
  verificarRut(): void {
    const rut = this.rut.trim();
    if (!rut || rut === this.rutVerificado) return;
    this.rutVerificado = rut;
    this.errorRut = '';
    this.colegioNombre = '';
    this.onColegioChange(new CustomEvent('ionChange', { detail: { value: null } }));
    this.verificandoRut = true;
    this.estudianteService.consultarHabilitacion(rut).subscribe({
      next: (habilitacion) => {
        if (this.rutVerificado !== rut) return;
        this.verificandoRut = false;
        this.colegioNombre = habilitacion.colegio_nombre;
        this.onColegioChange(new CustomEvent('ionChange', { detail: { value: habilitacion.colegio_id } }));
      },
      error: (err) => {
        if (this.rutVerificado !== rut) return;
        this.verificandoRut = false;
        this.errorRut = err?.error?.message
          || 'No fue posible verificar el RUT. Revisa tu conexión e inténtalo de nuevo.';
        // Permite volver a intentarlo con el mismo RUT.
        this.rutVerificado = '';
      }
    });
  }

  onColegioChange(event: CustomEvent<{ value: number | string | null | undefined }>): void {
    const valor = event.detail.value;
    const colegioId = valor === null || valor === undefined || valor === ''
      ? undefined
      : Number(valor);

    // Mantener el valor seleccionado con el mismo tipo numérico de las opciones.
    this.colegioId = colegioId !== undefined && Number.isInteger(colegioId) && colegioId > 0
      ? colegioId
      : undefined;

    // No conservar una sede del colegio anterior.
    this.sedeId = undefined;
    this.sedesList = [];
    this.cargandoSedes = false;

    if (this.colegioId === undefined) {
      return;
    }

    const colegioConsultado = this.colegioId;
    this.cargandoSedes = true;

    this.estudianteService.obtenerSedesActivas(colegioConsultado).subscribe({
      next: (data) => {
        // Ignorar respuestas antiguas si el usuario cambió de colegio.
        if (this.colegioId !== colegioConsultado) {
          return;
        }

        this.sedesList = (data || []).filter((sede) => sede.activa !== false);
        this.sedeId = this.sedesList.length === 1
          ? Number(this.sedesList[0].id)
          : undefined;
        this.cargandoSedes = false;
      },
      error: (err) => {
        if (this.colegioId !== colegioConsultado) {
          return;
        }

        console.error('Error al cargar sedes:', err);
        this.sedesList = [];
        this.sedeId = undefined;
        this.cargandoSedes = false;
        this.errorMensaje = 'No fue posible cargar las sedes del colegio seleccionado.';
      }
    });
  }

  async guardarEstudiante() {

    this.errorMensaje = '';

    // El colegio sale del RUT del hijo: sin un RUT habilitado no se puede continuar.
    if (this.rut.trim() && (this.rut.trim() !== this.rutVerificado || !this.colegioId)) {
      this.errorMensaje = this.errorRut || 'Primero verificamos el RUT de tu hijo para saber a qué colegio va.';
      await this.mostrarToast(this.errorMensaje, 'warning');
      this.verificarRut();
      return;
    }

    if (
      !this.nombre.trim() ||
      !this.apellido.trim() ||
      !this.rut.trim() ||
      !this.fechaNacimiento ||
      !this.colegioId ||
      !this.sedeId ||
      !this.curso.trim() ||
      !this.direccionPrincipal.trim() ||
      !this.comunaPrincipal.trim() ||
      !this.regionPrincipal ||
      !this.ubicacionConfirmada ||
      this.latitud === undefined ||
      this.longitud === undefined
    ) {

      this.errorMensaje =
        'Completa los campos obligatorios (incluidas la sede, la región y la comuna) y confirma la ubicación exacta de la dirección principal.';

      await this.mostrarToast(
        this.errorMensaje,
        'warning'
      );

      return;
    }

    if (!extraerNumeracion(this.direccionPrincipal)) {
      this.errorMensaje = 'Agrega la numeración de la dirección (y depto o casa si corresponde) para que el conductor sepa cuál es la casa.';
      await this.mostrarToast(this.errorMensaje, 'warning');
      return;
    }

    if (this.usaBiometria && !this.fotoSeleccionada) {
      this.capturaPendienteDeGuardar = true;
      this.errorMensaje = 'Toma o selecciona una foto frontal del rostro del estudiante para registrar su biometría.';
      await this.mostrarToast(this.errorMensaje, 'warning');
      await this.abrirCamara();
      return;
    }

    this.cargando = true;

    const estudianteData: Estudiante = {

      nombre: this.nombre.trim(),

      apellido: this.apellido.trim(),

      rut: this.rut.trim(),

      fecha_nacimiento: this.fechaNacimiento,

      colegio: this.colegioId,

      colegio_id: this.colegioId,

      sede: this.sedeId,

      sede_id: this.sedeId,

      curso: this.curso.trim(),

      direccion_principal:
        this.direccionPrincipal.trim(),
      comuna: this.comunaPrincipal.trim(),
      region: this.regionPrincipal,

      latitud: Number(this.latitud.toFixed(6)),
      longitud: Number(this.longitud.toFixed(6)),
      ubicacion_confirmada: this.ubicacionConfirmada,


      // El servidor guarda el nombre completo en un solo campo.
      persona_autorizada:
        [this.personaAutorizada.trim(), this.apellidoPersonaAutorizada.trim()].filter(Boolean).join(' ') || undefined,

      rut_persona_autorizada:
        this.rutPersonaAutorizada.trim() || undefined,

      // Consentimiento biométrico de este hijo (el servidor deja la constancia).
      autoriza_biometria: this.usaBiometria
    };

    this.estudianteService
      .crearEstudiante(estudianteData, this.usaBiometria ? this.fotoSeleccionada : undefined)
      .subscribe({

        next: async (res) => {

          this.cargando = false;

          await this.mostrarToast(
            res.message || (this.usaBiometria
              ? 'Estudiante registrado con foto y biometría.'
              : 'Estudiante registrado. Subirá y bajará con código QR o con el inspector.'),
            'success'
          );

          this.router.navigate([
            '/apoderado/mis-hijos'
          ]);

        },

        error: async (err) => {

          this.cargando = false;

          let mensaje =
            'Error al registrar el estudiante.';

          console.error('Error registrando estudiante:', err);

          if (err.status === 0) {

            mensaje =
              'No se pudo conectar con el servidor. Verifica que Django esté iniciado.';

          } else if (err.status === 401) {

            mensaje =
              'Tu sesión expiró. Inicia sesión nuevamente.';

          } else if (err.status === 403) {

            mensaje =
              'No tienes permisos para registrar estudiantes.';

          } else if (err.status >= 500) {

            mensaje =
              'El servidor no pudo procesar la solicitud. Revisa la terminal de Django.';

          } else if (err.error) {

            if (err.error.message) {

              mensaje = err.error.message;

            }

            if (err.error.errors) {

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
          }

          this.errorMensaje = mensaje;

          await this.mostrarToast(
            mensaje,
            'danger'
          );
        }

      });
  }

  // Centra el mapa manual en la sede elegida, si tiene coordenadas.
  get sedeSeleccionada(): SedeItem | undefined {
    if (this.sedeId === undefined) return undefined;
    return this.sedesList.find((sede) => Number(sede.id) === Number(this.sedeId));
  }

  ubicacionCambio(ubicacion: UbicacionSeleccionada): void {
    this.direccionPrincipal = ubicacion.direccion;
    this.comunaPrincipal = ubicacion.comuna;
    this.regionPrincipal = ubicacion.region;
    this.latitud = ubicacion.latitud;
    this.longitud = ubicacion.longitud;
    this.ubicacionConfirmada = ubicacion.latitud !== undefined && ubicacion.longitud !== undefined;
  }

  ionViewDidLeave(): void {
    this.cerrarCamara();
  }

  async abrirCamara(deviceId?: string, restriccion?: MediaTrackConstraints): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia) {
      await this.mostrarToast('El navegador no permite acceder a la cámara. Abre la app desde localhost o una conexión segura.', 'danger');
      this.capturaPendienteDeGuardar = false;
      return;
    }

    try {
      // Android no abre una cámara mientras otra sigue activa.
      this.flujoCamara?.getTracks().forEach((track) => track.stop());
      const nuevoFlujo = await navigator.mediaDevices.getUserMedia({
        video: restriccion ?? (deviceId ? { deviceId: { exact: deviceId } } : { facingMode: 'user' }),
        audio: false
      });
      this.flujoCamara = nuevoFlujo;
      this.camaraAbierta = true;
      this.camarasDisponibles = (await navigator.mediaDevices.enumerateDevices())
        .filter((device) => device.kind === 'videoinput');
      this.camaraSeleccionada = nuevoFlujo.getVideoTracks()[0]?.getSettings().deviceId || deviceId || '';
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
      const video = this.cameraPreview?.nativeElement;
      if (video) {
        video.srcObject = nuevoFlujo;
        aplicarEspejo(video, nuevoFlujo);
        await video.play();
      }
      this.errorMensaje = '';
    } catch (error) {
      console.error('No se pudo iniciar la cámara:', error);
      this.capturaPendienteDeGuardar = false;
      this.cerrarCamara();
      await this.mostrarToast('No se pudo abrir la cámara. Revisa el permiso del navegador y que iVCam esté activo.', 'danger');
    }
  }

  async alternarCamara(): Promise<void> {
    const restriccion = await restriccionOtraCamara(this.flujoCamara?.getVideoTracks()[0]);
    if (!restriccion) {
      await this.mostrarToast('Este dispositivo tiene una sola cámara.', 'warning');
      return;
    }
    await this.abrirCamara(undefined, restriccion);
  }

  cambiarCamara(event: Event): void {
    const deviceId = (event.target as HTMLSelectElement).value;
    if (deviceId) void this.abrirCamara(deviceId);
  }

  async capturarFoto(): Promise<void> {
    const video = this.cameraPreview?.nativeElement;
    if (!video?.videoWidth || !video.videoHeight) {
      await this.mostrarToast('Espera a que la cámara muestre la imagen antes de capturar.', 'warning');
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height);
    const foto = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9));
    if (!foto || foto.size > 5 * 1024 * 1024) {
      await this.mostrarToast('La foto supera el máximo de 5 MB. Acércate un poco y vuelve a intentarlo.', 'warning');
      return;
    }

    this.limpiarVistaPrevia();
    this.fotoSeleccionada = new File([foto], 'rostro-estudiante.jpg', { type: 'image/jpeg' });
    this.vistaPreviaFoto = URL.createObjectURL(this.fotoSeleccionada);
    this.cerrarCamara();
    if (this.capturaPendienteDeGuardar) {
      this.capturaPendienteDeGuardar = false;
      void this.guardarEstudiante();
    }
  }

  async seleccionarFoto(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const archivo = input.files?.[0];
    input.value = '';
    if (!archivo) return;

    const formatosPermitidos = ['image/jpeg', 'image/png', 'image/webp'];
    if (!formatosPermitidos.includes(archivo.type.toLowerCase())) {
      await this.mostrarToast('Formato no admitido. Selecciona una imagen JPG, PNG o WebP.', 'warning');
      return;
    }
    if (archivo.size > 5 * 1024 * 1024) {
      await this.mostrarToast('La foto supera el máximo permitido de 5 MB.', 'warning');
      return;
    }

    this.cerrarCamara();
    this.limpiarVistaPrevia();
    this.fotoSeleccionada = archivo;
    this.vistaPreviaFoto = URL.createObjectURL(archivo);
    this.errorMensaje = '';
    this.capturaPendienteDeGuardar = false;
  }

  cancelarCaptura(): void {
    this.capturaPendienteDeGuardar = false;
    this.cerrarCamara();
  }

  quitarFoto(): void {
    this.limpiarVistaPrevia();
    this.fotoSeleccionada = undefined;
  }

  private cerrarCamara(): void {
    this.flujoCamara?.getTracks().forEach((track) => track.stop());
    this.flujoCamara = undefined;
    this.camaraAbierta = false;
    this.camarasDisponibles = [];
    this.camaraSeleccionada = '';
  }

  private limpiarVistaPrevia() {
    if (this.vistaPreviaFoto) {
      URL.revokeObjectURL(this.vistaPreviaFoto);
      this.vistaPreviaFoto = '';
    }
  }

  private async mostrarToast(
    mensaje: string,
    color: 'success' | 'danger' | 'warning'
  ) {

    await this.feedback.show(mensaje, color as FeedbackType);
  }

}
