import {
  Component, ElementRef, EventEmitter, Input, OnChanges, OnDestroy, Output,
  SimpleChanges, ViewChild
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import * as L from 'leaflet';
import {
  IonButton, IonInput, IonItem, IonSelect, IonSelectOption, IonSpinner
} from '@ionic/angular/standalone';

import {
  CoincidenciaDireccion,
  GeocodingService
} from '../../services/geocoding.service';
import { combinarDireccion, extraerNumeracion, ordenarPorComuna } from '../../utils/direccion.util';
import { REGIONES_CHILE, comunasDeRegion } from '../../utils/chile-territorio';

export interface UbicacionSeleccionada {
  /** Solo calle y número (con depto/casa si corresponde). */
  direccion: string;
  comuna: string;
  region: string;
  latitud?: number;
  longitud?: number;
}

// Centro de Santiago, usado cuando no hay ningún punto de referencia.
const CENTRO_POR_DEFECTO: [number, number] = [-33.4489, -70.6693];

/**
 * Campo de dirección con búsqueda y mapa con marcador movible.
 * El marcador se puede arrastrar o reubicar tocando el mapa.
 */
@Component({
  selector: 'app-selector-ubicacion',
  templateUrl: './selector-ubicacion.component.html',
  styleUrls: ['./selector-ubicacion.component.scss'],
  standalone: true,
  imports: [
    CommonModule, FormsModule, IonButton, IonInput, IonItem,
    IonSelect, IonSelectOption, IonSpinner
  ]
})
export class SelectorUbicacionComponent implements OnChanges, OnDestroy {
  @Input() direccion: string | null | undefined = '';
  @Input() comuna: string | null | undefined = '';
  @Input() region: string | null | undefined = '';
  @Input() latitud: number | string | null | undefined;
  @Input() longitud: number | string | null | undefined;
  @Input() etiqueta = 'Dirección';
  @Input() placeholder = 'Ej: Av. Matta 1234, depto 502';
  /** Punto inicial del mapa manual cuando aún no hay coordenadas. */
  @Input() latitudReferencia: number | string | null | undefined;
  @Input() longitudReferencia: number | string | null | undefined;
  @Output() ubicacionCambio = new EventEmitter<UbicacionSeleccionada>();

  @ViewChild('contenedorMapa') private contenedorMapa?: ElementRef<HTMLDivElement>;

  readonly regiones = REGIONES_CHILE;

  textoDireccion = '';
  comunaSeleccionada = '';
  regionSeleccionada = '';
  lat?: number;
  lng?: number;
  buscando = false;
  coincidencias: CoincidenciaDireccion[] = [];
  mensaje = '';
  /** Dirección que entregó el buscador, solo como referencia visual. */
  referenciaMapa = '';

  private mapa?: L.Map;
  private marcador?: L.Marker;

  constructor(private geocodingService: GeocodingService) {}

  ngOnChanges(cambios: SimpleChanges): void {
    if (cambios['direccion']) {
      this.textoDireccion = this.direccion || '';
    }
    if (cambios['comuna']) {
      this.comunaSeleccionada = this.comuna || '';
    }
    if (cambios['region']) {
      this.regionSeleccionada = this.region || '';
    }
    if (cambios['latitud'] || cambios['longitud']) {
      const lat = this.aNumero(this.latitud);
      const lng = this.aNumero(this.longitud);
      if (lat === this.lat && lng === this.lng) return;
      this.lat = lat;
      this.lng = lng;
      if (this.tienePunto) {
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
    return this.lat !== undefined && this.lng !== undefined;
  }

  /** Comunas de la región elegida; vacío significa que la comuna se escribe a mano. */
  get comunasDisponibles(): string[] {
    return comunasDeRegion(this.regionSeleccionada);
  }

  regionElegida(): void {
    const comunas = this.comunasDisponibles;
    if (comunas.length && !comunas.includes(this.comunaSeleccionada)) {
      this.comunaSeleccionada = '';
    }
    this.coincidencias = [];
    this.emitir();
  }

  comunaElegida(): void {
    this.coincidencias = [];
    this.emitir();
  }

  get faltaNumeracion(): boolean {
    const texto = this.textoDireccion.trim();
    return !!texto && !extraerNumeracion(texto);
  }

  // Editar el texto no mueve ni borra el punto: así se puede corregir la numeración
  // después de ajustar el marcador.
  direccionEscrita(): void {
    this.coincidencias = [];
    this.emitir();
  }

  buscar(): void {
    const calle = this.textoDireccion.trim();
    if (calle.length < 4) {
      this.mensaje = 'Escribe una dirección más completa antes de buscar.';
      return;
    }
    const comuna = this.comunaSeleccionada.trim();
    if (!comuna) {
      this.mensaje = 'Selecciona la región y la comuna antes de buscar.';
      return;
    }
    // Solo el primer tramo (calle y número): la comuna elegida manda sobre lo escrito.
    const query = `${calle.split(',')[0].trim()}, ${comuna}`;

    this.mensaje = '';
    this.buscando = true;
    this.coincidencias = [];

    this.geocodingService.buscarDirecciones(query, 6).subscribe({
      next: (respuesta) => {
        this.buscando = false;
        this.coincidencias = ordenarPorComuna(respuesta.coincidencias || [], comuna);
        if (!this.coincidencias.length) {
          this.mensaje = 'No encontramos coincidencias. Prueba agregando comuna o ciudad, o elige el punto en el mapa.';
        }
      },
      error: (err) => {
        console.error('Error buscando dirección:', err);
        this.buscando = false;
        if (err.status === 0) {
          this.mensaje = 'No se pudo conectar con el servidor. Verifica que Django esté iniciado y el teléfono conectado.';
        } else if (err.status === 401 || err.status === 403) {
          this.mensaje = 'Tu sesión venció o no tiene permisos. Vuelve a iniciar sesión.';
        } else {
          this.mensaje = err.error?.message || 'No se pudo buscar la dirección. Puedes elegir el punto en el mapa.';
        }
      }
    });
  }

  seleccionar(coincidencia: CoincidenciaDireccion): void {
    this.textoDireccion = combinarDireccion(this.textoDireccion, coincidencia);
    this.referenciaMapa = coincidencia.nombreCompleto;
    this.coincidencias = [];
    this.mensaje = 'El buscador ubica la calle de forma aproximada: mueve el marcador hasta la casa exacta.';
    this.fijarPunto(Number(coincidencia.latitud), Number(coincidencia.longitud));
    setTimeout(() => this.mostrarMapa(), 0);
  }

  abrirMapaManual(): void {
    if (!this.tienePunto) {
      const refLat = this.aNumero(this.latitudReferencia);
      const refLng = this.aNumero(this.longitudReferencia);
      const [lat, lng] = refLat !== undefined && refLng !== undefined
        ? [refLat, refLng]
        : CENTRO_POR_DEFECTO;
      this.fijarPunto(lat, lng);
    }
    this.mensaje = 'Toca el mapa o arrastra el marcador hasta la entrada exacta.';
    setTimeout(() => this.mostrarMapa(), 0);
  }

  private fijarPunto(latitud: number, longitud: number): void {
    // Django almacena coordenadas con un máximo de 6 decimales.
    this.lat = Number(latitud.toFixed(6));
    this.lng = Number(longitud.toFixed(6));
    this.marcador?.setLatLng([latitud, longitud]);
    this.emitir();
  }

  private emitir(): void {
    this.ubicacionCambio.emit({
      direccion: this.textoDireccion,
      comuna: this.comunaSeleccionada,
      region: this.regionSeleccionada,
      latitud: this.lat,
      longitud: this.lng
    });
  }

  private mostrarMapa(): void {
    const contenedor = this.contenedorMapa?.nativeElement;
    if (this.lat === undefined || this.lng === undefined || !contenedor) {
      return;
    }

    if (this.mapa && this.mapa.getContainer() === contenedor) {
      this.marcador?.setLatLng([this.lat, this.lng]);
      this.mapa.setView([this.lat, this.lng], Math.max(this.mapa.getZoom(), 17));
      return;
    }

    this.destruirMapa();

    this.mapa = L.map(contenedor, {
      zoomControl: true,
      attributionControl: true
    }).setView([this.lat, this.lng], 18);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 20,
      attribution: '&copy; colaboradores de OpenStreetMap'
    }).addTo(this.mapa);

    const icono = L.divIcon({
      className: 'student-location-icon',
      html: '<span></span>',
      iconSize: [28, 28],
      iconAnchor: [14, 28]
    });

    this.marcador = L.marker([this.lat, this.lng], { draggable: true, icon: icono })
      .addTo(this.mapa);

    this.marcador.on('dragend', () => {
      const posicion = this.marcador!.getLatLng();
      this.fijarPunto(posicion.lat, posicion.lng);
    });
    this.mapa.on('click', (evento) => this.fijarPunto(evento.latlng.lat, evento.latlng.lng));

    setTimeout(() => this.mapa?.invalidateSize(), 100);
  }

  private destruirMapa(): void {
    this.mapa?.remove();
    this.mapa = undefined;
    this.marcador = undefined;
  }

  private aNumero(valor: number | string | null | undefined): number | undefined {
    if (valor === null || valor === undefined || valor === '') return undefined;
    const numero = Number(valor);
    return Number.isFinite(numero) ? numero : undefined;
  }
}
