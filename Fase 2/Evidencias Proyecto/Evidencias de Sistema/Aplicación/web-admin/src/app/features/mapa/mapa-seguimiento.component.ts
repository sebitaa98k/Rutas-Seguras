import { Component, OnInit, OnDestroy, Input, Output, EventEmitter, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import * as L from 'leaflet';
import { RutasService, Ruta } from '../../core/services/rutas.service';
import { PosicionFurgon, PuntoTrazado, SeguidorTrazado } from '../../core/utils/seguidor-trazado';

interface PuntoMapa {
  tipo: 'estudiante' | 'sede' | 'colegio';
  id: number;
  nombre: string;
  direccion: string;
  latitud: number;
  longitud: number;
}

/** Seguimiento en vivo de una ruta: paradas reales, trazado por calles y GPS del furgón. */
@Component({
  selector: 'app-mapa-seguimiento',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './mapa-seguimiento.component.html',
  styleUrl: './mapa-seguimiento.component.scss'
})
export class MapaSeguimientoComponent implements OnInit, OnDestroy {
  @Input({ required: true }) rutaId!: number | string;
  @Input() rutaNombre = '';

  @Output() cerrar = new EventEmitter<void>();

  cargando = signal(true);
  error = signal('');
  ultimaActualizacion = signal<string | null>(null);
  /** El furgón está recorriendo la ruta en este momento. */
  enRecorrido = signal(false);
  /** Hora (ISO) en que el conductor terminó la ruta; null si no está terminada. */
  terminadaEn = signal<string | null>(null);

  private map?: L.Map;
  private furgonMarker?: L.Marker;
  private capaParadas?: L.LayerGroup;
  private firmaParadas = '';
  private actualizacionTimer?: ReturnType<typeof setInterval>;
  private rutaSubscription?: Subscription;
  private readonly seguidor: SeguidorTrazado;

  constructor(private rutasService: RutasService) {
    this.seguidor = new SeguidorTrazado(
      puntos => this.rutasService.trazarRecorrido(puntos),
      { color: '#2d6861', weight: 5, opacity: 0.9, lineCap: 'round', lineJoin: 'round' }
    );
  }

  ngOnInit(): void {
    if (!document.getElementById('leaflet-css')) {
      const link = document.createElement('link');
      link.id = 'leaflet-css';
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(link);
    }
    this.cargarRuta();
    this.actualizacionTimer = setInterval(() => this.cargarRuta(), 10000);
  }

  ngOnDestroy(): void {
    this.destruirMapa();
  }

  cerrarModal(event?: MouseEvent): void {
    event?.stopPropagation();
    event?.preventDefault();
    this.destruirMapa();
    this.cerrar.emit();
  }

  private cargarRuta(): void {
    this.rutaSubscription?.unsubscribe();
    this.rutaSubscription = this.rutasService.getRuta(this.rutaId).subscribe({
      next: ruta => {
        this.cargando.set(false);
        this.error.set('');
        // Se espera al render del contenedor del mapa.
        setTimeout(() => this.actualizarMapa(ruta), 0);
      },
      error: err => {
        this.cargando.set(false);
        this.error.set(err?.error?.message || 'No fue posible cargar la ruta.');
      }
    });
  }

  private actualizarMapa(ruta: Ruta): void {
    const contenedor = document.getElementById('mapa');
    if (!contenedor) return;

    const puntos: PuntoMapa[] = (ruta.puntos_recorrido || [])
      .map(punto => ({ ...punto, latitud: Number(punto.latitud), longitud: Number(punto.longitud) }))
      .filter(punto => Number.isFinite(punto.latitud) && Number.isFinite(punto.longitud));
    const gps = this.posicionGps(ruta);

    if (!this.map) {
      const centro: L.LatLngExpression = gps ?? (puntos[0] ? [puntos[0].latitud, puntos[0].longitud] : [-33.45, -70.66]);
      this.map = L.map(contenedor, { zoomControl: false }).setView(centro, 14);
      L.control.zoom({ position: 'bottomright' }).addTo(this.map);
      // Mismas teselas que el resto de los mapas: CARTO ahora exige API key.
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
      }).addTo(this.map);
      setTimeout(() => this.map?.invalidateSize(), 300);
    }

    this.ultimaActualizacion.set(ruta.ubicacion_actualizada_en ?? null);
    this.actualizarFurgon(gps);

    const enRuta = ruta.estado === 'en_ruta';
    this.enRecorrido.set(enRuta);
    this.terminadaEn.set(ruta.estado === 'finalizada' ? ruta.finalizada_en ?? null : null);
    // En curso: lo que le falta al furgón. Antes de partir: el recorrido completo como vista previa.
    const destinos: PuntoTrazado[] = enRuta
      ? (ruta.puntos_trazado || [])
        .map(punto => ({ latitud: Number(punto.latitud), longitud: Number(punto.longitud) }))
        .filter(punto => Number.isFinite(punto.latitud) && Number.isFinite(punto.longitud))
      : puntos;
    const precision = Number(ruta.precision_gps_metros);
    const furgon: PosicionFurgon | null = gps && enRuta
      ? { latitud: gps[0], longitud: gps[1], precision: Number.isFinite(precision) ? precision : null }
      : null;
    this.seguidor.actualizar(this.map!, destinos, furgon, () => this.ajustarVista(puntos, gps));

    const firma = puntos.map(punto => `${punto.tipo}:${punto.id}:${punto.latitud}:${punto.longitud}`).join('|');
    if (firma === this.firmaParadas) return;
    this.firmaParadas = firma;
    this.dibujarParadas(puntos);
  }

  private posicionGps(ruta: Ruta): [number, number] | null {
    const latitud = Number(ruta.ultima_latitud);
    const longitud = Number(ruta.ultima_longitud);
    if (ruta.ultima_latitud == null || ruta.ultima_longitud == null) return null;
    return Number.isFinite(latitud) && Number.isFinite(longitud) ? [latitud, longitud] : null;
  }

  private dibujarParadas(puntos: PuntoMapa[]): void {
    this.capaParadas?.remove();
    this.capaParadas = L.layerGroup().addTo(this.map!);
    let numero = 0;
    for (const punto of puntos) {
      const esEstablecimiento = punto.tipo !== 'estudiante';
      if (!esEstablecimiento) numero++;
      const icono = L.divIcon({
        html: `<div class="custom-pin ${esEstablecimiento ? 'pin-destino' : 'pin-parada'}"><span>${esEstablecimiento ? '🏫' : numero}</span></div>`,
        className: 'custom-leaflet-marker',
        iconSize: [38, 38],
        iconAnchor: [19, 19]
      });
      L.marker([punto.latitud, punto.longitud], { icon: icono })
        .bindPopup(`<b>${this.escapar(punto.nombre)}</b><br>${this.escapar(punto.direccion)}`)
        .addTo(this.capaParadas);
    }
  }

  private actualizarFurgon(gps: [number, number] | null): void {
    if (!this.map) return;
    if (!gps) {
      this.furgonMarker?.remove();
      this.furgonMarker = undefined;
      return;
    }
    if (this.furgonMarker) {
      this.furgonMarker.setLatLng(gps);
      return;
    }
    const icono = L.divIcon({
      html: `
        <div class="furgon-pin-container">
          <div class="pulse-ring"></div>
          <div class="furgon-card">🚌</div>
        </div>`,
      className: 'custom-leaflet-marker',
      iconSize: [44, 44],
      iconAnchor: [22, 22]
    });
    this.furgonMarker = L.marker(gps, { icon: icono, zIndexOffset: 1000 })
      .bindPopup('<b>Furgón escolar</b><br>Última posición GPS')
      .addTo(this.map);
  }

  private ajustarVista(puntos: PuntoMapa[], gps: [number, number] | null): void {
    if (!this.map) return;
    const coordenadas: [number, number][] = puntos.map(punto => [punto.latitud, punto.longitud]);
    if (gps) coordenadas.push(gps);
    if (coordenadas.length) {
      this.map.fitBounds(L.latLngBounds(coordenadas), { padding: [40, 40], maxZoom: 16 });
    }
  }

  private escapar(texto: string): string {
    const div = document.createElement('div');
    div.textContent = texto ?? '';
    return div.innerHTML;
  }

  private destruirMapa(): void {
    if (this.actualizacionTimer) clearInterval(this.actualizacionTimer);
    this.actualizacionTimer = undefined;
    this.rutaSubscription?.unsubscribe();
    this.seguidor.destruir();
    this.map?.remove();
    this.map = undefined;
    this.furgonMarker = undefined;
    this.capaParadas = undefined;
    this.firmaParadas = '';
  }
}
