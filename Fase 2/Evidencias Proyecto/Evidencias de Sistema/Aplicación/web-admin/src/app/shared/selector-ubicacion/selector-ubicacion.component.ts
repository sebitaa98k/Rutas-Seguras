import {
  Component, ElementRef, EventEmitter, Input, OnChanges, OnDestroy, Output,
  SimpleChanges, ViewChild, inject, signal
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import * as L from 'leaflet';
import { ColegioService, CoincidenciaGeo } from '../../core/services/colegio.service';
import { combinarDireccion, extraerNumeracion, ordenarPorComuna } from '../direccion.util';
import { REGIONES_CHILE, comunasDeRegion } from '../chile-territorio';

export interface UbicacionSeleccionada {
  /** Solo calle y número (con depto/casa si corresponde). */
  direccion: string;
  comuna: string;
  region: string;
  latitud: number | null;
  longitud: number | null;
}

// Centro de Santiago, usado cuando no hay ningún punto de referencia.
const CENTRO_POR_DEFECTO: [number, number] = [-33.4489, -70.6693];

/**
 * Campo de dirección con búsqueda y mapa con marcador movible.
 * El marcador se puede arrastrar o reubicar haciendo clic en el mapa.
 */
@Component({
  selector: 'app-selector-ubicacion',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './selector-ubicacion.component.html',
  styleUrl: './selector-ubicacion.component.scss'
})
export class SelectorUbicacionComponent implements OnChanges, OnDestroy {
  @Input() direccion: string | null | undefined = '';
  @Input() comuna: string | null | undefined = '';
  @Input() region: string | null | undefined = '';
  @Input() latitud: number | string | null | undefined = null;
  @Input() longitud: number | string | null | undefined = null;
  @Input() etiqueta = 'Dirección';
  @Input() placeholder = 'Ej: Av. Providencia 1234, depto 502';
  @Input() requerido = false;
  @Input() invalido = false;
  @Input() textoMarcador = 'Ubicación seleccionada';
  /** Punto inicial del mapa manual cuando aún no hay coordenadas. */
  @Input() latitudReferencia: number | string | null | undefined = null;
  @Input() longitudReferencia: number | string | null | undefined = null;
  @Output() ubicacionCambio = new EventEmitter<UbicacionSeleccionada>();

  @ViewChild('contenedorMapa') private contenedorMapa?: ElementRef<HTMLDivElement>;

  private colegioService = inject(ColegioService);

  readonly regiones = REGIONES_CHILE;

  textoDireccion = signal('');
  comunaSeleccionada = signal('');
  regionSeleccionada = signal('');
  lat = signal<number | null>(null);
  lng = signal<number | null>(null);
  buscando = signal(false);
  coincidencias = signal<CoincidenciaGeo[]>([]);
  mensaje = signal('');
  /** Dirección que entregó el buscador, solo como referencia visual. */
  referenciaMapa = signal('');

  private mapa?: L.Map;
  private marcador?: L.Marker;

  ngOnChanges(cambios: SimpleChanges): void {
    if (cambios['direccion']) {
      this.textoDireccion.set(this.direccion || '');
    }
    if (cambios['comuna']) {
      this.comunaSeleccionada.set(this.comuna || '');
    }
    if (cambios['region']) {
      this.regionSeleccionada.set(this.region || '');
    }
    if (cambios['latitud'] || cambios['longitud']) {
      const lat = this.aNumero(this.latitud);
      const lng = this.aNumero(this.longitud);
      if (lat === this.lat() && lng === this.lng()) return;
      this.lat.set(lat);
      this.lng.set(lng);
      if (lat != null && lng != null) {
        setTimeout(() => this.mostrarMapa(), 0);
      } else {
        this.destruirMapa();
      }
    }
  }

  ngOnDestroy(): void {
    this.destruirMapa();
  }

  get tienePunto(): boolean {
    return this.lat() != null && this.lng() != null;
  }

  /** Comunas de la región elegida; vacío significa que la comuna se escribe a mano. */
  get comunasDisponibles(): string[] {
    return comunasDeRegion(this.regionSeleccionada());
  }

  regionElegida(region: string): void {
    this.regionSeleccionada.set(region);
    const comunas = comunasDeRegion(region);
    if (comunas.length && !comunas.includes(this.comunaSeleccionada())) {
      this.comunaSeleccionada.set('');
    }
    this.coincidencias.set([]);
    this.emitir();
  }

  comunaElegida(comuna: string): void {
    this.comunaSeleccionada.set(comuna);
    this.coincidencias.set([]);
    this.emitir();
  }

  get faltaNumeracion(): boolean {
    const texto = this.textoDireccion().trim();
    return !!texto && !extraerNumeracion(texto);
  }

  // Editar el texto no mueve ni borra el punto: así se puede corregir la numeración
  // después de ajustar el marcador.
  direccionEscrita(texto: string): void {
    this.textoDireccion.set(texto);
    this.coincidencias.set([]);
    this.emitir();
  }

  buscar(): void {
    const calle = this.textoDireccion().trim();
    if (calle.length < 4) {
      this.mensaje.set('Ingresa una dirección más completa antes de buscar.');
      return;
    }
    const comuna = this.comunaSeleccionada().trim();
    if (!comuna) {
      this.mensaje.set('Selecciona la región y la comuna antes de buscar.');
      return;
    }
    // Solo el primer tramo (calle y número): la comuna elegida manda sobre lo escrito.
    const query = `${calle.split(',')[0].trim()}, ${comuna}`;
    this.buscando.set(true);
    this.coincidencias.set([]);
    this.mensaje.set('');
    this.colegioService.buscarDirecciones(query).subscribe({
      next: respuesta => {
        this.buscando.set(false);
        this.coincidencias.set(ordenarPorComuna(respuesta.coincidencias || [], comuna));
        if (!respuesta.coincidencias?.length) {
          this.mensaje.set('No se encontraron coincidencias. Puedes elegir el punto manualmente en el mapa.');
        }
      },
      error: error => {
        this.buscando.set(false);
        this.mensaje.set(
          error?.error?.message || 'No fue posible buscar la dirección. Puedes elegir el punto manualmente en el mapa.'
        );
      }
    });
  }

  seleccionar(opcion: CoincidenciaGeo): void {
    this.textoDireccion.set(combinarDireccion(this.textoDireccion(), opcion));
    this.referenciaMapa.set(opcion.nombreCompleto);
    this.coincidencias.set([]);
    this.fijarPunto(Number(opcion.latitud), Number(opcion.longitud));
    this.mensaje.set('El buscador ubica la calle de forma aproximada: arrastra el marcador o haz clic en el mapa hasta la casa exacta.');
    setTimeout(() => this.mostrarMapa(), 0);
  }

  abrirMapaManual(): void {
    if (!this.tienePunto) {
      const refLat = this.aNumero(this.latitudReferencia);
      const refLng = this.aNumero(this.longitudReferencia);
      const [lat, lng] = refLat != null && refLng != null ? [refLat, refLng] : CENTRO_POR_DEFECTO;
      this.fijarPunto(lat, lng);
    }
    this.mensaje.set('Haz clic en el mapa o arrastra el marcador hasta el punto exacto.');
    setTimeout(() => this.mostrarMapa(), 0);
  }

  quitarPunto(): void {
    this.lat.set(null);
    this.lng.set(null);
    this.referenciaMapa.set('');
    this.destruirMapa();
    this.mensaje.set('');
    this.emitir();
  }

  private fijarPunto(latitud: number, longitud: number): void {
    this.lat.set(Number(latitud.toFixed(6)));
    this.lng.set(Number(longitud.toFixed(6)));
    this.marcador?.setLatLng([latitud, longitud]);
    this.emitir();
  }

  private emitir(): void {
    this.ubicacionCambio.emit({
      direccion: this.textoDireccion(),
      comuna: this.comunaSeleccionada(),
      region: this.regionSeleccionada(),
      latitud: this.lat(),
      longitud: this.lng(),
    });
  }

  private mostrarMapa(): void {
    const lat = this.lat();
    const lng = this.lng();
    const contenedor = this.contenedorMapa?.nativeElement;
    if (lat == null || lng == null || !contenedor) return;

    if (this.mapa && this.mapa.getContainer() === contenedor) {
      this.marcador?.setLatLng([lat, lng]);
      this.mapa.setView([lat, lng], Math.max(this.mapa.getZoom(), 17));
      return;
    }

    this.destruirMapa();
    this.mapa = L.map(contenedor).setView([lat, lng], 18);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 20,
      attribution: '&copy; colaboradores de OpenStreetMap',
    }).addTo(this.mapa);

    const icono = L.divIcon({
      className: 'selector-ubicacion-icono',
      html: '<span></span>',
      iconSize: [28, 28],
      iconAnchor: [14, 28],
    });
    this.marcador = L.marker([lat, lng], { draggable: true, icon: icono }).addTo(this.mapa);
    this.marcador.bindTooltip(this.textoMarcador);
    this.marcador.on('dragend', () => {
      const posicion = this.marcador!.getLatLng();
      this.fijarPunto(posicion.lat, posicion.lng);
    });
    this.mapa.on('click', evento => this.fijarPunto(evento.latlng.lat, evento.latlng.lng));
    setTimeout(() => this.mapa?.invalidateSize(), 100);
  }

  private destruirMapa(): void {
    this.mapa?.remove();
    this.mapa = undefined;
    this.marcador = undefined;
  }

  private aNumero(valor: number | string | null | undefined): number | null {
    if (valor === null || valor === undefined || valor === '') return null;
    const numero = Number(valor);
    return Number.isFinite(numero) ? numero : null;
  }
}
