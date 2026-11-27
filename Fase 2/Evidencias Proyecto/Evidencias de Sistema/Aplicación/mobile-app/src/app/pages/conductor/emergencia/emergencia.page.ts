import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  IonContent,
  IonIcon,
  IonMenuToggle,
  IonSpinner,
  AlertController
} from '@ionic/angular/standalone';

import { addIcons } from 'ionicons';
import {
  menuOutline,
  warningOutline,
  sendOutline,
  personOutline,
  checkmarkCircleOutline,
  radioButtonOnOutline,
  radioButtonOffOutline,
  alertCircleOutline
} from 'ionicons/icons';

import { NotificationService } from '../../../services/notification.service';
import { Estudiante } from '../../../services/estudiante.service';
import { AuthService } from '../../../services/auth.service';
import { FeedbackService, FeedbackType } from '../../../services/feedback.service';

addIcons({
  menuOutline,
  warningOutline,
  sendOutline,
  personOutline,
  checkmarkCircleOutline,
  radioButtonOnOutline,
  radioButtonOffOutline,
  alertCircleOutline
});

// Deben coincidir con TIPOS_EMERGENCIA_RUTA / TIPOS_EMERGENCIA_ESTUDIANTE del backend.
export const TIPOS_EMERGENCIA_RUTA = [
  'Avería mecánica',
  'Tráfico grave / Retraso',
  'Accidente en ruta',
  'Clima / Cierre de vía',
  'Otro',
] as const;

export const TIPOS_EMERGENCIA_ESTUDIANTE = [
  'Emergencia médica / Salud',
  'Malestar o mareo',
  'Lesión o golpe a bordo',
  'Conducta o pelea a bordo',
  'Otro',
] as const;

export interface EstadoEnRuta {
  texto: string;
  abordo: boolean;
}

/** Texto corto del estado del niño en la ruta para la lista de emergencias. */
export function estadoEnRuta(parada: any, esIda: boolean): EstadoEnRuta {
  if (parada?.entregado) return { texto: 'Entregado', abordo: false };
  if (parada?.abordo) return { texto: 'A bordo', abordo: true };
  if (parada?.estado === 'ausente') return { texto: esIda ? 'No se presentó' : 'No subió', abordo: false };
  if (parada?.no_asiste) return { texto: 'No asiste hoy', abordo: false };
  return { texto: esIda ? 'Por recoger' : 'Por subir', abordo: false };
}

@Component({
  selector: 'app-emergencia',
  templateUrl: './emergencia.page.html',
  styleUrls: ['./emergencia.page.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    IonContent,
    IonIcon,
    IonMenuToggle,
    IonSpinner
  ]
})
export class EmergenciaPage implements OnInit {

  tipo: 'ruta' | 'estudiante' = 'ruta';
  categoria: string = '';
  descripcion: string = '';

  estudiantesLista: Estudiante[] = [];
  estadoPorEstudiante = new Map<number, EstadoEnRuta>();
  estudianteSeleccionadoId: number | null = null;
  cargandoEstudiantes: boolean = false;
  enviando: boolean = false;

  constructor(
    private notificationService: NotificationService,
    private authService: AuthService,
    private feedback: FeedbackService,
    private alertController: AlertController
  ) {}

  ngOnInit() {
    this.cargarEstudiantesConductor();
  }

  ionViewWillEnter() {
    this.cargarEstudiantesConductor();
  }

  cargarEstudiantesConductor() {
    if (!this.authService.getUsuario()) return;

    this.cargandoEstudiantes = true;
    this.notificationService.obtenerMiRuta().subscribe({
      next: (ruta: any) => {
        this.cargandoEstudiantes = false;
        if (ruta?.estado !== 'en_ruta') {
          this.estudiantesLista = [];
          this.estudianteSeleccionadoId = null;
          return;
        }
        const esIda = ruta.sentido !== 'desde_colegio';
        this.estudiantesLista = (ruta.paradas || []).map((parada: any) => ({
          id: parada.estudiante_id,
          nombre: parada.estudiante_nombre,
          apellido: '',
        })) as Estudiante[];
        // Se permite reportar por cualquier niño de la ruta (p. ej. se accidentó al salir de casa),
        // pero el conductor ve si va a bordo o no.
        this.estadoPorEstudiante = new Map(
          (ruta.paradas || []).map((parada: any) => [parada.estudiante_id, estadoEnRuta(parada, esIda)])
        );
        if (this.estudiantesLista.length > 0 && !this.estudianteSeleccionadoId) {
          this.estudianteSeleccionadoId = this.estudiantesLista[0].id || null;
        }
      },
      error: (err) => {
        this.cargandoEstudiantes = false;
        this.estudiantesLista = [];
        this.estudianteSeleccionadoId = null;
        console.error('No fue posible cargar la ruta en curso:', err);
      }
    });
  }

  /** Cada tipo tiene sus propias opciones: una falla mecánica no es una emergencia de un estudiante. */
  get tiposDisponibles(): readonly string[] {
    return this.tipo === 'ruta' ? TIPOS_EMERGENCIA_RUTA : TIPOS_EMERGENCIA_ESTUDIANTE;
  }

  cambiarTipo(tipo: 'ruta' | 'estudiante') {
    if (this.tipo === tipo) return;
    this.tipo = tipo;
    this.categoria = '';
  }

  seleccionarEstudiante(estId?: number) {
    if (estId !== undefined) {
      this.estudianteSeleccionadoId = estId;
    }
  }

  async confirmarYEnviar() {
    if (!this.categoria) {
      await this.mostrarToast('Por favor selecciona un tipo de emergencia.', 'warning');
      return;
    }

    if (!this.descripcion.trim()) {
      await this.mostrarToast('Por favor describe brevemente la situación.', 'warning');
      return;
    }

    if (this.tipo === 'estudiante' && !this.estudianteSeleccionadoId) {
      await this.mostrarToast('Debes seleccionar un estudiante de la lista.', 'warning');
      return;
    }

    const alert = await this.alertController.create({
      header: 'Confirmar envío',
      message: '¿Confirmar envío de esta emergencia?',
      cssClass: 'rs-alert',
      buttons: [
        {
          text: 'Cancelar',
          role: 'cancel',
          cssClass: 'alert-button-cancel'
        },
        {
          text: 'Enviar emergencia',
          role: 'confirm',
          cssClass: 'rs-alert__danger',
          handler: () => {
            this.procesarEnvio();
          }
        }
      ]
    });

    await alert.present();
  }

  private procesarEnvio() {
    this.enviando = true;

    const payload = {
      categoria: this.tipo === 'ruta' ? 'emergencia_ruta' : 'emergencia_estudiante',
      tipo_emergencia: this.categoria,
      descripcion: this.descripcion.trim(),
      estudiante_id: this.tipo === 'estudiante' ? this.estudianteSeleccionadoId : null
    };

    this.notificationService.enviarEmergencia(payload).subscribe({
      next: async (res: any) => {
        this.enviando = false;
        const msg = res.message || '🚨 Alerta de emergencia emitida y notificada exitosamente.';
        await this.mostrarToast(msg, 'danger');

        // Reset form
        this.categoria = '';
        this.descripcion = '';
      },
      error: async (err: any) => {
        this.enviando = false;
        console.error('Error enviando emergencia:', err);
        const errDetail = err.error?.message || 'No se pudo emitir la emergencia.';
        await this.mostrarToast(errDetail, 'danger');
      }
    });
  }

  private async mostrarToast(mensaje: string, color: 'success' | 'danger' | 'warning' = 'danger') {
    await this.feedback.show(mensaje, color as FeedbackType, 3500);
  }

}
