import { Component, OnInit, signal, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { RutasService, Ruta } from '../../../core/services/rutas.service';
import { MapaSeguimientoComponent } from '../../mapa/mapa-seguimiento.component';
import { alCambiarColegio } from '../../../core/utils/al-cambiar-colegio';

@Component({
  selector: 'app-rutas-lista',
  standalone: true,
  imports: [CommonModule, MapaSeguimientoComponent],
  templateUrl: './rutas-lista.component.html',
  styleUrl: './rutas-lista.component.scss'
})
export class RutasListaComponent implements OnInit {
  rutas = signal<Ruta[]>([]);
  cargando = signal<boolean>(true);
  soloSinConductor = signal(false);

  mostrarMapa = signal<boolean>(false);
  rutaSeleccionada = signal<Ruta | null>(null);

  constructor(
    private rutasService: RutasService,
    private router: Router,
    private route: ActivatedRoute,
    private cdr: ChangeDetectorRef
  ) {
    alCambiarColegio(() => this.cargarRutas());
  }

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      this.soloSinConductor.set(params['filtro'] === 'sin_conductor');
    });
    this.cargarRutas();
  }

  rutasVisibles(): Ruta[] {
    if (!this.soloSinConductor()) return this.rutas();
    return this.rutas().filter(ruta =>
      (ruta.estado === 'activa' || ruta.estado === 'en_ruta')
      && !ruta.conductor_id
    );
  }

  cargarRutas(): void {
    this.cargando.set(true);
    this.rutasService.getRutas().subscribe({
      next: (data) => {
        const mapped: Ruta[] = data.map(r => ({
          ...r,
          estudiantesCount: r.estudiantesCount ?? r.estudiantes_count ?? 0,
          estado: r.estado || 'inactiva'
        }));
        this.rutas.set(mapped);
        this.cargando.set(false);
        this.cdr.markForCheck();
      },
      error: () => {
        this.cargando.set(false);
      }
    });
  }

  nuevaRuta(): void {
    this.router.navigate(['/rutas/nuevo']);
  }

  editarRuta(id: string | number | undefined): void {
    if (id !== undefined) {
      this.router.navigate(['/rutas/editar', id]);
    }
  }

  eliminarRuta(id: string | number | undefined): void {
    if (!id) return;
    if (confirm('¿Desactivar esta ruta? Sus estudiantes quedarán sin conductor hasta que se asignen a otra ruta. Quedará en la papelera y podrás reactivarla.')) {
      this.rutasService.eliminarRuta(id).subscribe({
        next: (res: any) => {
          alert(res?.message || 'Quedó desactivado. Puedes reactivarlo desde la papelera.');
          this.cargarRutas();
        },
        error: (err) => alert(err?.error?.message || 'No fue posible desactivar la ruta.')
      });
    }
  }

  iniciarRuta(ruta: Ruta): void {
    if (ruta.id === undefined) return;
    this.rutasService.iniciarRuta(ruta.id).subscribe({
      next: () => this.cargarRutas(),
      error: error => alert(error?.error?.message || 'No fue posible iniciar la ruta.')
    });
  }

  finalizarRuta(ruta: Ruta): void {
    if (ruta.id === undefined) return;
    this.rutasService.finalizarRuta(ruta.id).subscribe({
      next: () => this.cargarRutas(),
      error: error => alert(error?.error?.message || 'No fue posible finalizar la ruta.')
    });
  }

  /** Solo en modo demostración: el conductor podrá simular el recorrido de esta ruta. */
  cambiarSimulacion(ruta: Ruta): void {
    if (ruta.id === undefined) return;
    const activar = !ruta.simulacion_activa;
    if (activar && !confirm(`¿Activar la simulación de "${ruta.nombre}"? El conductor podrá recorrerla sin moverse, para la demostración.`)) return;
    this.rutasService.cambiarSimulacion(ruta.id, activar).subscribe({
      next: () => this.cargarRutas(),
      error: error => alert(error?.error?.message || 'No fue posible cambiar la simulación.')
    });
  }

  abrirMapa(ruta: Ruta): void {
    this.rutaSeleccionada.set(ruta);
    this.mostrarMapa.set(true);
  }

  cerrarMapa(): void {
    this.mostrarMapa.set(false);
    this.rutaSeleccionada.set(null);
  }
}
