import { Component, OnDestroy } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { Subscription } from 'rxjs';
import * as L from 'leaflet';
import { IonContent, IonSpinner, IonIcon } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { arrowBackOutline, busOutline, callOutline, refreshOutline, shieldCheckmarkOutline } from 'ionicons/icons';

import { SeguimientoService, Seguimiento } from '../../../services/seguimiento.service';
import { GeocodingService } from '../../../services/geocoding.service';
import { PuntoTrazado, SeguidorTrazado } from '../../../utils/seguidor-trazado';

addIcons({ arrowBackOutline, busOutline, callOutline, refreshOutline, shieldCheckmarkOutline });

@Component({
  selector: 'app-seguimiento-delegado',
  templateUrl: './seguimiento.page.html',
  styleUrls: ['./seguimiento.page.scss'],
  standalone: true,
  imports: [CommonModule, IonContent, IonSpinner, IonIcon]
})
export class SeguimientoDelegadoPage implements OnDestroy {
  seguimiento: Seguimiento | null = null;
  cargando = true;
  error = '';

  private seguimientoSub?: Subscription;
  private actualizacionTimer?: ReturnType<typeof setInterval>;
  private mapa?: L.Map;
  private marcadorFurgon?: L.Marker;
  private marcadores: L.Marker[] = [];
  private firmaRecorrido = '';
  private readonly seguidor: SeguidorTrazado;

  constructor(
    private location: Location,
    private seguimientoService: SeguimientoService,
    private geocodingService: GeocodingService
  ) {
    this.seguidor = new SeguidorTrazado(
      puntos => this.geocodingService.trazarRuta(puntos),
      { color: '#0f766e', weight: 5, opacity: 0.88 }
    );
  }

  ionViewWillEnter(): void {
    this.detenerActualizacion();
    this.cargarSeguimiento();
    // Cada 3 s (antes 10 s), igual que el apoderado: el furgón se veía con mucho atraso.
    this.actualizacionTimer = setInterval(() => this.cargarSeguimiento(false), 3000);
  }

  ionViewWillLeave(): void {
    this.detenerActualizacion();
    this.destruirMapa();
  }

  cargarSeguimiento(mostrarCarga = true): void {
    if (mostrarCarga && !this.seguimiento) this.cargando = true;
    this.error = '';
    this.seguimientoSub?.unsubscribe();
    this.seguimientoSub = this.seguimientoService.obtenerSeguimiento().subscribe({
      next: data => {
        this.seguimiento = data;
        this.cargando = false;
        setTimeout(() => this.actualizarMapa(), 0);
      },
      error: err => {
        this.cargando = false;
        if (!this.seguimiento) {
          this.error = err?.error?.message || 'No se pudo obtener la ubicación del furgón escolar.';
        }
      }
    });
  }

  get hayDatosMapa(): boolean {
    return !!this.seguimiento && (
      this.seguimiento.ubicacion.latitud != null
      || !!this.seguimiento.ruta.puntos_recorrido?.length
    );
  }

  volver(): void {
    this.location.back();
  }

  contactarConductor(): void {
    const telefono = this.seguimiento?.conductor.telefono;
    if (telefono) window.location.href = `tel:${telefono}`;
  }

  private actualizarMapa(): void {
    if (!this.seguimiento || !this.hayDatosMapa) return;
    const contenedor = document.getElementById('mapa-seguimiento-delegado');
    if (!contenedor) return;
    const puntos = (this.seguimiento.ruta.puntos_recorrido || [])
      .map(p => ({ ...p, latitud: Number(p.latitud), longitud: Number(p.longitud) }))
      .filter(p => Number.isFinite(p.latitud) && Number.isFinite(p.longitud));
    const ubicacion = this.seguimiento.ubicacion;
    const tieneGps = ubicacion.latitud != null && ubicacion.longitud != null;
    const centro: L.LatLngExpression = tieneGps
      ? [ubicacion.latitud!, ubicacion.longitud!]
      : [puntos[0].latitud, puntos[0].longitud];

    if (!this.mapa) {
      this.mapa = L.map(contenedor).setView(centro, 14);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 20,
        attribution: '&copy; colaboradores de OpenStreetMap'
      }).addTo(this.mapa);
      setTimeout(() => this.mapa?.invalidateSize(), 100);
    }

    if (tieneGps) {
      const posicion: L.LatLngExpression = [ubicacion.latitud!, ubicacion.longitud!];
      if (this.marcadorFurgon) {
        this.marcadorFurgon.setLatLng(posicion);
      } else {
        const icono = L.divIcon({
          className: 'delegate-map-pin delegate-bus-pin',
          html: '<span>🚌</span>', iconSize: [38, 38], iconAnchor: [19, 19]
        });
        this.marcadorFurgon = L.marker(posicion, { icon: icono }).addTo(this.mapa);
      }
    }

    const enCamino = this.seguimiento.ruta.estado === 'en_camino';
    // En curso: lo que le falta al furgón. Antes de partir: el recorrido completo como vista previa.
    const destinos: PuntoTrazado[] = enCamino
      ? (this.seguimiento.ruta.puntos_trazado || [])
        .map(p => ({ latitud: Number(p.latitud), longitud: Number(p.longitud) }))
        .filter(p => Number.isFinite(p.latitud) && Number.isFinite(p.longitud))
      : puntos;
    const furgon = tieneGps && enCamino
      ? { latitud: ubicacion.latitud!, longitud: ubicacion.longitud!, precision: ubicacion.precision_metros }
      : null;
    this.seguidor.actualizar(this.mapa, destinos, furgon, () => this.ajustarMapa());

    const firma = puntos.map(p => `${p.tipo}:${p.id}:${p.latitud}:${p.longitud}`).join('|');
    if (!puntos.length || firma === this.firmaRecorrido) return;
    this.firmaRecorrido = firma;
    this.marcadores.forEach(m => m.remove());
    this.marcadores = puntos.map((punto, index) => {
      const colegio = punto.tipo !== 'estudiante';
      const icono = L.divIcon({
        className: colegio ? 'delegate-map-pin delegate-school-pin' : 'delegate-map-pin',
        html: `<span>${colegio ? '🏫' : index + 1}</span>`,
        iconSize: [32, 32], iconAnchor: [16, 32]
      });
      return L.marker([punto.latitud, punto.longitud], { icon: icono }).addTo(this.mapa!);
    });
  }

  private ajustarMapa(): void {
    if (!this.mapa) return;
    const capas: L.Layer[] = [
      ...this.marcadores,
      ...(this.seguidor.capaLinea ? [this.seguidor.capaLinea] : []),
      ...(this.marcadorFurgon ? [this.marcadorFurgon] : [])
    ];
    if (capas.length) this.mapa.fitBounds(L.featureGroup(capas).getBounds().pad(0.15));
  }

  private detenerActualizacion(): void {
    if (this.actualizacionTimer) clearInterval(this.actualizacionTimer);
    this.actualizacionTimer = undefined;
    this.seguimientoSub?.unsubscribe();
  }

  private destruirMapa(): void {
    this.seguidor.destruir();
    this.mapa?.remove();
    this.mapa = undefined;
    this.marcadorFurgon = undefined;
    this.marcadores = [];
    this.firmaRecorrido = '';
  }

  ngOnDestroy(): void {
    this.detenerActualizacion();
    this.destruirMapa();
  }
}
