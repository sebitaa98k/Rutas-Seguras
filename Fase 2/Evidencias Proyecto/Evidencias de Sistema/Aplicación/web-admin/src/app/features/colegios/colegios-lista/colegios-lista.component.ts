import { Component, OnInit, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ColegioService, Colegio } from '../../../core/services/colegio.service';
import { SedesModalComponent } from '../sedes-modal/sedes-modal.component';
import { AdminColegioModalComponent } from '../admin-colegio-modal/admin-colegio-modal.component';

@Component({
  selector: 'app-colegios-lista',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule, SedesModalComponent, AdminColegioModalComponent],
  templateUrl: './colegios-lista.component.html',
  styleUrl: './colegios-lista.component.scss'
})
export class ColegiosListaComponent implements OnInit {
  protected colegioService = inject(ColegioService);

  colegios = signal<Colegio[]>([]);
  cargando = signal(true);
  errorCarga = signal('');
  busqueda = signal('');
  colegioParaSedes = signal<Colegio | null>(null);
  colegioParaAdmins = signal<Colegio | null>(null);

  ngOnInit(): void {
    this.cargarColegios();
  }

  async cargarColegios(): Promise<void> {
    this.cargando.set(true);
    this.errorCarga.set('');
    try {
      const data = await this.colegioService.getColegios();
      this.colegios.set(data);
    } catch (error) {
      console.error('Error al cargar colegios:', error);
      this.colegios.set([]);
      this.errorCarga.set('No fue posible cargar los colegios. Verifica que Django esté ejecutándose y vuelve a intentar.');
    } finally {
      this.cargando.set(false);
    }
  }

  colegiosFiltrados(): Colegio[] {
    const query = this.busqueda().toLowerCase().trim();
    if (!query) return this.colegios();
    return this.colegios().filter(c =>
      c.nombre.toLowerCase().includes(query) ||
      (c.rbd && c.rbd.toLowerCase().includes(query)) ||
      (c.direccion && c.direccion.toLowerCase().includes(query))
    );
  }

  abrirModalSedes(colegio: Colegio): void {
    this.colegioParaSedes.set(colegio);
  }

  cerrarModalSedes(): void {
    this.colegioParaSedes.set(null);
    this.cargarColegios();
  }

  abrirModalAdmins(colegio: Colegio): void {
    this.colegioParaAdmins.set(colegio);
  }

  cerrarModalAdmins(): void {
    this.colegioParaAdmins.set(null);
  }

  async eliminarColegio(colegio: Colegio): Promise<void> {
    if (confirm(`¿Desactivar el colegio "${colegio.nombre}"? Solo se puede si ya no tiene nada activo. Quedará en la papelera y podrás reactivarlo.`)) {
      this.colegioService.deleteColegio(colegio.id).subscribe({
        next: (res) => {
          alert(res?.message || 'Operación realizada correctamente.');
          this.cargarColegios();
        },
        error: (err) => {
          const msg = err?.error?.message || err?.error?.detail || 'No se pudo desactivar el colegio.';
          alert(msg);
        }
      });
    }
  }
}
