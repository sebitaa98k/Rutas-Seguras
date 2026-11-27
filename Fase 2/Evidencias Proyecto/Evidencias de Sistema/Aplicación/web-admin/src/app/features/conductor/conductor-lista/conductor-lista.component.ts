import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ConductorService, Conductor, EstudianteItem } from '../../../core/services/conductor.service';
import { alCambiarColegio } from '../../../core/utils/al-cambiar-colegio';

@Component({
  selector: 'app-conductor-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './conductor-lista.component.html',
  styleUrl: './conductor-lista.component.scss'
})
export class ConductorListaComponent implements OnInit {
  conductores: Conductor[] = [];
  cargando = true;

  // Modal de solo lectura con los estudiantes de sus rutas
  mostrarModalAsignacion: boolean = false;
  conductorSeleccionado: Conductor | null = null;
  estudiantesAsignados: EstudianteItem[] = [];
  cargandoModal: boolean = false;

  constructor(
    private conductorService: ConductorService,
    private router: Router,
    private cdr: ChangeDetectorRef
  ) {
    alCambiarColegio(() => this.cargarConductores());
  }

  ngOnInit(): void {
    this.cargarConductores();
  }

  cargarConductores(): void {
    this.cargando = true;
    this.conductorService.getConductores().subscribe({
      next: (data) => {
        this.conductores = data;
        this.cargando = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error cargando conductores desde backend:', err);
        this.cargando = false;
      }
    });
  }

  onEdit(id?: number): void {
    if (id) {
      this.router.navigate(['/conductores/editar', id]);
    }
  }

  onDelete(id?: number): void {
    if (!id) return;
    if (confirm('¿Desactivar a este conductor? Ya no podrá ingresar. Quedará en la papelera y podrás reactivarlo.')) {
      this.conductorService.eliminarConductor(id).subscribe({
        next: (res: any) => {
          alert(res?.message || 'Quedó desactivado. Puedes reactivarlo desde la papelera.');
          this.cargarConductores();
        },
        error: (err) => alert(err?.error?.message || 'No se pudo desactivar el conductor.')
      });
    }
  }

  // --- Ver los estudiantes del conductor (solo lectura: se asignan en la ruta) ---

  abrirModalAsignacion(conductor: Conductor): void {
    if (!conductor.id) return;
    this.conductorSeleccionado = conductor;
    this.mostrarModalAsignacion = true;
    this.cargarDatosModal(conductor.id);
  }

  cerrarModalAsignacion(): void {
    this.mostrarModalAsignacion = false;
    this.conductorSeleccionado = null;
    this.estudiantesAsignados = [];
  }

  cargarDatosModal(conductorId: number): void {
    this.cargandoModal = true;
    this.conductorService.getEstudiantesConductor(conductorId).subscribe({
      next: (asignados) => {
        this.estudiantesAsignados = asignados;
        this.cargandoModal = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error cargando estudiantes del conductor:', err);
        this.cargandoModal = false;
        this.cdr.markForCheck();
      }
    });
  }
}
