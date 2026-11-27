import { Component, OnInit, OnDestroy, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { EMPTY, Subject, Subscription, catchError, map, merge, switchMap, timer } from 'rxjs';
import { ColegioService } from '../../../core/services/colegio.service';
import { AuthService } from '../../../core/services/auth.service';
import { environment } from '../../../../environments/environment';

interface StatCard {
  key: string;
  title: string;
  count: number;
  icon: string;
  colorClass: string;
  route: string;
}

export interface DashboardAlerts {
  estudiantes_sin_biometria: number;
  estudiantes_sin_conductor: number;
  estudiantes_datos_incompletos: number;
  furgones_sin_conductor: number;
  rutas_sin_conductor: number;
  sedes_sin_inspector?: number;
  rutas_sin_furgon?: number;
}

export interface DashboardStatsResponse {
  colegios?: number;
  colegio_nombre?: string | null;
  estudiantes: number;
  conductores: number;
  apoderados: number;
  furgones: number;
  rutas: number;
  delegados?: number;
  alertas?: DashboardAlerts;
  /** Solo en los colegios multisede las alertas hablan de sedes. */
  colegio_multisede?: boolean;
  operacion_hoy?: DashboardOperation;
}

export interface DashboardOperation {
  rutas_en_recorrido: number;
  estudiantes_a_bordo: number;
  recorridos_completados: number;
  incidencias: number;
}

@Component({
  selector: 'app-dashboard-home',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './dashboard-home.component.html',
  styleUrl: './dashboard-home.component.scss'
})
export class DashboardHomeComponent implements OnInit, OnDestroy {
  private subscription?: Subscription;
  private clockSubscription?: Subscription;
  private readonly colegioChanged$ = new Subject<void>();
  private readonly apiUrl = `${environment.apiBaseUrl}/dashboard/stats/`;
  private colegioService = inject(ColegioService);
  protected authService = inject(AuthService);
  private onColegioChangedListener = () => {
    this.cargando.set(true);
    this.errorCarga.set(false);
    this.datosDesactualizados.set(false);
    this.tieneDatos.set(false);
    this.colegioChanged$.next();
  };

  isAdminColegio = computed(() => this.authService.currentUser()?.role === 'ADMIN_COLEGIO');
  alertas = signal<DashboardAlerts | null>(null);
  colegioMultisede = signal(false);
  operacionHoy = signal<DashboardOperation | null>(null);
  colegioNombre = signal<string | null>(this.authService.currentUser()?.colegioNombre ?? null);
  ahora = signal(new Date());
  ultimaActualizacion = signal<Date | null>(null);
  cargando = signal(true);
  errorCarga = signal(false);
  datosDesactualizados = signal(false);
  tieneDatos = signal(false);

  fechaActual = computed(() => new Intl.DateTimeFormat('es-CL', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  }).format(this.ahora()));

  horaActualizacion = computed(() => {
    const fecha = this.ultimaActualizacion();
    return fecha ? new Intl.DateTimeFormat('es-CL', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    }).format(fecha) : '--:--:--';
  });

  totalAlertas = computed(() => {
    const a = this.alertas();
    if (!a) return 0;
    return (
      (a.estudiantes_sin_biometria || 0) +
      (a.estudiantes_sin_conductor || 0) +
      (a.estudiantes_datos_incompletos || 0) +
      (a.furgones_sin_conductor || 0) +
      (a.rutas_sin_conductor || 0) +
      (a.sedes_sin_inspector || 0) +
      (a.rutas_sin_furgon || 0)
    );
  });

  stats = signal<StatCard[]>([
    {
      key: 'estudiantes',
      title: 'Estudiantes',
      count: 0,
      icon: 'graduation-cap',
      colorClass: 'primary',
      route: '/estudiantes'
    },
    {
      key: 'furgones',
      title: 'Furgones',
      count: 0,
      icon: 'bus',
      colorClass: 'emerald',
      route: '/furgones'
    },
    {
      key: 'rutas',
      title: 'Rutas',
      count: 0,
      icon: 'map-pin',
      colorClass: 'amber',
      route: '/rutas'
    },
    {
      key: 'conductores',
      title: 'Conductores',
      count: 0,
      icon: 'steering-wheel',
      colorClass: 'cyan',
      route: '/conductores'
    },
    {
      key: 'apoderados',
      title: 'Apoderados',
      count: 0,
      icon: 'users',
      colorClass: 'purple',
      route: '/apoderados'
    }
  ]);

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    window.addEventListener('colegio-changed', this.onColegioChangedListener);

    this.subscription = merge(timer(0, 5000), this.colegioChanged$).pipe(
      switchMap(() => {
        const colegioSolicitado = this.colegioService.selectedColegioId();
        return this.http.get<DashboardStatsResponse>(this.apiUrl).pipe(
          map(data => ({ data, colegioSolicitado })),
          catchError(err => {
            console.error('Error al actualizar estadísticas del dashboard:', err);
            this.cargando.set(false);
            if (this.tieneDatos()) {
              this.datosDesactualizados.set(true);
            } else {
              this.errorCarga.set(true);
            }
            return EMPTY;
          })
        );
      })
    ).subscribe({
      next: ({ data, colegioSolicitado }) => {
        if (colegioSolicitado === this.colegioService.selectedColegioId()) {
          this.processStatsResponse(data);
        }
      }
    });

    this.clockSubscription = timer(0, 1000).subscribe(() => this.ahora.set(new Date()));
  }

  ngOnDestroy(): void {
    window.removeEventListener('colegio-changed', this.onColegioChangedListener);
    if (this.subscription) {
      this.subscription.unsubscribe();
    }
    this.colegioChanged$.complete();
    this.clockSubscription?.unsubscribe();
  }

  private processStatsResponse(data: DashboardStatsResponse): void {
    if (!data) return;

    this.cargando.set(false);
    this.errorCarga.set(false);
    this.datosDesactualizados.set(false);
    this.tieneDatos.set(true);
    this.ultimaActualizacion.set(new Date());
    this.colegioNombre.set(data.colegio_nombre ?? null);

    if (data.alertas && (this.isAdminColegio() || this.colegioService.selectedColegioId())) {
      this.alertas.set(data.alertas);
      this.colegioMultisede.set(!!data.colegio_multisede);
      this.operacionHoy.set(data.operacion_hoy ?? null);
    } else {
      this.alertas.set(null);
      this.operacionHoy.set(null);
    }

    const newCards: StatCard[] = [];

    // Si viene la propiedad 'colegios' (modo global para Admin Plataforma), añadir la card de Colegios
    if (data.colegios !== undefined && data.colegios !== null) {
      newCards.push({
        key: 'colegios',
        title: 'Colegios',
        count: data.colegios,
        icon: 'building',
        colorClass: 'indigo',
        route: '/colegios'
      });
    }

    newCards.push(
      { key: 'estudiantes', title: 'Estudiantes', count: data.estudiantes ?? 0, icon: 'graduation-cap', colorClass: 'primary', route: '/estudiantes' },
      { key: 'furgones', title: 'Furgones', count: data.furgones ?? 0, icon: 'bus', colorClass: 'emerald', route: '/furgones' },
      { key: 'rutas', title: 'Rutas', count: data.rutas ?? 0, icon: 'map-pin', colorClass: 'amber', route: '/rutas' },
      { key: 'conductores', title: 'Conductores', count: data.conductores ?? 0, icon: 'steering-wheel', colorClass: 'cyan', route: '/conductores' },
      { key: 'apoderados', title: 'Apoderados', count: data.apoderados ?? 0, icon: 'users', colorClass: 'purple', route: '/apoderados' }
    );

    if (data.delegados !== undefined && data.delegados !== null) {
      newCards.push({
        key: 'delegados',
        title: 'Delegados',
        count: data.delegados,
        icon: 'shield',
        colorClass: 'primary',
        route: '/delegados'
      });
    }

    this.stats.set(newCards);
  }
}
