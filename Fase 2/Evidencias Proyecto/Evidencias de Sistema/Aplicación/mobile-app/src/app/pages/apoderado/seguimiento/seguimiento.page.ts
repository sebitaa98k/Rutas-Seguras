import { Component, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { IonicModule } from '@ionic/angular';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';
import * as L from 'leaflet';

import { SeguimientoService, Seguimiento } from '../../../services/seguimiento.service';
import { GeocodingService } from '../../../services/geocoding.service';
import { PosicionFurgon, PuntoTrazado, SeguidorTrazado } from '../../../utils/seguidor-trazado';
import { Estudiante, EstudianteService } from '../../../services/estudiante.service';

/** Cada cuánto se pide la posición del furgón (antes 10 s: se veía con mucho atraso). */
const CONSULTA_SEGUIMIENTO_MS = 3000;
/** Duración del deslizamiento del furgón entre una posición y la siguiente. */
const DURACION_MOVIMIENTO_MS = 1500;

/** Desliza el marcador hasta la nueva posición en vez de saltar. */
function moverSuave(marcador: L.Marker, destino: [number, number]): void {
  const origen = marcador.getLatLng();
  const inicio = performance.now();
  const paso = (ahora: number) => {
    const t = Math.min(1, (ahora - inicio) / DURACION_MOVIMIENTO_MS);
    marcador.setLatLng([
      origen.lat + (destino[0] - origen.lat) * t,
      origen.lng + (destino[1] - origen.lng) * t
    ]);
    if (t < 1) requestAnimationFrame(paso);
  };
  requestAnimationFrame(paso);
}

@Component({
  selector: 'app-seguimiento',
  templateUrl: './seguimiento.page.html',
  styleUrls: ['./seguimiento.page.scss'],
  standalone: true,
  imports: [CommonModule, IonicModule]
})
export class SeguimientoPage implements OnDestroy {
  seguimiento: Seguimiento | null = null;
  estudiantes: Estudiante[] = [];
  estudianteSeleccionadoId: number | null = null;
  cargando = true;
  error = '';

  private estudiantesSubscription?: Subscription;
  private seguimientoSubscription?: Subscription;
  private actualizacionTimer?: ReturnType<typeof setInterval>;
  private mapa?: L.Map;
  private marcadorFurgon?: L.Marker;
  private marcadoresRuta: L.Marker[] = [];
  private firmaRecorrido = '';
  private readonly seguidor: SeguidorTrazado;

  constructor(
    private router: Router,
    private seguimientoService: SeguimientoService,
    private geocodingService: GeocodingService,
    private estudianteService: EstudianteService
  ) {
    this.seguidor = new SeguidorTrazado(
      puntos => this.geocodingService.trazarRuta(puntos),
      { color: '#167d73', weight: 5, opacity: 0.88 }
    );
  }

  ionViewWillEnter(): void {
    this.detenerActualizacion();
    this.cargarEstudiantes();
  }

  ionViewWillLeave(): void {
    this.detenerActualizacion();
    this.destruirMapa();
  }

  cargarSeguimiento(mostrarCarga = true): void {
    if (mostrarCarga && !this.seguimiento) this.cargando = true;
    this.error = '';
    this.seguimientoSubscription?.unsubscribe();
    const estudianteId = this.estudiantes.length > 1
      ? this.estudianteSeleccionadoId ?? undefined
      : undefined;
    this.seguimientoSubscription = this.seguimientoService.obtenerSeguimiento(estudianteId).subscribe({
      next: data => {
        this.seguimiento = data;
        this.cargando = false;
        setTimeout(() => this.actualizarMapa(), 0);
      },
      error: err => {
        console.error('Error al cargar seguimiento:', err);
        this.cargando = false;
        if (!this.seguimiento) {
          this.error = err?.error?.message || 'No se pudo cargar la información del seguimiento.';
        }
      }
    });
  }

  seleccionarHijo(event: Event): void {
    const estudianteId = Number((event.target as HTMLSelectElement).value);
    if (!Number.isInteger(estudianteId) || estudianteId === this.estudianteSeleccionadoId) return;

    this.estudianteSeleccionadoId = estudianteId;
    this.seguimiento = null;
    this.destruirMapa();
    this.cargarSeguimiento();
  }

  /** Sin ruta en curso se muestra dónde quedó el estudiante en lugar del estado de una ruta. */
  get sinRutaEnCurso(): boolean {
    return !!this.seguimiento && this.seguimiento.ruta.estado !== 'en_camino';
  }

  get iconoDondeEsta(): string {
    switch (this.seguimiento?.estudiante.donde_esta?.lugar) {
      case 'casa': return '🏠';
      case 'colegio': return '🏫';
      case 'furgon': return '🚌';
      default: return '📍';
    }
  }

  get tituloDondeEsta(): string {
    const nombre = this.seguimiento?.estudiante.nombre.split(' ')[0] || 'Tu hijo';
    switch (this.seguimiento?.estudiante.donde_esta?.lugar) {
      case 'casa': return `${nombre} está en casa`;
      case 'colegio': return `${nombre} está en el colegio`;
      case 'furgon': return `${nombre} va en el furgón`;
      default: return 'Sin recorridos registrados hoy';
    }
  }

  get estadoRuta(): string {
    if (this.sinRutaEnCurso) return 'No hay rutas activas';
    switch (this.seguimiento?.ruta.estado) {
      case 'en_camino': return 'En camino';
      case 'no_iniciada': return 'Ruta no iniciada';
      case 'finalizada': return 'Ruta finalizada';
      case 'pausada': return 'Ruta pausada';
      default: return 'Estado desconocido';
    }
  }

  get descripcionEstado(): string {
    const terminada = this.seguimiento?.ultima_ruta_terminada;
    if (this.sinRutaEnCurso && terminada) {
      const tramo = terminada.sentido === 'hacia_colegio' ? 'de ida' : 'de vuelta';
      return `La ruta ${tramo} "${terminada.nombre}" terminó a las ${terminada.hora}.`;
    }
    if (this.sinRutaEnCurso && this.seguimiento?.ruta.estado === 'no_iniciada') {
      return `La próxima ruta, "${this.seguimiento.ruta.nombre}", aún no comienza.`;
    }
    switch (this.seguimiento?.ruta.estado) {
      case 'en_camino': return 'El furgón se encuentra en ruta';
      case 'no_iniciada': return 'El conductor aún no ha iniciado la ruta';
      case 'finalizada': return 'La ruta ha finalizado';
      case 'pausada': return 'La ruta se encuentra temporalmente pausada';
      default: return 'Estado de la ruta no disponible';
    }
  }

  get tieneUbicacion(): boolean {
    return this.seguimiento?.ubicacion.latitud != null
      && this.seguimiento?.ubicacion.longitud != null;
  }

  get tieneRecorrido(): boolean {
    return !!this.seguimiento?.ruta.puntos_recorrido?.length;
  }

  verRutaCompleta(): void {
    if (!this.mapa) return;
    const capas: L.Layer[] = [
      ...this.marcadoresRuta,
      ...(this.seguidor.capaLinea ? [this.seguidor.capaLinea] : []),
      ...(this.marcadorFurgon ? [this.marcadorFurgon] : [])
    ];
    if (capas.length) this.mapa.fitBounds(L.featureGroup(capas).getBounds().pad(0.15));
  }

  volver(): void {
    this.router.navigate(['/apoderado/inicio']);
  }

  private actualizarMapa(): void {
    if (!this.seguimiento || (!this.tieneRecorrido && !this.tieneUbicacion)) return;
    const contenedor = document.getElementById('mapa-seguimiento');
    if (!contenedor) return;

    if (!this.mapa) {
      this.mapa = L.map(contenedor).setView(this.centroInicial(), 14);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 20,
        attribution: '&copy; colaboradores de OpenStreetMap'
      }).addTo(this.mapa);
      setTimeout(() => this.mapa?.invalidateSize(), 100);
    }

    this.actualizarMarcadorFurgon();
    const puntos = (this.seguimiento.ruta.puntos_recorrido || [])
      .map(punto => ({ ...punto, latitud: Number(punto.latitud), longitud: Number(punto.longitud) }))
      .filter(punto => Number.isFinite(punto.latitud) && Number.isFinite(punto.longitud));
    this.seguidor.actualizar(this.mapa, this.destinosLinea(puntos), this.posicionFurgon(), () => this.verRutaCompleta());

    const firma = puntos.map(punto => `${punto.tipo}:${punto.id}:${punto.latitud}:${punto.longitud}`).join('|');
    if (!puntos.length || firma === this.firmaRecorrido) return;

    this.firmaRecorrido = firma;
    this.marcadoresRuta.forEach(marcador => marcador.remove());
    this.marcadoresRuta = puntos.map((punto, index) => {
      const establecimiento = punto.tipo === 'sede' || punto.tipo === 'colegio';
      const icono = L.divIcon({
        className: establecimiento ? 'tracking-pin school-pin' : 'tracking-pin stop-pin',
        html: `<span>${establecimiento ? '🏫' : index + 1}</span>`,
        iconSize: [32, 32],
        iconAnchor: [16, 32]
      });
      return L.marker([punto.latitud, punto.longitud], { icon: icono }).addTo(this.mapa!);
    });
  }

  /** En curso: lo que le falta al furgón. Antes de partir: el recorrido completo como vista previa. */
  private destinosLinea(puntos: PuntoTrazado[]): PuntoTrazado[] {
    if (this.seguimiento?.ruta.estado !== 'en_camino') return puntos;
    return (this.seguimiento.ruta.puntos_trazado || [])
      .map(punto => ({ latitud: Number(punto.latitud), longitud: Number(punto.longitud) }))
      .filter(punto => Number.isFinite(punto.latitud) && Number.isFinite(punto.longitud));
  }

  private posicionFurgon(): PosicionFurgon | null {
    if (!this.tieneUbicacion || this.seguimiento?.ruta.estado !== 'en_camino') return null;
    const ubicacion = this.seguimiento.ubicacion;
    return { latitud: ubicacion.latitud!, longitud: ubicacion.longitud!, precision: ubicacion.precision_metros };
  }

  private centroInicial(): L.LatLngExpression {
    if (this.tieneUbicacion) {
      return [this.seguimiento!.ubicacion.latitud!, this.seguimiento!.ubicacion.longitud!];
    }
    const primero = this.seguimiento!.ruta.puntos_recorrido[0];
    return [Number(primero.latitud), Number(primero.longitud)];
  }

  private actualizarMarcadorFurgon(): void {
    if (!this.mapa || !this.tieneUbicacion) return;
    const posicion: L.LatLngExpression = [
      this.seguimiento!.ubicacion.latitud!,
      this.seguimiento!.ubicacion.longitud!
    ];
    if (this.marcadorFurgon) {
      moverSuave(this.marcadorFurgon, posicion as [number, number]);
      return;
    }
    const icono = L.divIcon({
      className: 'tracking-pin bus-pin',
      html: '<span>🚌</span>',
      iconSize: [38, 38],
      iconAnchor: [19, 19]
    });
    this.marcadorFurgon = L.marker(posicion, { icon: icono }).addTo(this.mapa);
  }

  private detenerActualizacion(): void {
    if (this.actualizacionTimer) clearInterval(this.actualizacionTimer);
    this.actualizacionTimer = undefined;
    this.estudiantesSubscription?.unsubscribe();
    this.seguimientoSubscription?.unsubscribe();
  }

  private cargarEstudiantes(): void {
    this.cargando = true;
    this.error = '';
    this.estudiantesSubscription?.unsubscribe();
    this.estudiantesSubscription = this.estudianteService.obtenerEstudiantes().subscribe({
      next: estudiantes => {
        this.estudiantes = estudiantes.filter(
          (estudiante): estudiante is Estudiante & { id: number } => estudiante.id != null
        );
        if (!this.estudiantes.length) {
          this.cargando = false;
          this.error = 'No hay estudiantes asociados a tu cuenta.';
          return;
        }
        if (this.estudiantes.length > 1) {
          const seleccionSigueDisponible = this.estudiantes.some(
            estudiante => estudiante.id === this.estudianteSeleccionadoId
          );
          if (!seleccionSigueDisponible) {
            this.estudianteSeleccionadoId = this.estudiantes[0].id!;
          }
        } else {
          this.estudianteSeleccionadoId = null;
        }
        this.cargarSeguimiento();
        this.actualizacionTimer = setInterval(() => this.cargarSeguimiento(false), CONSULTA_SEGUIMIENTO_MS);
      },
      error: err => {
        console.error('Error al cargar estudiantes:', err);
        this.cargando = false;
        this.error = err?.error?.message || 'No se pudo cargar la lista de estudiantes.';
      }
    });
  }

  private destruirMapa(): void {
    this.seguidor.destruir();
    this.mapa?.remove();
    this.mapa = undefined;
    this.marcadorFurgon = undefined;
    this.marcadoresRuta = [];
    this.firmaRecorrido = '';
  }

  ngOnDestroy(): void {
    this.detenerActualizacion();
    this.destruirMapa();
  }
}
