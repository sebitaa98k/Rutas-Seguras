import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { ApoderadoService, Apoderado } from '../../../core/services/apoderado.service';
import { alCambiarColegio } from '../../../core/utils/al-cambiar-colegio';
import { AuthService } from '../../../core/services/auth.service';
import { ColegioService } from '../../../core/services/colegio.service';

@Component({
  selector: 'app-apoderado-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './apoderado-lista.component.html',
  styleUrl: './apoderado-lista.component.scss'
})
export class ApoderadoListaComponent implements OnInit {
  apoderados: Apoderado[] = [];
  expandedApoderadoIds: Set<number> = new Set<number>();
  cargando = false;

  constructor(
    private apoderadoService: ApoderadoService,
    private router: Router,
    private cdr: ChangeDetectorRef
  ) {
    alCambiarColegio(() => this.cargarApoderados());
  }

ngOnInit(): void {
  this.cargarApoderados();
}

cargarApoderados(): void {
  this.cargando = true;

  this.apoderadoService.getApoderados().subscribe({
    next: (data) => {
      

      this.apoderados = data;
      this.cargando = false;

      this.cdr.markForCheck();
    },
    error: (err) => {
      console.error('❌ ERROR AL CARGAR APODERADOS:', err);
      this.cargando = false;

      this.cdr.markForCheck();
    }
  });
}

  toggleExpand(id: number): void {
    if (this.expandedApoderadoIds.has(id)) {
      this.expandedApoderadoIds.delete(id);
    } else {
      this.expandedApoderadoIds.add(id);
    }
  }

  isExpanded(id: number): boolean {
    return this.expandedApoderadoIds.has(id);
  }

  onEdit(id: number): void {
    this.router.navigate(['/apoderados/editar', id]);
  }

  private authService = inject(AuthService);
  private colegioService = inject(ColegioService);

  /** Colegio desde el que se mira la lista (el propio, o el elegido arriba por el admin de plataforma). */
  private get colegioActual(): number | null {
    return this.authService.currentUser()?.colegioId || this.colegioService.selectedColegioId() || null;
  }

  /** Sus datos los edita solo el colegio dueño (el primero que lo registró) o el admin de plataforma. */
  puedeEditar(apoderado: Apoderado): boolean {
    if (this.authService.currentUser()?.role === 'ADMIN_PLATAFORMA') return true;
    return !apoderado.colegio_id || apoderado.colegio_id === this.authService.currentUser()?.colegioId;
  }

  /** Otros colegios donde también tiene hijos. */
  otrosColegios(apoderado: Apoderado): string {
    const actual = this.colegioActual;
    return (apoderado.colegios_vinculados || [])
      .filter(colegio => colegio.id !== actual)
      .map(colegio => colegio.nombre)
      .join(', ');
  }

  onDelete(apoderado: Apoderado): void {
    const id = apoderado.id;
    const mensaje = this.colegioActual && this.otrosColegios(apoderado)
      ? `Este apoderado también está en ${this.otrosColegios(apoderado)}. Se desvinculará solo de este colegio: ` +
        'sus hijos de aquí se desactivarán y su cuenta seguirá activa en sus otros colegios. ¿Continuar?'
      : '¿Desactivar a este apoderado? Ya no podrá ingresar. Quedará en la papelera y podrás reactivarlo.';
    if (confirm(mensaje)) {
      this.apoderadoService.deleteApoderado(id).subscribe({
        next: (res: any) => {
          alert(res?.message || 'Quedó desactivado. Puedes reactivarlo desde la papelera.');
          this.cargarApoderados();
        },
        error: (err) => alert(err?.error?.message || 'No se pudo desactivar el apoderado.')
      });
    }
  }

  subirBiometriaEstudiante(estudianteId: number, event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    const formatosPermitidos = ['image/jpeg', 'image/jpg', 'image/png'];
    if (!formatosPermitidos.includes(file.type.toLowerCase())) {
      alert('Selecciona una imagen JPG, JPEG o PNG.');
      input.value = '';
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      alert('La imagen no puede superar los 5 MB.');
      input.value = '';
      return;
    }
    this.cargando = true;

    this.apoderadoService.registrarBiometriaEstudiante(estudianteId, file).subscribe({
      next: (res) => {
        this.cargando = false;
        input.value = '';
        alert(res.message || 'Rostro procesado y biometría guardada exitosamente.');
        this.cargarApoderados();
      },
      error: (err) => {
        this.cargando = false;
        input.value = '';
        const msg = err.error?.message || 'Error al procesar la imagen biométrica.';
        alert(`❌ Error: ${msg}`);
        this.cdr.markForCheck();
      }
    });
  }
}
