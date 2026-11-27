import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { DelegadoService, Delegado } from '../../../core/services/delegado.service';
import { alCambiarColegio } from '../../../core/utils/al-cambiar-colegio';

@Component({
  selector: 'app-delegado-lista',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './delegado-lista.component.html',
  styleUrl: './delegado-lista.component.scss'
})
export class DelegadoListaComponent implements OnInit {
  delegados: Delegado[] = [];
  expandedDelegadoIds: Set<number> = new Set<number>();
  cargando = false;

  constructor(
    private delegadoService: DelegadoService,
    private router: Router,
    private cdr: ChangeDetectorRef
  ) {
    alCambiarColegio(() => this.cargarDelegados());
  }

  ngOnInit(): void {
    this.cargarDelegados();
  }

  cargarDelegados(): void {
    this.cargando = true;
    this.delegadoService.getDelegados().subscribe({
      next: (data) => {
        this.delegados = data;
        this.cargando = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error al cargar delegados:', err);
        this.cargando = false;
        this.cdr.markForCheck();
      }
    });
  }

  toggleExpand(id: number): void {
    if (this.expandedDelegadoIds.has(id)) {
      this.expandedDelegadoIds.delete(id);
    } else {
      this.expandedDelegadoIds.add(id);
    }
  }

  isExpanded(id: number): boolean {
    return this.expandedDelegadoIds.has(id);
  }

  onEdit(id: number): void {
    this.router.navigate(['/delegados/editar', id]);
  }

  onDelete(id: number): void {
    if (confirm('¿Desactivar a este delegado? Ya no podrá ingresar. Quedará en la papelera y podrás reactivarlo.')) {
      this.delegadoService.deleteDelegado(id).subscribe({
        next: (res: any) => {
          alert(res?.message || 'Quedó desactivado. Puedes reactivarlo desde la papelera.');
          this.cargarDelegados();
        },
        error: (err) => alert(err?.error?.message || 'No se pudo desactivar el delegado.')
      });
    }
  }

  etiquetaTipo(delegado: Delegado): string {
    return delegado.tipo_delegado === 'inspector' ? 'Inspector/a' : 'Persona autorizada';
  }

  onDesvincular(delegadoId: number, estudianteId: number, estudianteNombre: string): void {
    if (confirm(`¿Deseas desvincular al estudiante "${estudianteNombre}" de este delegado?`)) {
      this.delegadoService.desvincularEstudiante(estudianteId, delegadoId).subscribe({
        next: (res) => {
          alert(res.message || 'Estudiante desvinculado con éxito.');
          this.cargarDelegados();
        },
        error: (err) => {
          console.error('Error al desvincular estudiante:', err);
          alert('Ocurrió un error al desvincular el estudiante.');
        }
      });
    }
  }
}
