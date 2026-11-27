import { Component, OnInit, signal, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { FurgonesService, Furgon } from '../../../core/services/furgones.service';
import { alCambiarColegio } from '../../../core/utils/al-cambiar-colegio';

@Component({
  selector: 'app-furgones-lista',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './furgones-lista.component.html',
  styleUrl: './furgones-lista.component.scss'
})
export class FurgonesListaComponent implements OnInit {
  furgones = signal<Furgon[]>([]);
  /** La columna Sede solo aparece si hay furgones de colegios multisede (los demás la traen vacía). */
  mostrarSede(): boolean {
    return this.furgones().some(furgon => !!furgon.sede_nombre);
  }
  cargando = signal<boolean>(true);
  errorMensaje = signal('');

  constructor(
    private furgonesService: FurgonesService,
    private router: Router,
    private cdr: ChangeDetectorRef
  ) {
    alCambiarColegio(() => this.cargarFurgones());
  }

  ngOnInit(): void {
    this.cargarFurgones();
  }

  cargarFurgones(): void {
    this.cargando.set(true);
    this.errorMensaje.set('');
    this.furgonesService.getFurgones().subscribe({
      next: (data) => {
        const mapped = data.map(item => ({
          ...item,
          marcaModelo: item.marcaModelo || item.marca_modelo || '',
          conductor: item.conductor || 'Sin rutas asignadas'
        }));
        this.furgones.set(mapped);
        this.cargando.set(false);
        this.cdr.markForCheck();
      },
      error: (error) => {
        console.error('Error al cargar furgones:', error);
        this.furgones.set([]);
        this.errorMensaje.set('No fue posible cargar los furgones. Los datos de ejemplo fueron eliminados para no confundirlos con registros reales.');
        this.cargando.set(false);
      }
    });
  }

  nuevoFurgon(): void {
    this.router.navigate(['/furgones/nuevo']);
  }

  editarFurgon(id: string | number | undefined): void {
    if (id !== undefined) {
      this.router.navigate(['/furgones/editar', id]);
    }
  }

  eliminarFurgon(id: string | number | undefined): void {
    if (!id) return;
    if (confirm('¿Desactivar este furgón? Quedará en la papelera y podrás reactivarlo.')) {
      this.furgonesService.eliminarFurgon(id).subscribe({
        next: (res: any) => {
          alert(res?.message || 'Quedó desactivado. Puedes reactivarlo desde la papelera.');
          this.cargarFurgones();
        },
        error: (err) => alert(err?.error?.message || 'No fue posible desactivar el furgón.')
      });
    }
  }
}
