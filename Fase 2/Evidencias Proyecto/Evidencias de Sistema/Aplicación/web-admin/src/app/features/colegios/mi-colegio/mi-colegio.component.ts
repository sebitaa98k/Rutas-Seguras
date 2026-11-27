import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';
import { Colegio, ColegioService, Sede } from '../../../core/services/colegio.service';

/**
 * "Mi colegio" del administrador de un colegio: un resumen, no un formulario.
 * - Todos los planes: datos del colegio y un botón al formulario de contacto.
 * - Avanzado (multisede): además sus sedes. Solo puede cambiar el teléfono de las que no son la principal;
 *   crear o desactivar sedes lo hace la plataforma, a pedido del colegio.
 */
@Component({
  selector: 'app-mi-colegio',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './mi-colegio.component.html',
  styleUrl: './mi-colegio.component.scss'
})
export class MiColegioComponent implements OnInit {
  private colegioService = inject(ColegioService);
  private authService = inject(AuthService);

  colegio = signal<Colegio | null>(null);
  sedes = signal<Sede[]>([]);
  cargando = signal(true);
  error = signal('');

  /** Sede cuyo teléfono se está editando. */
  editandoId = signal<number | null>(null);
  telefono = '';
  guardando = signal(false);

  ngOnInit(): void {
    const colegioId = this.authService.currentUser()?.colegioId;
    if (!colegioId) {
      this.cargando.set(false);
      this.error.set('Tu cuenta no tiene un colegio asignado.');
      return;
    }
    this.colegioService.getColegio(colegioId).subscribe({
      next: (colegio) => {
        this.colegio.set(colegio);
        this.cargando.set(false);
        if (colegio.es_multisede) {
          this.cargarSedes(colegio.id);
        }
      },
      error: () => {
        this.cargando.set(false);
        this.error.set('No se pudo cargar la información del colegio.');
      }
    });
  }

  private cargarSedes(colegioId: number): void {
    this.colegioService.getSedes(colegioId).subscribe({
      next: (sedes) => this.sedes.set(sedes || []),
      error: () => this.error.set('No se pudieron cargar las sedes.')
    });
  }

  nombresInspectores(sede: Sede): string {
    return (sede.inspectores || []).map(inspector => inspector.nombre).join(', ');
  }

  editarTelefono(sede: Sede): void {
    this.editandoId.set(sede.id);
    this.telefono = sede.telefono || '';
  }

  cancelar(): void {
    this.editandoId.set(null);
  }

  guardarTelefono(sede: Sede): void {
    const telefono = this.telefono.trim();
    if (!telefono) {
      alert('Ingresa el teléfono de la sede.');
      return;
    }
    this.guardando.set(true);
    this.colegioService.updateSede(sede.id, { telefono }).subscribe({
      next: (actualizada) => {
        this.guardando.set(false);
        this.editandoId.set(null);
        this.sedes.update(lista => lista.map(item => item.id === sede.id ? { ...item, telefono: actualizada.telefono } : item));
      },
      error: (err) => {
        this.guardando.set(false);
        alert(err?.error?.message || err?.error?.telefono?.[0] || 'No se pudo guardar el teléfono.');
      }
    });
  }
}
