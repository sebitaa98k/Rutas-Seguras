import { ChangeDetectorRef, Component, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import * as L from 'leaflet';

import {
  IonContent,
  IonIcon,
  IonMenuToggle,
  IonToast,
  IonSpinner,
AlertController
} from '@ionic/angular/standalone';

import { Observable } from 'rxjs';
import { addIcons } from 'ionicons';
import {
  menuOutline,
  busOutline,
  locationOutline,
  locateOutline,
  personOutline,
  checkmarkCircleOutline,
  scanOutline,
  warningOutline,
  flagOutline,
  checkmarkDoneCircleOutline,
  shieldCheckmarkOutline,
  playCircleOutline,
  personRemoveOutline,
  schoolOutline,
  notificationsOutline,
  callOutline,
  qrCodeOutline
} from 'ionicons/icons';

import { NotificationService } from '../../../services/notification.service';
import { GeocodingService, PuntoRuta } from '../../../services/geocoding.service';
import {
  Coordenada,
  avanzarSobreTrazado,
  distanciaHastaParada,
  distanciaMetros,
  trazadoRestante,
  ubicarConRespaldo,
  ubicarEnTrazado
} from '../../../utils/trazado.util';

/** Distancia al trazado desde la que se considera que el furgón tomó otro camino. */
const DESVIO_MAXIMO_METROS = 50;
/** Lecturas del GPS menos precisas que esto no cuentan como desvío. */
const PRECISION_GPS_MAXIMA_METROS = 40;
/** Evita pedir trazados nuevos seguidos al servicio de rutas. */
const ESPERA_ENTRE_RECALCULOS_MS = 15000;
/** Cuánto se espera la ubicación antes de dibujar el mapa al abrir la pantalla. */
const ESPERA_UBICACION_MS = 3000;

// Simulador de ruta (solo en modo demostración).
/** Cada cuánto avanza el furgón simulado. */
const PASO_SIMULACION_MS = 500;
/** Velocidad a x1: 10 m/s, unos 36 km/h. */
const VELOCIDAD_SIMULACION_MS = 10;
/**
 * El furgón simulado se detiene justo en la parada, y se considera que está en ella a esta distancia.
 * La llegada se mide por el camino (ver `distanciaHastaParada`), no en línea recta.
 */
const LLEGADA_PARADA_METROS = 5;
/** Cada cuánto se envía la posición simulada al servidor. */
const ENVIO_SIMULACION_MS = 3000;
/** Precisión con que se informa la posición simulada: es exacta. */
const PRECISION_SIMULADA_METROS = 5;
/** Cada cuánto se envía la posición al servidor, aunque el furgón no se mueva (antes 10 s: el apoderado lo veía atrasado). */
const INTERVALO_ENVIO_POSICION_MS = 5000;

addIcons({
  menuOutline,
  busOutline,
  locationOutline,
  locateOutline,
  personOutline,
  checkmarkCircleOutline,
  scanOutline,
  warningOutline,
  flagOutline,
  checkmarkDoneCircleOutline,
  shieldCheckmarkOutline,
  playCircleOutline,
  personRemoveOutline,
  schoolOutline,
  notificationsOutline,
  callOutline,
  qrCodeOutline
});

export interface ParadaRuta {
  id: number;
  numero: number;
  estudiante: string;
  colegioOCurso: string;
  direccion: string;
  /** Apoderado, personas autorizadas e inspector, cada uno con su rol. */
  contactos: { rol: string; nombre: string }[];
  estado: 'actual' | 'pendiente' | 'completada' | 'ausente' | 'entregado' | 'no_asiste' | 'no_recibido';
  /** Se llamó a su contacto cuando era la parada actual: habilita "No se recibió". */
  llamado: boolean;
  /** Ya subió al furgón (en la vuelta sigue pendiente hasta entregarlo en casa). */
  abordo: boolean;
  /** Su apoderado no autorizó la biometría (o no tiene rostro registrado): se valida con QR o el inspector. */
  soloQr: boolean;
  latitud: number;
  longitud: number;
}

interface ContactoLlamada {
  id: string;
  rol: string;
  nombre: string;
  telefono: string;
}

interface PuntoRecorridoApi {
  tipo: 'estudiante' | 'sede' | 'colegio';
  id: number;
  nombre: string;
  direccion: string;
  latitud: number | string;
  longitud: number | string;
}

interface RutaConductor {
  id: number;
  nombre: string;
  estado: 'activa' | 'en_ruta' | 'finalizada' | 'inactiva';
  iniciada_en?: string | null;
  finalizada_en?: string | null;
  reparto_iniciado_en?: string | null;
  origen_recalculo_latitud?: number | null;
  origen_recalculo_longitud?: number | null;
  sentido: 'hacia_colegio' | 'desde_colegio';
  /** Solo en modo demostración: el recorrido se simula sin moverse. */
  simulacion_activa?: boolean;
  colegio_nombre?: string;
  sede_nombre?: string;
  furgon_patente?: string;
  puntos_recorrido: PuntoRecorridoApi[];
  paradas: Array<{
    estudiante_id: number;
    estudiante_nombre: string;
    direccion: string;
    latitud: number | string;
    longitud: number | string;
    curso?: string;
    personas_autorizadas?: { nombre: string; rut: string }[];
    inspectores?: string[];
    apoderado_nombre?: string;
    completada?: boolean;
    estado?: 'pendiente' | 'completada' | 'ausente' | 'entregado' | 'no_asiste';
    abordo?: boolean;
    entregado?: boolean;
    no_recibido?: boolean;
    llamado?: boolean;
    /** Aviso del apoderado: hoy no usa el furgón en este tramo. */
    no_asiste?: boolean;
    solo_qr?: boolean;
  }>;
}

@Component({
  selector: 'app-ruta-activa',
  templateUrl: './ruta-activa.page.html',
  styleUrls: ['./ruta-activa.page.scss'],
  standalone: true,
  imports: [CommonModule, IonContent, IonIcon, IonMenuToggle, IonToast, IonSpinner]
})
export class RutaActivaPage implements OnDestroy {
  ruta?: RutaConductor;
  paradas: ParadaRuta[] = [];
  cargandoParadas = true;
  paradaActualIndex = 0;
  segundosTranscurridos = 0;
  rutaIniciada = false;
  iniciandoRuta = false;
  finalizandoRuta = false;
  /**
   * Aviso fijo cuando el teléfono no entrega la ubicación (permiso denegado o GPS apagado).
   * Antes era un mensaje flotante de 2 segundos que el conductor podía no ver (prueba de uso PERM-A).
   */
  avisoUbicacion: string | null = null;
  avisandoLlegada = false;
  marcandoAusente = false;
  iniciandoReparto = false;
  /** Último aviso de abordaje ("Juan subió. Siguiente: Pepito."), visible sobre la próxima parada. */
  avisoAbordaje = '';
  avisoFueraDeDomicilio = false;

  mostrarToast = false;
  mensajeToast = '';
  colorToast = 'success';

  distanciaRutaKm?: number;
  duracionRutaMin?: number;

  private intervalTimer: ReturnType<typeof setInterval> | null = null;
  private inicioRutaMs: number | null = null;
  private mapa?: L.Map;
  private capaRuta?: L.Polyline;
  /** Trazado completo por calles; en pantalla solo se muestra lo que falta recorrer. */
  private trazadoCompleto: Coordenada[] = [];
  private indiceTrazado = 0;
  /** Paradas que siguen después del furgón, para recalcular el trazado si se desvía. */
  private destinosTrazado: PuntoRuta[] = [];
  private recalculandoTrazado = false;
  /** El mapa se dibujó antes de conocer la ubicación: la línea debe rehacerse desde el furgón. */
  private trazadoSinGps = false;
  private ultimoRecalculoMs = 0;
  private marcadores: L.Layer[] = [];
  private marcadorFurgon?: L.Marker;
  private gpsWatchId?: number;
  private ultimoEnvioGpsMs = 0;
  /** Reenvía la posición aunque el furgón no se mueva: el servidor la usa para la regla de los 100 m. */
  private envioPeriodicoTimer: ReturnType<typeof setInterval> | null = null;
  private ultimaPosicionGps?: { latitud: number; longitud: number; precision?: number };
  /** Simulador: el furgón avanza solo por la línea y se detiene en cada parada. */
  simulando = false;
  velocidadSimulacion = 1;
  readonly velocidadesSimulacion = [1, 5, 10];
  private simulacionTimer: ReturnType<typeof setInterval> | null = null;
  private ultimoEnvioSimuladoMs = 0;
  /** Consulta periódica de la ruta: avisos de inasistencia y cambios de orden. */
  private consultaRutaTimer: ReturnType<typeof setInterval> | null = null;

  constructor(
    private router: Router,
    private notificationService: NotificationService,
    private geocodingService: GeocodingService,
    private cdr: ChangeDetectorRef,
    private alertController: AlertController
  ) {}

  // Ionic conserva las pestañas montadas: recargar cada vez que se vuelve.
  ionViewWillEnter(): void {
    // El escaneo facial/QR vuelve con el resultado del abordaje para mostrarlo aquí.
    const estado = this.router.getCurrentNavigation()?.extras.state || history.state || {};
    if (estado.avisoAbordaje) {
      this.avisoAbordaje = estado.avisoAbordaje;
      this.avisoFueraDeDomicilio = !!estado.fueraDeDomicilio;
      history.replaceState({ ...estado, avisoAbordaje: undefined, fueraDeDomicilio: undefined }, '');
    }
    this.cargarRutaAsignada();
  }

  /** En la ida las paradas se completan al subir el estudiante (rostro o QR). */
  get esIda(): boolean {
    return this.ruta?.sentido === 'hacia_colegio';
  }

  /** Vuelta antes de tocar "Iniciar reparto". */
  get vueltaSinReparto(): boolean {
    return !this.esIda && !this.ruta?.reparto_iniciado_en;
  }

  get faseSubida(): boolean {
    return this.rutaIniciada && this.vueltaSinReparto;
  }

  private estaPorEntregar(parada: ParadaRuta): boolean {
    return parada.estado === 'pendiente' || parada.estado === 'actual';
  }

  get aBordoCount(): number {
    return this.paradas.filter(p => p.abordo && this.estaPorEntregar(p)).length;
  }

  get noSubieronCount(): number {
    return this.paradas.filter(p => p.estado === 'ausente').length;
  }

  get faltanPorSubirCount(): number {
    return this.paradas.filter(p => !p.abordo && this.estaPorEntregar(p)).length;
  }

  get puedeIniciarReparto(): boolean {
    return this.faseSubida && !this.iniciandoReparto && this.faltanPorSubirCount === 0 && this.aBordoCount > 0;
  }

  get noRecibidosCount(): number {
    return this.paradas.filter(p => p.estado === 'no_recibido').length;
  }

  /** Reparto terminado en las casas: quedan niños que nadie recibió y vuelven al colegio. */
  get volviendoAlColegio(): boolean {
    return !this.esIda && this.rutaIniciada && !this.vueltaSinReparto && !this.paradaActual && this.noRecibidosCount > 0;
  }

  get destinoNombre(): string {
    return this.ruta?.sede_nombre || this.ruta?.colegio_nombre || 'el colegio';
  }

  ngOnDestroy(): void {
    this.pausarSimulacion();
    this.detenerTimer();
    this.detenerSeguimientoGps();
    this.detenerConsultaRuta();
    this.destruirMapa();
  }

  ionViewWillLeave(): void {
    this.pausarSimulacion();
    this.detenerTimer();
    this.detenerSeguimientoGps();
    this.detenerConsultaRuta();
    this.destruirMapa();
  }

  ionViewDidEnter(): void {
    this.iniciarConsultaRuta();
  }

  /** Cada 15 s revisa si un apoderado avisó inasistencia (o la revirtió) y si cambió el orden. */
  private iniciarConsultaRuta(): void {
    this.detenerConsultaRuta();
    this.consultaRutaTimer = setInterval(() => this.refrescarRuta(), 15000);
  }

  private detenerConsultaRuta(): void {
    if (this.consultaRutaTimer) {
      clearInterval(this.consultaRutaTimer);
      this.consultaRutaTimer = null;
    }
  }

  cargarRutaAsignada(): void {
    this.cargandoParadas = true;
    this.notificationService.obtenerMiRuta().subscribe({
      next: (ruta: RutaConductor) => {
        this.ruta = ruta;
        this.rutaIniciada = ruta.estado === 'en_ruta';
        this.aplicarParadas(ruta);
        this.cargandoParadas = false;

        if (this.rutaIniciada) {
          this.iniciarTimer(ruta.iniciada_en);
          this.iniciarSeguimientoGps();
        } else {
          this.detenerTimer();
          this.detenerSeguimientoGps();
          this.inicioRutaMs = null;
          this.segundosTranscurridos = 0;
          this.destruirMapa();
        }
        this.cdr.detectChanges();
        if (this.rutaIniciada) {
          // Así la línea parte en el furgón desde el primer dibujo, sin el salto al recargar.
          void this.esperarUbicacion().then(() => {
            // El servidor conoce la posición desde el primer momento, no recién al moverse.
            this.publicarPosicion(true);
            this.mostrarMapaRuta();
          });
        }
      },
      error: err => {
        this.cargandoParadas = false;
        this.lanzarToast(err?.error?.message || 'No se pudo cargar tu ruta asignada.', 'danger');
      }
    });
  }

  /** El backend entrega las paradas pendientes ya ordenadas por cercanía desde el furgón. */
  private aplicarParadas(ruta: RutaConductor): void {
    this.paradas = (ruta.paradas || []).map((e, index) => ({
      id: e.estudiante_id,
      numero: index + 1,
      estudiante: e.estudiante_nombre,
      colegioOCurso: `${e.curso || ''}${ruta.colegio_nombre ? ' · ' + ruta.colegio_nombre : ''}`,
      direccion: e.direccion,
      contactos: [
        ...(e.apoderado_nombre ? [{ rol: 'Apoderado', nombre: e.apoderado_nombre }] : []),
        ...(e.personas_autorizadas || []).map(p => ({ rol: 'Persona autorizada', nombre: p.nombre })),
        ...(e.inspectores || []).map(nombre => ({ rol: 'Inspector/a', nombre })),
      ],
      llamado: !!e.llamado,
      estado: e.estado === 'entregado'
        ? 'entregado'
        : e.no_recibido
        ? 'no_recibido'
        : (e.estado === 'ausente'
          ? 'ausente'
          : (e.completada ? 'completada' : (e.estado === 'no_asiste' ? 'no_asiste' : 'pendiente'))),
      abordo: !!e.abordo,
      soloQr: !!e.solo_qr,
      latitud: Number(e.latitud),
      longitud: Number(e.longitud)
    }));
    // En la vuelta suben en cualquier orden: la parada actual existe recién durante el reparto.
    if (ruta.sentido === 'desde_colegio' && !ruta.reparto_iniciado_en) {
      this.paradaActualIndex = this.paradas.length;
      return;
    }
    this.paradaActualIndex = this.paradas.findIndex(parada => parada.estado === 'pendiente');
    if (this.paradaActualIndex < 0) {
      this.paradaActualIndex = this.paradas.length;
    } else {
      this.paradas[this.paradaActualIndex].estado = 'actual';
    }
  }

  /**
   * Consulta la ruta sin recargar la pantalla. Detecta:
   * - avisos de inasistencia de apoderados (o su anulación), aunque la ruta esté en curso;
   * - cambios en el orden óptimo a medida que el furgón avanza.
   * Solo redibuja si algo cambió.
   */
  private refrescarRuta(): void {
    const ocupado = this.cargandoParadas || this.iniciandoRuta || this.finalizandoRuta
      || this.avisandoLlegada || this.marcandoAusente;
    if (!this.ruta || ocupado) return;

    this.notificationService.obtenerMiRuta().subscribe({
      next: (ruta: RutaConductor) => {
        const anterior = this.ruta;
        if (!anterior || ruta.id !== anterior.id || ruta.estado !== anterior.estado) {
          // La ruta cambió desde otro lado (inició, finalizó o se reasignó): recarga completa.
          this.cargarRutaAsignada();
          return;
        }

        const avisos = this.cambiosDeAsistencia(anterior, ruta);
        const firma = (r: RutaConductor) =>
          (r.paradas || []).filter(p => p.estado === 'pendiente').map(p => p.estudiante_id).join(',');
        const cambioOrden = firma(ruta) !== firma(anterior);
        const actualAntes = this.paradaActual?.id;
        this.ruta = ruta;
        if (!cambioOrden && !avisos.length) return;

        this.aplicarParadas(ruta);
        this.cdr.detectChanges();
        if (this.rutaIniciada) {
          setTimeout(() => this.mostrarMapaRuta(), 0);
        }

        if (avisos.length) {
          const siguiente = this.paradaActual
            ? `Siguiente: ${this.paradaActual.estudiante}.`
            : (this.rutaIniciada && this.esIda ? 'Dirigiéndose al colegio.' : '');
          this.avisoAbordaje = `${avisos.join(' ')} ${siguiente}`.trim();
          this.avisoFueraDeDomicilio = true;
          this.lanzarToast(avisos.join(' '), 'warning');
        } else if (this.rutaIniciada && this.paradaActual && this.paradaActual.id !== actualAntes) {
          this.lanzarToast(`Recorrido reordenado: ahora el más cercano es ${this.paradaActual.estudiante}.`, 'success');
        }
      },
      error: err => console.error('No se pudo actualizar la ruta:', err)
    });
  }

  private cambiosDeAsistencia(anterior: RutaConductor, actual: RutaConductor): string[] {
    const estadoAnterior = new Map((anterior.paradas || []).map(p => [p.estudiante_id, p.estado]));
    const avisos: string[] = [];
    for (const parada of actual.paradas || []) {
      const antes = estadoAnterior.get(parada.estudiante_id);
      if (parada.estado === 'no_asiste' && antes !== 'no_asiste') {
        avisos.push(`⚠️ ${parada.estudiante_nombre} no asistirá hoy (aviso del apoderado).`);
      } else if (antes === 'no_asiste' && parada.estado === 'pendiente') {
        avisos.push(`${parada.estudiante_nombre} sí asistirá: volvió al recorrido.`);
      }
    }
    return avisos;
  }

  /**
   * Primera ubicación antes de dibujar el mapa, esperando como máximo ESPERA_UBICACION_MS.
   * Si no llega a tiempo se dibuja igual y la línea se corrige cuando llegue.
   */
  private esperarUbicacion(): Promise<void> {
    // También en la simulación: el furgón simulado parte desde donde está el teléfono.
    if (this.ultimaPosicionGps || !navigator.geolocation) return Promise.resolve();
    return new Promise(resolve => {
      navigator.geolocation.getCurrentPosition(
        posicion => {
          this.ultimaPosicionGps ??= {
            latitud: posicion.coords.latitude,
            longitud: posicion.coords.longitude,
            precision: posicion.coords.accuracy
          };
          resolve();
        },
        () => resolve(),
        { enableHighAccuracy: true, timeout: ESPERA_UBICACION_MS, maximumAge: 30000 }
      );
    });
  }

  /** Posición actual para que el recorrido se ordene desde el inicio (máx. 5 s de espera). */
  private obtenerPosicionInicial(): Promise<{ latitud: number; longitud: number } | undefined> {
    if (this.ultimaPosicionGps) {
      return Promise.resolve({ latitud: this.ultimaPosicionGps.latitud, longitud: this.ultimaPosicionGps.longitud });
    }
    if (!navigator.geolocation) return Promise.resolve(undefined);
    return new Promise(resolve => {
      navigator.geolocation.getCurrentPosition(
        posicion => resolve({ latitud: posicion.coords.latitude, longitud: posicion.coords.longitude }),
        () => resolve(undefined),
        { enableHighAccuracy: true, timeout: 5000, maximumAge: 30000 }
      );
    });
  }

  async iniciarRecorrido(): Promise<void> {
    if (!this.ruta?.id || this.iniciandoRuta || this.rutaIniciada) return;

    this.iniciandoRuta = true;
    const posicion = await this.obtenerPosicionInicial();
    this.notificationService.iniciarRuta(this.ruta.id, posicion).subscribe({
      next: res => {
        this.iniciandoRuta = false;
        if (res?.ruta?.estado !== 'en_ruta') {
          this.lanzarToast('El servidor no confirmó el inicio de la ruta.', 'warning');
        } else {
          this.lanzarToast(res?.message || 'Ruta iniciada exitosamente.', 'success');
        }
        // Recarga paradas (ya ordenadas desde la posición del furgón), mapa, timer y GPS.
        this.cargarRutaAsignada();
      },
      error: err => {
        this.iniciandoRuta = false;
        this.lanzarToast(err?.error?.message || 'No se pudo iniciar la ruta.', 'danger');
      }
    });
  }

  private mostrarMapaRuta(): void {
    if (!this.rutaIniciada || !this.ruta?.puntos_recorrido?.length) return;

    this.destruirMapa();
    const contenedor = document.getElementById('mapa-ruta-conductor');
    if (!contenedor) return;

    const puntosExactos = this.ruta.puntos_recorrido.map(p => ({
      ...p,
      latitud: Number(p.latitud),
      longitud: Number(p.longitud)
    }));

    this.mapa = L.map(contenedor).setView(
      [puntosExactos[0].latitud, puntosExactos[0].longitud],
      14
    );

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 20,
      attribution: '&copy; colaboradores de OpenStreetMap'
    }).addTo(this.mapa);

    // Los pines de estudiantes se numeran igual que la lista de paradas (sin contar el colegio);
    // las paradas ya resueltas (subió, entregado, ausente) muestran ✓ en vez del número.
    const paradaPorId = new Map(this.paradas.map(parada => [parada.id, parada]));
    puntosExactos.forEach(punto => {
      const esSede = punto.tipo === 'sede' || punto.tipo === 'colegio';
      const parada = esSede ? undefined : paradaPorId.get(punto.id);
      const resuelta = !!parada && this.paradaResuelta(parada);
      const icono = L.divIcon({
        className: esSede ? 'route-pin school-pin' : `route-pin student-pin${resuelta ? ' done-pin' : ''}`,
        // El pin va girado para formar su punta: el <b> endereza el contenido.
        html: `<span>${esSede ? '🏫' : `<b>${resuelta ? '✓' : (parada?.numero ?? '•')}</b>`}</span>`,
        iconSize: [34, 34],
        iconAnchor: [17, 34]
      });
      const marcador = L.marker([punto.latitud, punto.longitud], { icon: icono })
        .bindPopup(`<strong>${punto.nombre}</strong><br>${punto.direccion}`)
        .addTo(this.mapa!);
      this.marcadores.push(marcador);
    });

    const resueltas = this.paradas.filter(parada => this.paradaResuelta(parada));
    const completadas = new Set(resueltas.map(parada => parada.id));
    const alumnosPendientes = puntosExactos.filter(
      punto => punto.tipo === 'estudiante' && !completadas.has(punto.id)
    );
    const establecimiento = puntosExactos.find(punto => punto.tipo !== 'estudiante');

    // La línea parte donde está el furgón; el orden de las paradas lo decide el servidor.
    let origen: { latitud: number; longitud: number } | undefined = this.ultimaPosicionGps;
    let destinos: Array<{ latitud: number; longitud: number }>;
    if (this.esIda) {
      // Ida: por las casas pendientes, hasta el colegio.
      destinos = [...alumnosPendientes, ...(establecimiento ? [establecimiento] : [])];
    } else {
      // Vuelta: por las casas en el orden de entrega. Quienes nadie recibió vuelven al colegio al final.
      const casas = alumnosPendientes.filter(punto => paradaPorId.get(punto.id)?.estado !== 'no_recibido');
      destinos = [...casas, ...(this.noRecibidosCount > 0 && establecimiento ? [establecimiento] : [])];
      if (!origen) {
        // Sin GPS: desde la última casa entregada o, antes de repartir, desde el colegio.
        const ultimaEntregada = resueltas.filter(parada => parada.estado === 'entregado').pop();
        origen = ultimaEntregada
          ? { latitud: ultimaEntregada.latitud, longitud: ultimaEntregada.longitud }
          : establecimiento;
      }
    }
    const puntosTrazado = [...(origen ? [origen] : []), ...destinos];
    this.trazadoSinGps = !this.ultimaPosicionGps;
    this.destinosTrazado = destinos.map(p => ({ latitud: p.latitud, longitud: p.longitud }));
    const puntos: PuntoRuta[] = puntosTrazado.map(p => ({
      latitud: p.latitud,
      longitud: p.longitud
    }));

    if (puntos.length < 2) {
      const bounds = L.latLngBounds(
        puntosExactos.map(p => [p.latitud, p.longitud] as [number, number])
      );
      this.mapa.fitBounds(bounds.pad(0.15));
      this.actualizarMarcadorFurgon(false);
      return;
    }

    this.geocodingService.trazarRuta(puntos).subscribe({
      next: respuesta => {
        if (!this.mapa) return;

        this.distanciaRutaKm = Math.round((respuesta.distanciaMetros / 1000) * 10) / 10;
        this.duracionRutaMin = Math.round(respuesta.duracionSegundos / 60);

        this.trazadoCompleto = respuesta.puntosRuta;
        this.indiceTrazado = 0;
        this.capaRuta = L.polyline(respuesta.puntosRuta, {
          weight: 5,
          opacity: 0.85
        }).addTo(this.mapa);

        // OSRM ajusta los puntos a calles transitables. El pin permanece en la
        // coordenada exacta confirmada por el apoderado y esta línea muestra el ajuste.
        (respuesta.puntosAjustados || []).forEach((ajustado, index) => {
          const exacto = puntosTrazado[index];
          if (!exacto || ajustado.distanciaAjusteMetros < 2) return;
          const conector = L.polyline(
            [
              [exacto.latitud, exacto.longitud],
              [ajustado.latitud, ajustado.longitud]
            ],
            { weight: 2, dashArray: '5,6', opacity: 0.55 }
          ).addTo(this.mapa!);
          this.marcadores.push(conector);
        });

        const bounds = L.latLngBounds(
          puntosExactos.map(p => [p.latitud, p.longitud] as [number, number])
        );
        this.mapa.fitBounds(bounds.pad(0.15));
      },
      error: err => {
        console.error('No se pudo calcular el trazado OSRM:', err);
        if (!this.mapa) return;
        const bounds = L.latLngBounds(
          puntosExactos.map(p => [p.latitud, p.longitud] as [number, number])
        );
        this.mapa.fitBounds(bounds.pad(0.15));
        this.lanzarToast('Se muestran las paradas, pero no fue posible calcular el trazado por calles.', 'warning');
      }
    });

    setTimeout(() => this.mapa?.invalidateSize(), 100);
    this.actualizarMarcadorFurgon(false);
  }

  centrarUbicacion(): void {
    if (!this.mapa || !navigator.geolocation) {
      this.lanzarToast('La ubicación del dispositivo no está disponible.', 'warning');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      posicion => {
        const lat = posicion.coords.latitude;
        const lng = posicion.coords.longitude;
        if (this.marcadorFurgon) {
          this.marcadorFurgon.setLatLng([lat, lng]);
        } else {
          const icono = L.divIcon({
            className: 'route-pin van-pin',
            html: '<span>🚌</span>',
            iconSize: [38, 38],
            iconAnchor: [19, 19]
          });
          this.marcadorFurgon = L.marker([lat, lng], { icon: icono }).addTo(this.mapa!);
        }
        this.mapa!.setView([lat, lng], 16);
      },
      () => this.lanzarToast('No se pudo obtener tu ubicación actual.', 'warning'),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }

  /**
   * Solo avisa al apoderado de ese niño. Ida: llegó a buscarlo (la parada se completa al subir).
   * Vuelta: llegó a dejarlo (se completa al validar la entrega con rostro o QR).
   */
  avisarLlegada(): void {
    const actual = this.paradaActual;
    if (!this.ruta?.id || !actual || this.avisandoLlegada) return;
    if (!this.esIda && this.accionVuelta(actual) !== 'entregar') return;

    this.avisandoLlegada = true;
    this.notificationService.avisarLlegada(this.ruta.id, actual.id).subscribe({
      next: respuesta => {
        this.avisandoLlegada = false;
        this.lanzarToast(respuesta?.message || `Se avisó la llegada de ${actual.estudiante}.`, 'success');
      },
      error: err => {
        this.avisandoLlegada = false;
        this.lanzarToast(err?.error?.message || 'No se pudo enviar el aviso.', 'danger');
      }
    });
  }

  finalizarRuta(): void {
    if (!this.ruta?.id || !this.rutaIniciada || this.finalizandoRuta) {
      this.lanzarToast('Primero debes iniciar la ruta.', 'warning');
      return;
    }

    this.finalizandoRuta = true;
    this.notificationService.finalizarRuta(this.ruta.id).subscribe({
      next: res => {
        this.finalizandoRuta = false;
        this.detenerTimer();
        this.detenerSeguimientoGps();
        this.rutaIniciada = false;
        if (this.ruta) {
          this.ruta.estado = 'finalizada';
          this.ruta.finalizada_en = res?.ruta?.finalizada_en || new Date().toISOString();
        }
        this.destruirMapa();
        this.cdr.markForCheck();
        this.mostrarRutaTerminada(res?.message || 'La ruta terminó correctamente.');
      },
      error: err => {
        this.finalizandoRuta = false;
        if (err?.error?.requiere_recepcion_institucional) {
          this.lanzarToast(err.error.message, 'warning');
          this.router.navigate(['/conductor/escanear-qr'], {
            queryParams: {
              recepcion_institucional: 1,
              finalizar_ruta: 1,
              ruta_id: err.error.ruta_id || this.ruta?.id
            }
          });
          return;
        }
        this.lanzarToast(err?.error?.message || 'No se pudo finalizar la ruta.', 'danger');
      }
    });
  }

  /** Aviso que no se pierde como un toast: el conductor lo cierra y vuelve al inicio. */
  private async mostrarRutaTerminada(mensaje: string): Promise<void> {
    const alerta = await this.alertController.create({
      header: 'Ruta terminada',
      message: mensaje,
      backdropDismiss: false,
      buttons: [{ text: 'Volver al inicio', role: 'confirm' }]
    });
    await alerta.present();
    await alerta.onDidDismiss();
    this.router.navigate(['/conductor/inicio']);
  }

  get paradaActual(): ParadaRuta | null {
    return this.paradaActualIndex < this.paradas.length
      ? this.paradas[this.paradaActualIndex]
      : null;
  }

  /** "03", "12": número de parada con dos dígitos. */
  numeroDosDigitos(numero: number): string {
    return String(numero).padStart(2, '0');
  }

  get completadasCount(): number {
    return this.paradas.filter(p => this.paradaResuelta(p)).length;
  }

  private paradaResuelta(parada: ParadaRuta): boolean {
    return parada.estado === 'completada'
      || parada.estado === 'ausente'
      || parada.estado === 'entregado'
      || parada.estado === 'no_asiste';
  }

  marcarAusente(parada?: ParadaRuta): void {
    const actual = parada || this.paradaActual;
    if (!this.ruta?.id || !actual || this.marcandoAusente) return;
    const pregunta = this.esIda
      ? `¿${actual.estudiante} no se presentó? Se avisará a su apoderado y se pasará a la siguiente parada.`
      : `¿${actual.estudiante} no subió? Se avisará a su apoderado.`;
    if (!confirm(pregunta)) {
      return;
    }

    this.marcandoAusente = true;
    this.notificationService.marcarAusente(this.ruta.id, actual.id).subscribe({
      next: res => {
        this.marcandoAusente = false;
        this.avisoAbordaje = res?.message || `${actual.estudiante} marcado como ausente.`;
        this.avisoFueraDeDomicilio = false;
        this.cargarRutaAsignada();
      },
      error: err => {
        this.marcandoAusente = false;
        this.lanzarToast(err?.error?.message || 'No se pudo marcar la ausencia.', 'danger');
      }
    });
  }

  /** Muestra los contactos del niño; siempre se pregunta antes de marcar. */
  llamar(parada: ParadaRuta): void {
    if (!this.ruta?.id) return;
    const rutaId = this.ruta.id;
    this.notificationService.contactosEstudiante(rutaId, parada.id).subscribe({
      next: async res => {
        const contactos: ContactoLlamada[] = res?.contactos || [];
        if (!contactos.length) {
          this.lanzarToast('Este estudiante no tiene contactos registrados.', 'warning');
          return;
        }
        const alerta = await this.alertController.create({
          header: `Llamar por ${parada.estudiante}`,
          inputs: contactos.map(contacto => ({
            type: 'radio' as const,
            label: `${contacto.rol}: ${contacto.nombre}${contacto.telefono ? '' : ' (sin teléfono)'}`,
            value: contacto,
            disabled: !contacto.telefono
          })),
          buttons: [
            { text: 'Cancelar', role: 'cancel' },
            {
              text: 'Llamar',
              handler: (contacto?: ContactoLlamada) => {
                if (!contacto) return false;
                this.confirmarLlamada(rutaId, parada, contacto);
                return true;
              }
            }
          ]
        });
        await alerta.present();
      },
      error: err => this.lanzarToast(err?.error?.message || 'No se pudieron cargar los contactos.', 'danger')
    });
  }

  private confirmarLlamada(rutaId: number, parada: ParadaRuta, contacto: ContactoLlamada): void {
    if (!confirm(`¿Quieres marcar a ${contacto.nombre} (${contacto.rol})?`)) return;
    const marcar = () => { window.location.href = `tel:${contacto.telefono.replace(/[^\d+]/g, '')}`; };
    this.notificationService.registrarLlamada(rutaId, parada.id, contacto.id).subscribe({
      next: () => {
        this.cargarRutaAsignada();
        marcar();
      },
      error: err => {
        this.lanzarToast(err?.error?.message || 'La llamada no quedó registrada.', 'warning');
        marcar();
      }
    });
  }

  noSeRecibio(): void {
    const actual = this.paradaActual;
    if (!this.ruta?.id || !actual?.llamado || this.marcandoAusente) return;
    if (!confirm(`¿Confirmas que nadie recibió a ${actual.estudiante}? Se avisará a su apoderado y volverá al colegio al final del recorrido.`)) return;
    this.ejecutarAccionReparto(this.notificationService.marcarNoRecibido(this.ruta.id, actual.id));
  }

  apoderadoDisponible(parada: ParadaRuta): void {
    if (!this.ruta?.id || this.marcandoAusente) return;
    if (!confirm(`¿El apoderado de ${parada.estudiante} ya está disponible? Su casa vuelve al recorrido.`)) return;
    this.ejecutarAccionReparto(this.notificationService.marcarApoderadoDisponible(this.ruta.id, parada.id));
  }

  private ejecutarAccionReparto(accion: Observable<any>): void {
    this.marcandoAusente = true;
    accion.subscribe({
      next: res => {
        this.marcandoAusente = false;
        this.avisoAbordaje = res?.message || '';
        this.avisoFueraDeDomicilio = false;
        this.cargarRutaAsignada();
      },
      error: err => {
        this.marcandoAusente = false;
        this.lanzarToast(err?.error?.message || 'No se pudo completar la acción.', 'danger');
      }
    });
  }

  iniciarReparto(): void {
    if (!this.ruta?.id || !this.puedeIniciarReparto) return;
    if (!confirm('¿Iniciar el reparto? Después de esto ya no podrá subir nadie más.')) return;

    this.iniciandoReparto = true;
    this.notificationService.iniciarReparto(this.ruta.id).subscribe({
      next: res => {
        this.iniciandoReparto = false;
        this.avisoAbordaje = res?.message || 'Reparto iniciado.';
        this.avisoFueraDeDomicilio = false;
        this.cargarRutaAsignada();
      },
      error: err => {
        this.iniciandoReparto = false;
        this.lanzarToast(err?.error?.message || 'No se pudo iniciar el reparto.', 'danger');
      }
    });
  }

  corregirAbordaje(parada: ParadaRuta): void {
    if (!this.ruta?.id || this.marcandoAusente) return;
    if (!confirm(`¿Corregir a ${parada.estudiante}? Quedará como "No subió" y se avisará a su apoderado.`)) return;

    this.marcandoAusente = true;
    this.notificationService.corregirAbordaje(this.ruta.id, parada.id).subscribe({
      next: res => {
        this.marcandoAusente = false;
        this.avisoAbordaje = res?.message || `${parada.estudiante} quedó como que no subió.`;
        this.avisoFueraDeDomicilio = false;
        this.cargarRutaAsignada();
      },
      error: err => {
        this.marcandoAusente = false;
        this.lanzarToast(err?.error?.message || 'No se pudo corregir la subida.', 'danger');
      }
    });
  }

  /** Una ruta sin estudiantes igual debe poder cerrarse. */
  get puedeFinalizar(): boolean {
    return this.rutaIniciada && !this.finalizandoRuta
      && this.paradas.every(p => this.paradaResuelta(p) || p.estado === 'no_recibido');
  }

  get todasCompletadas(): boolean {
    return this.paradas.length > 0 && this.completadasCount === this.paradas.length;
  }

  get tiempoFormateado(): string {
    const mins = Math.floor(this.segundosTranscurridos / 60);
    const secs = this.segundosTranscurridos % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  /** Qué corresponde en la vuelta: subirlo en el colegio o, ya a bordo, entregarlo en su casa. */
  accionVuelta(parada: ParadaRuta | null): 'abordar' | 'entregar' | null {
    if (!this.rutaIniciada || !parada || (parada.estado !== 'actual' && parada.estado !== 'pendiente')) return null;
    if (!parada.abordo) return 'abordar';
    return this.vueltaSinReparto ? null : 'entregar';
  }

  /** Vuelta: la cámara reconoce a quien tenga enfrente, sin elegir al estudiante antes. */
  escanearSubida(): void {
    if (!this.ruta?.id) return;
    this.router.navigate(['/conductor/escaneo-facial'], {
      queryParams: { ruta_id: this.ruta.id, modo: 'abordar', subida_general: 1 }
    });
  }

  irAEscaneoFacial(parada?: ParadaRuta | null): void {
    const seleccionada = parada || (!this.esIda ? this.paradaActual : null);
    if (!this.esIda && this.ruta?.id && seleccionada) {
      this.router.navigate(['/conductor/escaneo-facial'], {
        queryParams: {
          ruta_id: this.ruta.id,
          estudiante_id: seleccionada.id,
          estudiante_nombre: seleccionada.estudiante,
          modo: this.accionVuelta(seleccionada) === 'entregar' ? 'entregar' : 'abordar',
        }
      });
      return;
    }
    this.router.navigate(['/conductor/escaneo-facial']);
  }

  /**
   * Alternativa al rostro, siempre disponible: obligatoria para los niños cuyo apoderado no autorizó la
   * biometría, y útil cuando la cámara no reconoce. En la ida el QR del apoderado indica quién sube.
   */
  async irAEscanearQR(): Promise<void> {
    if (!this.ruta?.id || !this.rutaIniciada) return;
    if (this.esIda) {
      // Se escanea el QR del apoderado; el niño de la parada actual queda marcado de antemano.
      const actual = this.paradaActual;
      this.router.navigate(['/conductor/escanear-qr'], actual ? { queryParams: { estudiante_id: actual.id } } : {});
      return;
    }
    if (this.faseSubida) {
      await this.elegirQuienSubeConQR();
      return;
    }
    const parada = this.paradaActual;
    const accion = this.accionVuelta(parada);
    if (!parada || !accion) return;
    this.router.navigate(['/conductor/escanear-qr'], {
      queryParams: accion === 'entregar'
        ? { entrega_domicilio: 1, estudiante_id: parada.id }
        : { validacion_institucional: 1, ruta_id: this.ruta.id, estudiante_id: parada.id }
    });
  }

  get puedeUsarQR(): boolean {
    if (!this.rutaIniciada) return false;
    if (this.esIda) return !this.todasCompletadas;
    if (this.faseSubida) return this.faltanPorSubirCount > 0;
    return !!this.accionVuelta(this.paradaActual);
  }

  /** Vuelta, subida en el colegio: primero se indica quién sube y después se escanea el QR del inspector. */
  private async elegirQuienSubeConQR(): Promise<void> {
    const pendientes = this.paradas.filter(p => !p.abordo && this.estaPorEntregar(p));
    if (!pendientes.length || !this.ruta?.id) {
      this.lanzarToast('No quedan estudiantes por subir.', 'warning');
      return;
    }
    const rutaId = this.ruta.id;
    const alerta = await this.alertController.create({
      header: '¿Quién sube?',
      inputs: pendientes.map(parada => ({
        type: 'radio' as const,
        label: parada.soloQr ? `${parada.estudiante} (solo QR)` : parada.estudiante,
        value: parada.id
      })),
      buttons: [
        { text: 'Cancelar', role: 'cancel' },
        {
          text: 'Escanear QR',
          handler: (estudianteId: number) => {
            if (!estudianteId) return false;
            this.router.navigate(['/conductor/escanear-qr'], {
              queryParams: { validacion_institucional: 1, ruta_id: rutaId, estudiante_id: estudianteId }
            });
            return true;
          }
        }
      ]
    });
    await alerta.present();
  }

  irAEmergencia(): void {
    this.router.navigate(['/conductor/emergencia']);
  }

  private iniciarTimer(iniciadaEn?: string | null): void {
    this.detenerTimer();
    const desdeBackend = iniciadaEn ? Date.parse(iniciadaEn) : NaN;
    this.inicioRutaMs = Number.isFinite(desdeBackend) ? desdeBackend : Date.now();

    const actualizar = () => {
      this.segundosTranscurridos = Math.max(
        0,
        Math.floor((Date.now() - this.inicioRutaMs!) / 1000)
      );
      this.cdr.markForCheck();
    };

    actualizar();
    this.intervalTimer = setInterval(actualizar, 1000);
  }

  private detenerTimer(): void {
    if (this.intervalTimer) {
      clearInterval(this.intervalTimer);
      this.intervalTimer = null;
    }
  }

  private iniciarSeguimientoGps(): void {
    if (this.gpsWatchId !== undefined || !navigator.geolocation) {
      return;
    }

    this.gpsWatchId = navigator.geolocation.watchPosition(
      posicion => {
        if (this.simulacionDisponible) return;
        this.avisoUbicacion = null;
        this.ultimaPosicionGps = {
          latitud: posicion.coords.latitude,
          longitud: posicion.coords.longitude,
          precision: posicion.coords.accuracy
        };
        this.actualizarMarcadorFurgon(false);
        this.seguirTrazado();
        this.publicarPosicion();
      },
      error => {
        console.error('No se pudo leer la ubicación GPS:', error);
        // En el simulador la posición la entrega la app: no hace falta el GPS.
        if (this.simulacionDisponible) return;
        this.avisoUbicacion = error?.code === 1
          ? 'Ubicación desactivada: el apoderado no ve el furgón. Actívala en Ajustes > Aplicaciones > Rutas Seguras > Permisos > Ubicación.'
          : 'No se puede obtener tu ubicación: revisa que el GPS del teléfono esté encendido.';
        this.cdr.markForCheck();
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
    this.envioPeriodicoTimer = setInterval(() => this.publicarPosicion(true), INTERVALO_ENVIO_POSICION_MS);
  }

  /**
   * Envía la posición del furgón al servidor, como máximo cada INTERVALO_ENVIO_POSICION_MS.
   * `periodico`: el reenvío del temporizador, aunque el furgón no se haya movido.
   * En la simulación la posición es exacta, aunque el punto de partida viniera de un GPS impreciso.
   */
  private publicarPosicion(periodico = false): void {
    const gps = this.ultimaPosicionGps;
    const ahora = Date.now();
    if (!this.ruta?.id || !gps) return;
    if (!periodico && ahora - this.ultimoEnvioGpsMs < INTERVALO_ENVIO_POSICION_MS) return;
    this.ultimoEnvioGpsMs = ahora;
    const precision = this.simulacionDisponible ? PRECISION_SIMULADA_METROS : gps.precision;
    this.notificationService.actualizarUbicacionRuta(this.ruta.id, gps.latitud, gps.longitud, precision).subscribe({
      // El orden según la nueva posición lo recoge la consulta periódica de la ruta.
      error: err => console.error('No se pudo publicar la ubicación GPS:', err)
    });
  }

  private detenerSeguimientoGps(): void {
    if (this.gpsWatchId !== undefined && navigator.geolocation) {
      navigator.geolocation.clearWatch(this.gpsWatchId);
    }
    this.gpsWatchId = undefined;
    this.ultimoEnvioGpsMs = 0;
    if (this.envioPeriodicoTimer) clearInterval(this.envioPeriodicoTimer);
    this.envioPeriodicoTimer = null;
  }

  private actualizarMarcadorFurgon(centrar: boolean): void {
    if (!this.mapa || !this.ultimaPosicionGps) return;
    const punto: L.LatLngExpression = [
      this.ultimaPosicionGps.latitud,
      this.ultimaPosicionGps.longitud
    ];
    if (this.marcadorFurgon) {
      this.marcadorFurgon.setLatLng(punto);
    } else {
      const icono = L.divIcon({
        className: 'route-pin van-pin',
        html: '<span>🚌</span>',
        iconSize: [38, 38],
        iconAnchor: [19, 19]
      });
      this.marcadorFurgon = L.marker(punto, { icon: icono }).addTo(this.mapa);
    }
    if (centrar) {
      this.mapa.setView(punto, 16);
    }
  }

  /** Borra lo ya recorrido. Si el furgón se salió del camino, pide un trazado nuevo desde donde está. */
  private seguirTrazado(): void {
    const gps = this.ultimaPosicionGps;
    if (!this.mapa || !this.capaRuta || !gps || this.trazadoCompleto.length < 2) return;
    if (this.trazadoSinGps) {
      this.recalcularTrazado(true);
      return;
    }

    const posicion = ubicarConRespaldo(this.trazadoCompleto, [gps.latitud, gps.longitud], this.indiceTrazado, DESVIO_MAXIMO_METROS);
    if (!posicion) return;
    if (posicion.distancia > DESVIO_MAXIMO_METROS) {
      // Una lectura imprecisa del GPS no se considera un desvío.
      if ((gps.precision ?? 0) <= PRECISION_GPS_MAXIMA_METROS) {
        this.recalcularTrazado();
      }
      return;
    }
    this.indiceTrazado = posicion.indice;
    this.capaRuta.setLatLngs(trazadoRestante(this.trazadoCompleto, posicion));
  }

  /** `inicial`: primera ubicación tras dibujar sin GPS; no espera entre recálculos. */
  private recalcularTrazado(inicial = false): void {
    const gps = this.ultimaPosicionGps;
    const ahora = Date.now();
    if (
      !gps || !this.destinosTrazado.length || this.recalculandoTrazado
      || (!inicial && ahora - this.ultimoRecalculoMs < ESPERA_ENTRE_RECALCULOS_MS)
    ) {
      return;
    }
    this.recalculandoTrazado = true;
    this.ultimoRecalculoMs = ahora;
    const mapa = this.mapa;

    this.geocodingService.trazarRuta([{ latitud: gps.latitud, longitud: gps.longitud }, ...this.destinosTrazado]).subscribe({
      next: respuesta => {
        this.recalculandoTrazado = false;
        // Si el mapa se redibujó mientras tanto, ese dibujo ya trae su propio trazado.
        if (!this.capaRuta || this.mapa !== mapa) return;
        this.trazadoSinGps = false;
        this.trazadoCompleto = respuesta.puntosRuta;
        this.indiceTrazado = 0;
        this.capaRuta.setLatLngs(respuesta.puntosRuta);
        this.distanciaRutaKm = Math.round((respuesta.distanciaMetros / 1000) * 10) / 10;
        this.duracionRutaMin = Math.round(respuesta.duracionSegundos / 60);
        this.cdr.detectChanges();
      },
      error: err => {
        this.recalculandoTrazado = false;
        // Si falla, no se reintenta en cada lectura: queda la regla de desvío, con su espera.
        this.trazadoSinGps = false;
        console.error('No se pudo recalcular el trazado:', err);
      }
    });
  }

  // ===============================================
  // SIMULADOR DE RUTA (solo en modo demostración)
  // ===============================================

  /** El administrador activó la simulación de esta ruta y el recorrido está en curso. */
  get simulacionDisponible(): boolean {
    return !!this.ruta?.simulacion_activa && this.rutaIniciada;
  }

  alternarSimulacion(): void {
    if (this.simulando) {
      this.pausarSimulacion();
      return;
    }
    const parada = this.paradaEnLaQueEsta();
    if (parada) {
      this.lanzarToast(`Estás en ${parada}. Marca la subida o la entrega antes de seguir.`, 'warning');
      return;
    }
    this.simulando = true;
    this.simulacionTimer = setInterval(() => this.avanzarSimulacion(), PASO_SIMULACION_MS);
  }

  cambiarVelocidadSimulacion(velocidad: number): void {
    this.velocidadSimulacion = velocidad;
  }

  private pausarSimulacion(): void {
    if (this.simulacionTimer) clearInterval(this.simulacionTimer);
    this.simulacionTimer = null;
    this.simulando = false;
  }

  /** Nombre de la parada donde está detenido el furgón simulado, o null si va entre paradas. */
  private paradaEnLaQueEsta(): string | null {
    const gps = this.ultimaPosicionGps;
    const siguiente = this.destinosTrazado[0];
    if (!gps || !siguiente) return null;
    const distancia = distanciaMetros([gps.latitud, gps.longitud], [siguiente.latitud, siguiente.longitud]);
    if (distancia > LLEGADA_PARADA_METROS) return null;
    return this.paradaActual ? `la casa de ${this.paradaActual.estudiante}` : this.destinoNombre;
  }

  private avanzarSimulacion(): void {
    // Mientras el mapa se redibuja no hay trazado: se espera al siguiente paso.
    if (!this.mapa || this.trazadoCompleto.length < 2) return;

    const gps = this.ultimaPosicionGps;
    const ubicacion = gps ? ubicarEnTrazado(this.trazadoCompleto, [gps.latitud, gps.longitud], this.indiceTrazado) : null;
    const desde: Coordenada = ubicacion ? ubicacion.punto : this.trazadoCompleto[0];
    const paso = VELOCIDAD_SIMULACION_MS * this.velocidadSimulacion * (PASO_SIMULACION_MS / 1000);

    let punto: Coordenada;
    let llego = false;
    const siguiente = this.destinosTrazado[0];
    // Se mide lo que falta por el camino: pasar por el otro lado de la avenida no cuenta como llegar.
    const llegada = siguiente && ubicacion
      ? distanciaHastaParada(this.trazadoCompleto, ubicacion, [siguiente.latitud, siguiente.longitud])
      : null;
    if (siguiente && llegada && llegada.metros <= paso) {
      // Llega a la parada: se ubica en ella y se detiene hasta que el conductor la resuelva.
      punto = [siguiente.latitud, siguiente.longitud];
      llego = true;
    } else {
      const avance = avanzarSobreTrazado(this.trazadoCompleto, ubicacion?.indice ?? 0, desde, paso);
      punto = avance.punto;
      llego = avance.alFinal;
    }

    this.ultimaPosicionGps = { latitud: punto[0], longitud: punto[1], precision: 5 };
    this.actualizarMarcadorFurgon(false);
    this.seguirTrazado();
    this.publicarPosicionSimulada(llego);

    if (llego) {
      this.pausarSimulacion();
      const parada = this.paradaEnLaQueEsta() || this.destinoNombre;
      this.lanzarToast(`Llegaste a ${parada}. Marca la subida o la entrega y presiona ▶ para seguir.`, 'success');
    }
    this.cdr.detectChanges();
  }

  /** La posición simulada se publica como si fuera el GPS: así la ven el apoderado y el panel. */
  private publicarPosicionSimulada(forzar: boolean): void {
    const gps = this.ultimaPosicionGps;
    const ahora = Date.now();
    if (!this.ruta?.id || !gps || (!forzar && ahora - this.ultimoEnvioSimuladoMs < ENVIO_SIMULACION_MS)) return;
    this.ultimoEnvioSimuladoMs = ahora;
    this.ultimoEnvioGpsMs = ahora;
    this.notificationService.actualizarUbicacionRuta(this.ruta.id, gps.latitud, gps.longitud, PRECISION_SIMULADA_METROS).subscribe({
      error: err => console.error('No se pudo publicar la posición simulada:', err)
    });
  }

  private destruirMapa(): void {
    if (this.mapa) {
      this.mapa.remove();
      this.mapa = undefined;
    }
    this.capaRuta = undefined;
    this.trazadoCompleto = [];
    this.indiceTrazado = 0;
    this.trazadoSinGps = false;
    this.marcadores = [];
    this.marcadorFurgon = undefined;
  }

  private lanzarToast(mensaje: string, color = 'success'): void {
    this.mensajeToast = mensaje;
    this.colorToast = color;
    this.mostrarToast = true;
  }
}
