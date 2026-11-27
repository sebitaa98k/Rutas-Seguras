import { Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';

import {
  IonContent,
  IonIcon,
  IonSpinner,
  IonMenuToggle,
  IonToggle,
  AlertController,
  IonButton, IonInput } from '@ionic/angular/standalone';
import { ConsentimientoBiometricoComponent } from '../../../components/consentimiento-biometrico/consentimiento-biometrico.component';

import { addIcons } from 'ionicons';
import { FeedbackService, FeedbackType } from '../../../services/feedback.service';

import {
  schoolOutline,
  calendarOutline,
  cardOutline,
  locationOutline,
  homeOutline,
  personOutline,
  shieldCheckmarkOutline,
  busOutline,
  menuOutline,
  lockClosedOutline,
  createOutline,
  bookOutline,
  cameraOutline,
  cameraReverseOutline,
  closeOutline,
  addOutline,
  trashOutline
} from 'ionicons/icons';

import {
  EstudianteService,
  Estudiante,
  PersonaAutorizada
} from '../../../services/estudiante.service';
import { AsistenciaHijoComponent } from '../../../components/asistencia-hijo/asistencia-hijo.component';
import {
  SelectorUbicacionComponent,
  UbicacionSeleccionada
} from '../../../components/selector-ubicacion/selector-ubicacion.component';
import { extraerNumeracion } from '../../../utils/direccion.util';
import { aplicarEspejo, restriccionOtraCamara } from '../../../utils/camara.util';

addIcons({
  schoolOutline,
  calendarOutline,
  cardOutline,
  locationOutline,
  homeOutline,
  personOutline,
  shieldCheckmarkOutline,
  busOutline,
  menuOutline,
  lockClosedOutline,
  createOutline,
  bookOutline,
  cameraOutline,
  cameraReverseOutline,
  closeOutline,
  addOutline,
  trashOutline
});

@Component({
  selector: 'app-detalle-hijo',
  templateUrl: './detalle-hijo.page.html',
  styleUrls: ['./detalle-hijo.page.scss'],

  standalone: true,

  imports: [IonButton, IonInput, IonToggle, ConsentimientoBiometricoComponent,
    CommonModule,
    FormsModule,
    IonContent,
    IonIcon,
    IonSpinner,
    IonMenuToggle,
    SelectorUbicacionComponent,
    AsistenciaHijoComponent
  ]
})
export class DetalleHijoPage implements OnInit {

  estudiante?: Estudiante;

  cargando = true;

  errorMensaje = '';
  modoEdicion = false;
  guardando = false;
  datosEdicion?: Estudiante;
  personasAutorizadas: PersonaAutorizada[] = [];
  nuevoAutorizado = { nombre: '', apellido: '', rut: '' };
  guardandoAutorizado = false;
  fotoBiometrica?: File;
  vistaPreviaBiometrica = '';
  camaraAbierta = false;
  camarasDisponibles: MediaDeviceInfo[] = [];
  camaraSeleccionada = '';
  private flujoCamara?: MediaStream;
  @ViewChild('cameraPreview') private cameraPreview?: ElementRef<HTMLVideoElement>;


  constructor(
    private route: ActivatedRoute,
    private estudianteService: EstudianteService,
    private feedback: FeedbackService,
    private alertController: AlertController
  ) {
      addIcons({shieldCheckmarkOutline,menuOutline,personOutline,schoolOutline,cardOutline,lockClosedOutline,calendarOutline,bookOutline,busOutline,locationOutline,homeOutline,createOutline,closeOutline,cameraOutline, cameraReverseOutline});}


  ngOnInit() {

    this.route.queryParams.subscribe(params => {

      const id = Number(params['id']);

      if (!id) {

        this.errorMensaje =
          'No se encontró el estudiante seleccionado.';

        this.cargando = false;

        return;
      }

      this.cargarEstudiante(id);

    });

  }


  cargarEstudiante(id: number) {

    this.cargando = true;

    this.errorMensaje = '';

    this.estudianteService
      .obtenerEstudiante(id)
      .subscribe({

        next: (data) => {

          this.estudiante = data;
          this.datosEdicion = { ...data };
          this.cargarPersonasAutorizadas(data.id!);

          this.cargando = false;

        },

        error: async (err) => {

          console.error(
            'Error cargando estudiante:',
            err
          );

          this.cargando = false;

          this.errorMensaje =
            'No se pudo cargar la información del estudiante.';

          await this.mostrarToast(
            this.errorMensaje,
            'danger'
          );

        }

      });

  }

  cargarPersonasAutorizadas(estudianteId: number): void {
    this.estudianteService.obtenerPersonasAutorizadas(estudianteId).subscribe({
      next: personas => this.personasAutorizadas = personas,
      error: err => console.error('Error cargando personas autorizadas:', err)
    });
  }

  async agregarAutorizado(): Promise<void> {
    const { nombre, apellido, rut } = this.nuevoAutorizado;
    if (!this.estudiante?.id || !nombre.trim() || !apellido.trim() || !rut.trim()) {
      await this.mostrarToast('Ingresa nombre, apellido y RUT de la persona autorizada.', 'warning');
      return;
    }
    this.guardandoAutorizado = true;
    // El servidor guarda el nombre completo de la persona autorizada en un solo campo.
    const datos = { nombre: `${nombre.trim()} ${apellido.trim()}`, rut };
    this.estudianteService.agregarPersonaAutorizada(this.estudiante.id, datos).subscribe({
      next: async persona => {
        this.personasAutorizadas.push(persona);
        this.nuevoAutorizado = { nombre: '', apellido: '', rut: '' };
        this.guardandoAutorizado = false;
        await this.mostrarToast('Persona autorizada agregada.', 'success');
      },
      error: async err => {
        this.guardandoAutorizado = false;
        await this.mostrarToast(err?.error?.message || 'No se pudo agregar la autorización.', 'danger');
      }
    });
  }

  async eliminarAutorizado(persona: PersonaAutorizada): Promise<void> {
    if (!this.estudiante?.id || !window.confirm(`¿Eliminar la autorización de ${persona.nombre}?`)) return;
    this.estudianteService.eliminarPersonaAutorizada(this.estudiante.id, persona.id).subscribe({
      next: async () => {
        this.personasAutorizadas = this.personasAutorizadas.filter(item => item.id !== persona.id);
        await this.mostrarToast('Autorización eliminada.', 'success');
      },
      error: async err => {
        await this.mostrarToast(err?.error?.message || 'No se pudo eliminar la autorización.', 'danger');
      }
    });
  }

  iniciarEdicion() {
    if (!this.estudiante) {
      return;
    }
    this.datosEdicion = { ...this.estudiante };
    this.limpiarVistaPreviaBiometrica();
    this.fotoBiometrica = undefined;
    this.modoEdicion = true;
  }

  cancelarEdicion() {
    this.datosEdicion = this.estudiante ? { ...this.estudiante } : undefined;
    this.fotoBiometrica = undefined;
    this.limpiarVistaPreviaBiometrica();
    this.modoEdicion = false;
  }

  ubicacionCambio(ubicacion: UbicacionSeleccionada): void {
    if (!this.datosEdicion) {
      return;
    }
    const tienePunto = ubicacion.latitud !== undefined && ubicacion.longitud !== undefined;
    this.datosEdicion.direccion_principal = ubicacion.direccion;
    this.datosEdicion.comuna = ubicacion.comuna;
    this.datosEdicion.region = ubicacion.region;
    this.datosEdicion.latitud = tienePunto ? ubicacion.latitud : null;
    this.datosEdicion.longitud = tienePunto ? ubicacion.longitud : null;
    this.datosEdicion.ubicacion_confirmada = tienePunto;
  }

  async guardarCambios() {
    if (!this.estudiante?.id || !this.datosEdicion) {
      return;
    }

    if (!this.datosEdicion.region || !(this.datosEdicion.comuna || '').trim()) {
      await this.mostrarToast('Selecciona la región y la comuna de la dirección.', 'warning');
      return;
    }

    if (!extraerNumeracion(this.datosEdicion.direccion_principal || '')) {
      await this.mostrarToast(
        'Agrega la numeración de la dirección (y depto o casa si corresponde) para que el conductor sepa cuál es la casa.',
        'warning'
      );
      return;
    }

    this.guardando = true;
    const { id, rut, tiene_foto, created_at, updated_at, colegio_nombre, sede_nombre, direccion_completa, ...datos } = this.datosEdicion;

    this.estudianteService.actualizarEstudiante(this.estudiante.id, datos).subscribe({
      next: async (respuesta) => {
        this.estudiante = respuesta.estudiante;
        this.datosEdicion = { ...respuesta.estudiante };
        if (this.fotoBiometrica && this.estudiante.id) {
          this.estudianteService.registrarBiometriaEstudiante(
            this.estudiante.id,
            this.fotoBiometrica
          ).subscribe({
            next: async () => {
              this.estudiante!.tiene_foto = true;
              this.estudiante!.tiene_biometria = true;
              this.datosEdicion = { ...this.estudiante! };
              this.fotoBiometrica = undefined;
              this.limpiarVistaPreviaBiometrica();
              this.modoEdicion = false;
              this.guardando = false;
              await this.mostrarToast('Datos y foto biométrica actualizados.', 'success');
            },
            error: async (err) => {
              this.guardando = false;
              const mensaje = err.error?.message || 'Los datos se guardaron, pero no se pudo actualizar la foto biométrica.';
              await this.mostrarToast(mensaje, 'danger');
            }
          });
          return;
        }
        this.modoEdicion = false;
        this.guardando = false;
        await this.mostrarToast(respuesta.message, 'success');
      },
      error: async (err) => {
        this.guardando = false;
        console.error('Error actualizando estudiante:', err);
        let mensaje = 'No se pudo actualizar la información del estudiante.';
        const errores = err.error?.errors;
        if (errores) {
          const primerCampo = Object.keys(errores)[0];
          const primerError = errores[primerCampo];
          mensaje = Array.isArray(primerError) ? primerError[0] : primerError;
        }
        await this.mostrarToast(mensaje, 'danger');
      }
    });
  }

  async abrirCamara(deviceId?: string, restriccion?: MediaTrackConstraints): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia) {
      await this.mostrarToast('El navegador no permite acceder a la cámara. Abre la app desde localhost o una conexión segura.', 'danger');
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
    } catch (error) {
      console.error('No se pudo iniciar la cámara:', error);
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

  async capturarFotoBiometrica(): Promise<void> {
    const video = this.cameraPreview?.nativeElement;
    if (!video?.videoWidth || !video.videoHeight) {
      await this.mostrarToast('Espera a que la cámara muestre la imagen antes de capturar.', 'warning');
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imagen = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9));
    if (!imagen || imagen.size > 5 * 1024 * 1024) {
      await this.mostrarToast('La foto supera el máximo de 5 MB. Vuelve a intentarlo.', 'warning');
      return;
    }

    this.limpiarVistaPreviaBiometrica();
    this.fotoBiometrica = new File([imagen], 'rostro-estudiante.jpg', { type: 'image/jpeg' });
    this.vistaPreviaBiometrica = URL.createObjectURL(this.fotoBiometrica);
    this.cerrarCamara();
  }

  async seleccionarFotoBiometrica(event: Event): Promise<void> {
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
    this.limpiarVistaPreviaBiometrica();
    this.fotoBiometrica = archivo;
    this.vistaPreviaBiometrica = URL.createObjectURL(archivo);
  }

  cancelarCaptura(): void {
    this.cerrarCamara();
  }

  quitarFotoBiometrica(): void {
    this.fotoBiometrica = undefined;
    this.limpiarVistaPreviaBiometrica();
  }

  ionViewDidLeave(): void {
    this.cerrarCamara();
  }

  private cerrarCamara(): void {
    this.flujoCamara?.getTracks().forEach((track) => track.stop());
    this.flujoCamara = undefined;
    this.camaraAbierta = false;
    this.camarasDisponibles = [];
    this.camaraSeleccionada = '';
  }

  private limpiarVistaPreviaBiometrica(): void {
    if (this.vistaPreviaBiometrica) {
      URL.revokeObjectURL(this.vistaPreviaBiometrica);
      this.vistaPreviaBiometrica = '';
    }
  }


  formatearFecha(fecha: string): string {

    if (!fecha) {
      return 'No registrada';
    }

    const [anio, mes, dia] =
      fecha.split('-');

    return `${dia}/${mes}/${anio}`;

  }


  // ------------------------------------------------ consentimiento biométrico de este hijo

  cambiandoBiometria = false;

  /**
   * Autoriza o revoca el reconocimiento facial de este hijo (Ley 21.719). Se pide confirmar: al
   * revocar se borran al tiro su foto y sus datos faciales.
   */
  async cambiarBiometria(evento: CustomEvent, autoriza: boolean): Promise<void> {
    const toggle = evento.target as HTMLIonToggleElement;
    const estudiante = this.estudiante;
    if (!estudiante?.id || this.cambiandoBiometria) return;
    const nombre = estudiante.nombre;
    const alerta = await this.alertController.create({
      header: autoriza ? 'Autorizar reconocimiento facial' : 'Desactivar reconocimiento facial',
      message: autoriza
        ? `Autorizas usar el rostro de ${nombre} solo para identificarlo al subir y bajar del furgón. ` +
          'Después debes registrar su foto. Puedes retirarlo cuando quieras.'
        : `Se borrarán de inmediato y para siempre la foto y los datos faciales de ${nombre}. ` +
          'Desde ahora subirá y bajará con tu código QR o con el inspector.',
      cssClass: 'rs-alert',
      buttons: [
        { text: 'Cancelar', role: 'cancel' },
        { text: autoriza ? 'Autorizar' : 'Desactivar y borrar', role: 'confirm', cssClass: autoriza ? '' : 'rs-alert__danger' },
      ],
    });
    await alerta.present();
    const { role } = await alerta.onDidDismiss();
    if (role !== 'confirm') {
      // Vuelve el interruptor a como estaba.
      toggle.checked = !autoriza;
      return;
    }
    this.cambiandoBiometria = true;
    this.estudianteService.cambiarBiometria(estudiante.id, autoriza).subscribe({
      next: async respuesta => {
        this.cambiandoBiometria = false;
        this.estudiante = { ...estudiante, ...respuesta.estudiante };
        await this.mostrarToast(respuesta.message, 'success');
      },
      error: async err => {
        this.cambiandoBiometria = false;
        toggle.checked = !autoriza;
        await this.mostrarToast(err?.error?.message || 'No se pudo cambiar el reconocimiento facial.', 'danger');
      },
    });
  }

  private async mostrarToast(
    mensaje: string,
    color: 'success' | 'danger' | 'warning'
  ) {

    await this.feedback.show(mensaje, color as FeedbackType);

  }

}
