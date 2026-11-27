import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AlertController, IonIcon, IonSpinner } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import {
  alertCircleOutline,
  busOutline,
  calendarOutline,
  checkmarkCircleOutline,
  closeCircleOutline,
  homeOutline,
  schoolOutline
} from 'ionicons/icons';

import {
  DiaAsistencia,
  EstadoAsistencia,
  EstadoTramoAsistencia,
  EstudianteService,
  TramoAsistencia
} from '../../services/estudiante.service';
import { FeedbackService, FeedbackType } from '../../services/feedback.service';

interface TramoVista {
  clave: TramoAsistencia;
  titulo: string;
  detalle: string;
  icono: string;
  estado: EstadoTramoAsistencia;
}

/**
 * El apoderado avisa que hoy o mañana no enviará a su hijo en el furgón (ida, vuelta o ambos),
 * o lo revierte. El conductor lo ve en su ruta de inmediato.
 */
@Component({
  selector: 'app-asistencia-hijo',
  templateUrl: './asistencia-hijo.component.html',
  styleUrls: ['./asistencia-hijo.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule, IonIcon, IonSpinner]
})
export class AsistenciaHijoComponent implements OnChanges {
  @Input({ required: true }) estudianteId!: number;
  @Input() nombre = '';
  @Output() asistenciaCambio = new EventEmitter<EstadoAsistencia>();

  estado?: EstadoAsistencia;
  cargando = false;
  guardando = false;
  error = '';
  diaIndex = 0;
  motivo = '';

  constructor(
    private estudianteService: EstudianteService,
    private alertController: AlertController,
    private feedback: FeedbackService
  ) {
    addIcons({
      alertCircleOutline,
      busOutline,
      calendarOutline,
      checkmarkCircleOutline,
      closeCircleOutline,
      homeOutline,
      schoolOutline
    });
  }

  ngOnChanges(cambios: SimpleChanges): void {
    if (cambios['estudianteId'] && this.estudianteId) {
      this.cargar();
    }
  }

  get dia(): DiaAsistencia | undefined {
    return this.estado?.dias[this.diaIndex];
  }

  get diaTexto(): string {
    return (this.dia?.etiqueta || 'hoy').toLowerCase();
  }

  get tramos(): TramoVista[] {
    const dia = this.dia;
    if (!dia) return [];
    return [
      { clave: 'ida', titulo: 'Ida', detalle: 'Casa → colegio', icono: 'school-outline', estado: dia.ida },
      { clave: 'vuelta', titulo: 'Vuelta', detalle: 'Colegio → casa', icono: 'home-outline', estado: dia.vuelta }
    ];
  }

  /** Atajo "No irá a clases": ambos tramos disponibles y ninguno avisado aún. */
  get puedeAvisarDiaCompleto(): boolean {
    return this.tramos.length === 2
      && this.tramos.every(tramo => !tramo.estado.no_asiste && !tramo.estado.bloqueo);
  }

  get diaCompletoAvisado(): boolean {
    return this.tramos.length === 2 && this.tramos.every(tramo => tramo.estado.no_asiste);
  }

  seleccionarDia(indice: number): void {
    this.diaIndex = indice;
    this.motivo = '';
  }

  cargar(): void {
    this.cargando = true;
    this.error = '';
    this.estudianteService.obtenerAsistencia(this.estudianteId).subscribe({
      next: estado => {
        this.estado = estado;
        this.cargando = false;
      },
      error: err => {
        this.cargando = false;
        this.error = err?.error?.message || 'No se pudo cargar la asistencia.';
      }
    });
  }

  async avisar(tramo: TramoAsistencia | 'ambos'): Promise<void> {
    const dia = this.dia;
    if (!dia || this.guardando) return;
    const nombre = this.nombre || this.estado?.estudiante_nombre || 'tu hijo/a';
    const queTramo = tramo === 'ambos' ? 'ni de ida ni de vuelta' : (tramo === 'ida' ? 'de ida' : 'de vuelta');

    const confirmado = await this.confirmar(
      '¿No usará el furgón?',
      `${nombre} no usará el furgón ${this.diaTexto} ${queTramo}. El conductor no pasará por él y lo verá en su ruta.`,
      'Sí, avisar'
    );
    if (!confirmado) return;

    this.guardando = true;
    this.estudianteService.avisarInasistencia(this.estudianteId, dia.fecha, tramo, this.motivo.trim()).subscribe({
      next: respuesta => this.aplicarRespuesta(respuesta, 'success'),
      error: err => this.aplicarError(err)
    });
  }

  async cancelar(tramo: TramoAsistencia | 'ambos'): Promise<void> {
    const dia = this.dia;
    if (!dia || this.guardando) return;
    const nombre = this.nombre || this.estado?.estudiante_nombre || 'tu hijo/a';
    const queTramo = tramo === 'ambos' ? '' : (tramo === 'ida' ? ' de ida' : ' de vuelta');

    const confirmado = await this.confirmar(
      '¿Sí usará el furgón?',
      `${nombre} sí usará el furgón ${this.diaTexto}${queTramo}. Volverá a quedar en la ruta del conductor.`,
      'Sí, usará el furgón'
    );
    if (!confirmado) return;

    this.guardando = true;
    this.estudianteService.cancelarInasistencia(this.estudianteId, dia.fecha, tramo).subscribe({
      next: respuesta => this.aplicarRespuesta(respuesta, 'success'),
      error: err => this.aplicarError(err)
    });
  }

  private aplicarRespuesta(respuesta: EstadoAsistencia, color: 'success' | 'warning'): void {
    this.guardando = false;
    this.estado = respuesta;
    this.motivo = '';
    this.asistenciaCambio.emit(respuesta);
    this.mostrarToast(respuesta.message || 'Asistencia actualizada.', color);
  }

  private aplicarError(err: any): void {
    this.guardando = false;
    // El backend devuelve el estado actualizado junto al motivo (ej: "ya está en el furgón").
    if (err?.error?.dias) {
      this.estado = err.error as EstadoAsistencia;
    }
    this.mostrarToast(err?.error?.message || 'No se pudo actualizar la asistencia.', 'danger');
  }

  private async confirmar(header: string, message: string, textoAceptar: string): Promise<boolean> {
    const alerta = await this.alertController.create({
      header,
      message,
      cssClass: 'rs-alert',
      buttons: [
        { text: 'Cancelar', role: 'cancel' },
        { text: textoAceptar, role: 'confirm' }
      ]
    });
    await alerta.present();
    const { role } = await alerta.onDidDismiss();
    return role === 'confirm';
  }

  private async mostrarToast(mensaje: string, color: 'success' | 'warning' | 'danger'): Promise<void> {
    await this.feedback.show(mensaje, color as FeedbackType, 3000);
  }
}
