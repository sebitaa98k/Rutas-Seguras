import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import {
  IonContent,
  IonButton,
  IonSpinner,
  IonIcon,
  IonMenuToggle
} from '@ionic/angular/standalone';

import { addIcons } from 'ionicons';
import {
  shieldCheckmarkOutline,
  qrCodeOutline,
  navigateOutline,
  callOutline,
  personOutline,
  busOutline,
  schoolOutline,
  homeOutline,
  menuOutline,
  searchOutline,
  peopleOutline,
  optionsOutline
} from 'ionicons/icons';

import { AuthService, Usuario } from '../../../services/auth.service';
import { FeedbackService, FeedbackType } from '../../../services/feedback.service';

addIcons({
  shieldCheckmarkOutline,
  qrCodeOutline,
  navigateOutline,
  callOutline,
  personOutline,
  busOutline,
  schoolOutline,
  homeOutline,
  menuOutline,
  searchOutline,
  peopleOutline,
  optionsOutline
});

export interface EstudianteDelegado {
  id: number;
  rut: string;
  nombre: string;
  apellido: string;
  nombre_completo: string;
  colegio: number;
  colegio_nombre?: string;
  sede_nombre?: string;
  curso: string;
  direccion_principal: string;
  apoderado_nombre: string;
  apoderado_telefono: string;
  conductor_nombre: string;
  conductor_telefono: string;
}

@Component({
  selector: 'app-inicio-delegado',
  templateUrl: './inicio.page.html',
  styleUrls: ['./inicio.page.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    IonContent,
    IonButton,
    IonSpinner,
    IonIcon,
    IonMenuToggle
  ]
})
export class InicioDelegadoPage implements OnInit {

  usuario: Usuario | null = null;
  estudiantes: EstudianteDelegado[] = [];
  cargando: boolean = true;
  errorMensaje: string = '';
  busqueda = '';
  cursoSeleccionado = '';

  constructor(
    private authService: AuthService,
    private feedback: FeedbackService
  ) {}

  ngOnInit() {
    this.usuario = this.authService.getUsuario();
  }

  ionViewWillEnter() {
    this.usuario = this.authService.getUsuario();
    this.cargarEstudiantes();
  }

  cargarEstudiantes() {
    this.cargando = true;
    this.errorMensaje = '';
    this.authService.getPerfilDelegado().subscribe({
      next: (usuario) => this.usuario = usuario,
      error: () => undefined
    });
    this.authService.getEstudiantesDelegado().subscribe({
      next: (res) => {
        this.cargando = false;
        this.estudiantes = res || [];
      },
      error: async (err) => {
        this.cargando = false;
        this.errorMensaje = 'No se pudieron cargar los estudiantes. Intenta nuevamente.';
      }
    });
  }

  get esInspector(): boolean {
    return this.usuario?.tipo_delegado === 'inspector';
  }

  get nombreAsignacion(): string {
    const sedes = this.usuario?.sedes_responsable || [];
    if (sedes.length === 1) return sedes[0].nombre;
    if (sedes.length > 1) return `${sedes.length} sedes`;
    return this.usuario?.colegio_nombre || 'Todo el establecimiento';
  }

  get cursos(): string[] {
    return [...new Set(this.estudiantes.map(est => est.curso).filter(Boolean))].sort();
  }

  get estudiantesFiltrados(): EstudianteDelegado[] {
    const termino = this.busqueda.trim().toLocaleLowerCase('es');
    return this.estudiantes.filter(est => {
      const coincideCurso = !this.cursoSeleccionado || est.curso === this.cursoSeleccionado;
      const contenido = `${est.nombre_completo} ${est.rut} ${est.curso || ''}`.toLocaleLowerCase('es');
      return coincideCurso && (!termino || contenido.includes(termino));
    });
  }

  get totalConConductor(): number {
    return this.estudiantes.filter(est => !!est.conductor_nombre).length;
  }

  limpiarFiltros(): void {
    this.busqueda = '';
    this.cursoSeleccionado = '';
  }

  llamarTelefono(numero?: string) {
    if (numero) {
      window.location.href = `tel:${numero}`;
    } else {
      this.mostrarToast('No hay teléfono registrado para contactar.', 'warning');
    }
  }

  private async mostrarToast(mensaje: string, color: 'success' | 'danger' | 'warning') {
    await this.feedback.show(mensaje, color as FeedbackType, 3000);
  }
}
