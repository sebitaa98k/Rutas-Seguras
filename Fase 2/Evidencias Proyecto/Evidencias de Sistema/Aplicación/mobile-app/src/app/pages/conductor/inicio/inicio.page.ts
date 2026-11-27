import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

import {
  IonContent,
  IonButton,
  IonIcon,
  IonMenuToggle,
  IonSpinner
} from '@ionic/angular/standalone';

import { addIcons } from 'ionicons';

import {
  menuOutline,
  busOutline,
  playCircleOutline,
  personOutline,
  locationOutline,
  notificationsOutline,
  informationCircleOutline,
  cardOutline,
  shieldCheckmarkOutline,
  alertCircleOutline,
  schoolOutline
} from 'ionicons/icons';

import { AuthService, Usuario } from '../../../services/auth.service';
import { NotificationService } from '../../../services/notification.service';

/** Parada de la ruta asignada; la ruta es la fuente de verdad de los niños a cargo. */
export interface ParadaInicio {
  id: number;
  nombre: string;
  curso: string;
  direccion: string;
  apoderadoNombre: string;
  personaAutorizada: string;
  rutPersonaAutorizada: string;
  completada: boolean;
  /** Aviso del apoderado: hoy no usa el furgón en este tramo. */
  noAsiste: boolean;
}

addIcons({
  menuOutline,
  busOutline,
  playCircleOutline,
  personOutline,
  locationOutline,
  notificationsOutline,
  informationCircleOutline,
  cardOutline,
  shieldCheckmarkOutline,
  alertCircleOutline,
  schoolOutline
});

@Component({
  selector: 'app-inicio-conductor',
  templateUrl: './inicio.page.html',
  styleUrls: ['./inicio.page.scss'],
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    IonContent,
    IonButton,
    IonIcon,
    IonMenuToggle,
    IonSpinner
  ]
})
export class InicioPage implements OnInit {

  usuario: Usuario | null = null;
  rutaNombre = '';
  rutaEstado = '';
  paradas: ParadaInicio[] = [];
  cargandoEstudiantes: boolean = true;
  errorEstudiantes: string = '';

  constructor(
    private authService: AuthService,
    private notificationService: NotificationService
  ) {}

  ngOnInit() {
    this.cargarDatosConductor();
  }

  ionViewWillEnter() {
    this.cargarDatosConductor();
  }

  cargarDatosConductor() {
    this.usuario = this.authService.getUsuario();
    this.cargarRutaAsignada();
  }

  cargarRutaAsignada() {
    this.cargandoEstudiantes = true;
    this.errorEstudiantes = '';

    this.notificationService.obtenerMiRuta().subscribe({
      next: (ruta) => {
        this.rutaNombre = ruta?.nombre || '';
        this.rutaEstado = ruta?.estado || '';
        this.paradas = (ruta?.paradas || []).map((parada: any) => ({
          id: parada.estudiante_id,
          nombre: parada.estudiante_nombre,
          curso: parada.curso || '',
          direccion: parada.direccion || '',
          apoderadoNombre: parada.apoderado_nombre || '',
          personaAutorizada: [
            ...(parada.apoderado_nombre ? [`${parada.apoderado_nombre} (Apoderado)`] : []),
            ...(parada.personas_autorizadas || []).map((p: any) => `${p.nombre} (Persona autorizada)`),
          ].join(' · '),
          rutPersonaAutorizada: '',
          completada: ruta.estado === 'en_ruta' && !!parada.completada,
          noAsiste: parada.estado === 'no_asiste'
        }));
        this.cargandoEstudiantes = false;
      },
      error: (err) => {
        this.rutaNombre = '';
        this.rutaEstado = '';
        this.paradas = [];
        this.cargandoEstudiantes = false;
        // 404 significa que aún no hay ruta asignada: se muestra el estado vacío.
        if (err?.status !== 404) {
          console.error('Error al obtener la ruta del conductor:', err);
          this.errorEstudiantes = err?.error?.message || 'No se pudo cargar tu ruta asignada.';
        }
      }
    });
  }

  get saludo(): string {
    const hora = new Date().getHours();
    if (hora < 12) {
      return 'Buenos días';
    } else if (hora < 20) {
      return 'Buenas tardes';
    } else {
      return 'Buenas noches';
    }
  }

  get nombreMostrar(): string {
    if (!this.usuario) return 'Conductor';
    return this.usuario.first_name || 'Conductor';
  }

  get totalEstudiantes(): number {
    return this.paradas.length;
  }

  get proximaParada(): ParadaInicio | null {
    return this.paradas.find(parada => !parada.completada && !parada.noAsiste) || null;
  }

  get estadoRutaTexto(): string {
    switch (this.rutaEstado) {
      case 'en_ruta': return 'Ruta en recorrido';
      case 'finalizada': return 'Ruta finalizada';
      case 'activa': return 'Ruta no iniciada';
      default: return 'Sin ruta asignada';
    }
  }
}
