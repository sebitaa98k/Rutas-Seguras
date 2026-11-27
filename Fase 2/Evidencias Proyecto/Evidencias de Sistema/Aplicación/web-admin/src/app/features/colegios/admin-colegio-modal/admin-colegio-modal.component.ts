import { Component, Input, Output, EventEmitter, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ColegioService, Colegio } from '../../../core/services/colegio.service';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-admin-colegio-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-colegio-modal.component.html',
  styleUrl: './admin-colegio-modal.component.scss'
})
export class AdminColegioModalComponent implements OnInit {
  @Input({ required: true }) colegio!: Colegio;
  @Output() alCerrar = new EventEmitter<void>();

  admins = signal<any[]>([]);
  cargando = signal<boolean>(true);
  guardando = signal<boolean>(false);
  mensajeError = signal<string>('');
  mensajeExito = signal<string>('');

  adminForm = signal<{ nombre: string; apellido: string; email: string; password: string }>({
    nombre: '',
    apellido: '',
    email: '',
    password: ''
  });
  /** Id del administrador que se está editando; null al registrar uno nuevo. */
  editandoId = signal<number | null>(null);

  constructor(private colegioService: ColegioService, private authService: AuthService) {}

  /** Solo el administrador de plataforma edita las cuentas de los administradores de colegio. */
  get puedeEditar(): boolean {
    return this.authService.currentUser()?.role === 'ADMIN_PLATAFORMA';
  }

  editarAdmin(adm: any): void {
    this.mensajeError.set('');
    this.mensajeExito.set('');
    this.editandoId.set(adm.id);
    this.adminForm.set({ nombre: adm.first_name || '', apellido: adm.last_name || '', email: adm.email || '', password: '' });
  }

  cancelarEdicion(): void {
    this.editandoId.set(null);
    this.adminForm.set({ nombre: '', apellido: '', email: '', password: '' });
  }

  ngOnInit(): void {
    if (this.colegio?.id) {
      this.cargarAdministradores();
    }
  }

  cargarAdministradores(): void {
    this.cargando.set(true);
    this.colegioService.getAdministradoresColegio(this.colegio.id).subscribe({
      next: (list) => {
        this.admins.set(list || []);
        this.cargando.set(false);
      },
      error: (err) => {
        console.error('Error al cargar administradores:', err);
        this.cargando.set(false);
      }
    });
  }

  guardarAdmin(): void {
    this.mensajeError.set('');
    this.mensajeExito.set('');
    const data = this.adminForm();

    if (!data.nombre || !data.nombre.trim()) {
      this.mensajeError.set('Debe ingresar el nombre del administrador.');
      return;
    }
    if (!data.apellido || !data.apellido.trim()) {
      this.mensajeError.set('Debe ingresar el apellido del administrador.');
      return;
    }
    if (!data.email || !data.email.trim()) {
      this.mensajeError.set('Debe ingresar el correo electrónico.');
      return;
    }
    const editandoId = this.editandoId();
    // Al editar, la contraseña es opcional; si se escribe, debe tener el largo mínimo.
    if ((!editandoId || data.password) && (!data.password || data.password.length < 6)) {
      this.mensajeError.set('La contraseña debe tener al menos 6 caracteres.');
      return;
    }

    this.guardando.set(true);

    const datos = {
      nombre: data.nombre.trim(),
      apellido: data.apellido.trim(),
      email: data.email.trim(),
      ...(data.password ? { password: data.password } : {})
    };
    const solicitud = editandoId
      ? this.colegioService.updateAdministradorColegio(this.colegio.id, editandoId, datos)
      : this.colegioService.createAdministradorColegio(this.colegio.id, { ...datos, password: data.password });

    solicitud.subscribe({
      next: () => {
        this.guardando.set(false);
        this.mensajeExito.set(editandoId ? 'Administrador actualizado.' : 'Cuenta administrativa creada exitosamente.');
        this.cancelarEdicion();
        this.cargarAdministradores();
      },
      error: (err) => {
        this.guardando.set(false);
        let msg = 'Error al crear el administrador de colegio.';
        if (err?.error?.message) {
          msg = err.error.message;
        } else if (err?.error?.detail) {
          msg = err.error.detail;
        } else if (err?.error?.error) {
          msg = err.error.error;
        } else if (err?.error && typeof err.error === 'object') {
          const details: string[] = [];
          for (const k of Object.keys(err.error)) {
            const v = err.error[k];
            if (Array.isArray(v)) {
              details.push(`${k}: ${v.join(', ')}`);
            } else if (typeof v === 'string') {
              details.push(`${k}: ${v}`);
            }
          }
          if (details.length > 0) {
            msg = details.join(' | ');
          }
        } else if (typeof err?.error === 'string') {
          msg = err.error;
        }
        this.mensajeError.set(msg);
      }
    });
  }

  cerrar(): void {
    this.alCerrar.emit();
  }
}
