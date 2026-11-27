import { Component, signal, OnInit, effect, untracked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { ConductorService } from '../../../core/services/conductor.service';
import { AuthService } from '../../../core/services/auth.service';
import { Colegio, ColegioService } from '../../../core/services/colegio.service';

import { avisarPasswordInicial } from '../../../core/utils/password-inicial';

@Component({
  selector: 'app-conductor-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './conductor-form.component.html',
  styleUrl: './conductor-form.component.scss'
})
export class ConductorFormComponent implements OnInit {
  conductorForm!: FormGroup;
  // El panel no usa zone.js: con un signal detrás, la pantalla se actualiza sola cuando
  // responde el servidor (antes el botón quedaba "guardando" y el error no aparecía).
  private readonly enviando = signal(false);
  get isSubmitting(): boolean { return this.enviando(); }
  set isSubmitting(valor: boolean) { this.enviando.set(valor); }
  isEditMode = false;
  conductorId: number | null = null;
  private readonly mensajeError = signal('');
  get errorMessage(): string { return this.mensajeError(); }
  set errorMessage(valor: string) {
    this.mensajeError.set(valor);
    // El aviso está arriba del formulario: se lleva la vista hasta él.
    if (valor) setTimeout(() => document.querySelector('.alert-danger')?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  }
  esAdminPlataforma = false;
  colegios: Colegio[] = [];
  cargandoColegios = false;

  // Solo las clases que habilitan para conducir transporte escolar.
  licenciasDisponibles = ['Clase A1 (antigua)', 'Clase A3'];

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private route: ActivatedRoute,
    private conductorService: ConductorService,
    private authService: AuthService,
    private colegioService: ColegioService
  ) {
    // Conductor nuevo: el colegio del formulario sigue al de arriba.
    effect(() => {
      const colegioId = this.colegioService.selectedColegioId();
      untracked(() => {
        const editando = Boolean(this.route.snapshot.paramMap.get('id'));
        if (editando || !this.conductorForm || !colegioId) return;
        if (this.colegios.some(colegio => colegio.id === colegioId)) {
          this.conductorForm.patchValue({ colegio_id: colegioId });
        }
      });
    });
  }

  ngOnInit(): void {
    const usuario = this.authService.currentUser();
    this.esAdminPlataforma = usuario?.role === 'ADMIN_PLATAFORMA' || usuario?.role === 'ADMIN';

    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      this.conductorId = Number(idParam);
      this.isEditMode = true;
    }

    // El modo debe resolverse antes de crear el formulario. De lo contrario,
    // la contraseña queda marcada como obligatoria también al editar y se
    // termina reemplazando una credencial que el administrador no quería cambiar.
    this.initForm();

    if (this.esAdminPlataforma) {
      void this.cargarColegios();
    }

    if (this.isEditMode && this.conductorId) {
      this.cargarConductor(this.conductorId);
    }
  }

  initForm(): void {
    this.conductorForm = this.fb.group({
      nombre: ['', [Validators.required, Validators.minLength(2)]],
      apellido: ['', [Validators.required, Validators.minLength(2)]],
      rut: ['', [Validators.required, Validators.pattern('^[0-9]{7,8}-[0-9kK]{1}$')]],
      telefono: ['', [Validators.required]],
      licencia_conducir: ['', [Validators.required]],
      email: ['', [Validators.required, Validators.email]],
      colegio_id: [null, this.esAdminPlataforma ? [Validators.required] : []]
    });
  }

  async cargarColegios(): Promise<void> {
    this.cargandoColegios = true;
    try {
      this.colegios = await this.colegioService.getColegios(true);
      if (!this.isEditMode && !this.conductorForm.get('colegio_id')?.value) {
        const contexto = this.colegioService.selectedColegioId();
        if (contexto && this.colegios.some(colegio => colegio.id === contexto)) {
          this.conductorForm.patchValue({ colegio_id: contexto });
        }
      }
    } catch (error) {
      console.error('Error al cargar colegios:', error);
      this.errorMessage = 'No fue posible cargar los colegios disponibles.';
    } finally {
      this.cargandoColegios = false;
    }
  }

  cargarConductor(id: number): void {
    this.conductorService.getConductorById(id).subscribe({
      next: (conductor) => {
        if (conductor) {
          // Un conductor antiguo puede tener otra clase guardada: se muestra igual para no perderla.
          if (conductor.licencia_conducir && !this.licenciasDisponibles.includes(conductor.licencia_conducir)) {
            this.licenciasDisponibles = [...this.licenciasDisponibles, conductor.licencia_conducir];
          }
          this.conductorForm.patchValue({
            nombre: conductor.first_name || '',
            apellido: conductor.last_name || '',
            rut: conductor.rut,
            telefono: conductor.telefono,
            licencia_conducir: conductor.licencia_conducir,
            email: conductor.email,
            colegio_id: conductor.colegio_id || null
          });
        }
      },
      error: (err) => {
        console.error('Error al cargar conductor:', err);
        this.errorMessage = 'No se pudo cargar la información del conductor.';
      }
    });
  }

  isFieldInvalid(fieldName: string): boolean {
    const field = this.conductorForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  onSubmit(): void {
    this.errorMessage = '';

    if (this.conductorForm.invalid) {
      this.conductorForm.markAllAsTouched();
      return;
    }

    this.isSubmitting = true;

    const val = this.conductorForm.value;
    const nombre = val.nombre.trim();
    const apellido = val.apellido.trim();

    if (this.isEditMode && this.conductorId) {
      // Edición
      const updatePayload: any = {
        first_name: nombre,
        last_name: apellido,
        rut: val.rut.trim(),
        telefono: val.telefono.trim(),
        licencia_conducir: val.licencia_conducir,
        email: val.email.trim(),
        ...(this.esAdminPlataforma ? { colegio_id: Number(val.colegio_id) } : {})
      };


      this.conductorService.actualizarConductor(this.conductorId, updatePayload).subscribe({
        next: () => {
          this.isSubmitting = false;
          this.router.navigate(['/conductores']);
        },
        error: (err) => {
          this.isSubmitting = false;
          this.errorMessage = this.extraerError(err);
        }
      });
    } else {
      // Creación en backend Django
      const createPayload = {
        nombre: nombre,
        apellido: apellido,
        rut: val.rut.trim(),
        email: val.email.trim(),
        telefono: val.telefono.trim(),
        licencia_conducir: val.licencia_conducir,
        ...(this.esAdminPlataforma ? { colegio_id: Number(val.colegio_id) } : {})
      };

      this.conductorService.crearConductor(createPayload as any).subscribe({
        next: (res: any) => {
          this.isSubmitting = false;
          avisarPasswordInicial(res);
          this.router.navigate(['/conductores']);
        },
        error: (err) => {
          this.isSubmitting = false;
          this.errorMessage = this.extraerError(err);
        }
      });
    }
  }

  private extraerError(err: any): string {
    if (err?.error?.message) {
      return err.error.message;
    }
    if (err?.error?.errors) {
      const keys = Object.keys(err.error.errors);
      if (keys.length > 0) {
        const first = err.error.errors[keys[0]];
        return Array.isArray(first) ? first[0] : first;
      }
    }
    return 'Ocurrió un error al guardar los datos en el servidor.';
  }

  onCancel(): void {
    this.router.navigate(['/conductores']);
  }
}
