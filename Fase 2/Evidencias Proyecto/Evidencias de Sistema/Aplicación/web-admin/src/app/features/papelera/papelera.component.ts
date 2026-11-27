import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { GrupoPapelera, ItemPapelera, PapeleraService } from '../../core/services/papelera.service';
import { alCambiarColegio } from '../../core/utils/al-cambiar-colegio';

/** Papelera: lo desactivado (estudiantes, rutas, cuentas, etc.) se puede reactivar desde aquí. */
@Component({
  selector: 'app-papelera',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './papelera.component.html',
  styleUrl: './papelera.component.scss'
})
export class PapeleraComponent implements OnInit {
  grupos: GrupoPapelera[] = [];
  tipoActivo = '';
  cargando = false;
  error = '';
  aviso = '';
  reactivando = new Set<string>();
  /** Elemento que se va a eliminar definitivamente; abre la ventana de confirmación. */
  porEliminar: ItemPapelera | null = null;
  /** El seguro: hay que marcar que se entiende que no se puede deshacer. */
  confirmaEliminar = false;
  eliminando = false;

  constructor(private papeleraService: PapeleraService, private cdr: ChangeDetectorRef) {
    alCambiarColegio(() => this.cargar());
  }

  ngOnInit(): void {
    this.cargar();
  }

  get total(): number {
    return this.grupos.reduce((suma, grupo) => suma + grupo.items.length, 0);
  }

  get grupoActivo(): GrupoPapelera | undefined {
    return this.grupos.find(grupo => grupo.tipo === this.tipoActivo);
  }

  cargar(): void {
    this.cargando = true;
    this.error = '';
    this.papeleraService.listar().subscribe({
      next: grupos => {
        this.grupos = grupos;
        if (!grupos.some(grupo => grupo.tipo === this.tipoActivo)) {
          // Abre el primer grupo que tenga algo; si no hay nada, el primero.
          this.tipoActivo = (grupos.find(grupo => grupo.items.length) || grupos[0])?.tipo || '';
        }
        this.cargando = false;
        this.cdr.detectChanges();
      },
      error: err => {
        this.error = err?.error?.message || 'No se pudo cargar la papelera.';
        this.cargando = false;
        this.cdr.detectChanges();
      }
    });
  }

  clave(item: ItemPapelera): string {
    return `${item.tipo}-${item.id}`;
  }

  pedirEliminar(item: ItemPapelera): void {
    this.porEliminar = item;
    this.confirmaEliminar = false;
    this.aviso = '';
    this.error = '';
  }

  cancelarEliminar(): void {
    if (this.eliminando) return;
    this.porEliminar = null;
    this.confirmaEliminar = false;
  }

  aceptarEliminar(): void {
    const item = this.porEliminar;
    if (!item || !this.confirmaEliminar || this.eliminando) return;
    this.eliminando = true;
    this.papeleraService.eliminarDefinitivo(item).subscribe({
      next: res => {
        this.eliminando = false;
        this.porEliminar = null;
        this.aviso = res?.message || 'Se eliminó definitivamente.';
        this.cargar();
      },
      error: err => {
        this.eliminando = false;
        this.porEliminar = null;
        // 409: tiene historial de recorridos u otros registros que dependen de él.
        this.error = err?.error?.message || 'No se pudo eliminar.';
        this.cdr.detectChanges();
      }
    });
  }

  /** Textos de la confirmación de "Mover al colegio", según lo que se mueve. */
  private quedaraTras(item: ItemPapelera): string {
    switch (item.tipo) {
      case 'estudiante': return 'Quedará activo y sin ruta: después agrégalo a una ruta.';
      case 'furgon': return 'Quedará activo y sin ruta.';
      case 'ruta': return 'Quedará activa y sin estudiantes: mueve primero a los que correspondan.';
      default: return 'Su cuenta quedará activa en el colegio.';
    }
  }

  moverAlColegio(item: ItemPapelera): void {
    if (!confirm(`¿Mover "${item.nombre}" al colegio? ${this.quedaraTras(item)}`)) return;
    this.reactivando.add(this.clave(item));
    this.aviso = '';
    this.error = '';
    this.papeleraService.moverAlColegio(item).subscribe({
      next: res => {
        this.reactivando.delete(this.clave(item));
        this.aviso = res?.message || 'Se movió al colegio.';
        this.cargar();
      },
      error: err => {
        this.reactivando.delete(this.clave(item));
        // 409: falta algo antes (por ejemplo, reactivar el colegio o el apoderado).
        this.error = err?.error?.message || 'No se pudo mover al colegio.';
        this.cdr.detectChanges();
      }
    });
  }

  reactivar(item: ItemPapelera): void {
    if (!confirm(`¿Reactivar "${item.nombre}"?`)) return;
    this.reactivando.add(this.clave(item));
    this.aviso = '';
    this.error = '';
    this.papeleraService.reactivar(item).subscribe({
      next: res => {
        this.reactivando.delete(this.clave(item));
        this.aviso = res?.message || 'Se reactivó.';
        this.cargar();
      },
      error: err => {
        this.reactivando.delete(this.clave(item));
        // 409: falta reactivar antes otra cosa (por ejemplo, su apoderado o su sede).
        this.error = err?.error?.message || 'No se pudo reactivar.';
        this.cdr.detectChanges();
      }
    });
  }
}
