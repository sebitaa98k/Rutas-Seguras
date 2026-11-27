import { Component, Input, Output, EventEmitter, OnInit, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ColegioService, Colegio, Sede } from '../../../core/services/colegio.service';
import { REGION_METROPOLITANA } from '../../../shared/chile-territorio';
import { SelectorUbicacionComponent, UbicacionSeleccionada } from '../../../shared/selector-ubicacion/selector-ubicacion.component';

@Component({
  selector: 'app-sedes-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, SelectorUbicacionComponent],
  templateUrl: './sedes-modal.component.html',
  styleUrl: './sedes-modal.component.scss'
})
export class SedesModalComponent implements OnInit {
  @Input({ required: true }) colegio!: Colegio;
  @Output() alCerrar = new EventEmitter<void>();

  private colegioService = inject(ColegioService);

  sedes = signal<Sede[]>([]);
  cargando = signal(true);
  guardando = signal(false);

  // Formulario nueva/edición de sede
  sedeForm = signal<Partial<Sede>>({
    nombre: '',
    direccion: '',
    comuna: '',
    region: REGION_METROPOLITANA,
    latitud: null,
    longitud: null,
    telefono: '',
    activa: true
  });
  modoEdicion = signal(false);
  sedeEditandoId = signal<number | null>(null);
  editandoPrincipal = signal(false);

  ngOnInit(): void {
    this.cargarSedes();
  }

  ubicacionCambio(ubicacion: UbicacionSeleccionada): void {
    this.sedeForm.update(data => ({
      ...data,
      direccion: ubicacion.direccion,
      comuna: ubicacion.comuna,
      region: ubicacion.region,
      latitud: ubicacion.latitud,
      longitud: ubicacion.longitud,
    }));
  }

  cargarSedes(): void {
    this.cargando.set(true);
    this.colegioService.getSedes(this.colegio.id).subscribe({
      next: (data) => {
        this.sedes.set(data || []);
        this.cargando.set(false);
      },
      error: () => this.cargando.set(false)
    });
  }

  guardarSede(): void {
    const data = this.sedeForm();
    if (!data.nombre?.trim()) {
      alert('Debe ingresar un nombre para la sede.');
      return;
    }
    if (this.editandoPrincipal()) {
      // La sede principal copia los datos del colegio: aquí solo cambia su nombre.
      this.guardarPrincipal(data.nombre.trim());
      return;
    }
    if (!data.direccion?.trim()) {
      alert('Debe ingresar la dirección de la sede.');
      return;
    }
    if (!data.region?.trim() || !data.comuna?.trim()) {
      alert('Debe seleccionar la región y la comuna de la sede.');
      return;
    }
    if (!data.telefono?.trim()) {
      alert('Debe ingresar el teléfono de contacto de la sede.');
      return;
    }
    if (data.latitud === null || data.latitud === undefined || data.longitud === null || data.longitud === undefined) {
      alert('Debe ingresar latitud y longitud para la sede.');
      return;
    }
    if (data.latitud < -90 || data.latitud > 90 || data.longitud < -180 || data.longitud > 180) {
      alert('Las coordenadas ingresadas no son válidas.');
      return;
    }

    this.guardando.set(true);

    if (this.modoEdicion() && this.sedeEditandoId()) {
      this.colegioService.updateSede(this.sedeEditandoId()!, data).subscribe({
        next: () => {
          this.guardando.set(false);
          this.resetForm();
          this.cargarSedes();
        },
        error: (err) => {
          this.guardando.set(false);
          alert(err?.error?.message || 'Error al actualizar sede.');
        }
      });
    } else {
      this.colegioService.createSede(this.colegio.id, data).subscribe({
        next: () => {
          this.guardando.set(false);
          this.resetForm();
          this.cargarSedes();
        },
        error: (err) => {
          this.guardando.set(false);
          alert(err?.error?.message || 'Error al crear sede.');
        }
      });
    }
  }

  private guardarPrincipal(nombre: string): void {
    this.guardando.set(true);
    this.colegioService.updateSede(this.sedeEditandoId()!, { nombre }).subscribe({
      next: () => {
        this.guardando.set(false);
        this.resetForm();
        this.cargarSedes();
      },
      error: (err) => {
        this.guardando.set(false);
        alert(err?.error?.message || 'Error al actualizar sede.');
      }
    });
  }

  nombresInspectores(sede: Sede): string {
    return (sede.inspectores || []).map(inspector => inspector.nombre).join(', ');
  }

  editarSede(sede: Sede): void {
    this.editandoPrincipal.set(!!sede.es_principal);
    this.modoEdicion.set(true);
    this.sedeEditandoId.set(sede.id);
    this.sedeForm.set({
      nombre: sede.nombre,
      direccion: sede.direccion || '',
      comuna: sede.comuna || '',
      region: sede.region || '',
      latitud: sede.latitud ?? null,
      longitud: sede.longitud ?? null,
      telefono: sede.telefono || '',
      activa: sede.activa
    });
  }

  eliminarSede(sede: Sede): void {
    if (confirm(`¿Desactivar la sede "${sede.nombre}"? Solo se puede si no tiene estudiantes, furgones, rutas ni inspectores. Quedará en la papelera y podrás reactivarla.`)) {
      this.colegioService.deleteSede(sede.id).subscribe({
        next: (res: any) => {
          alert(res?.message || 'Quedó desactivado. Puedes reactivarlo desde la papelera.');
          this.cargarSedes();
        },
        error: (err) => alert(err?.error?.message || 'No se pudo desactivar la sede.')
      });
    }
  }

  resetForm(): void {
    this.modoEdicion.set(false);
    this.editandoPrincipal.set(false);
    this.sedeEditandoId.set(null);
    this.sedeForm.set({
      nombre: '',
      direccion: '',
      comuna: '',
      region: REGION_METROPOLITANA,
      latitud: null,
      longitud: null,
      telefono: '',
      activa: true
    });
  }

  cerrar(): void {
    this.alCerrar.emit();
  }
}
