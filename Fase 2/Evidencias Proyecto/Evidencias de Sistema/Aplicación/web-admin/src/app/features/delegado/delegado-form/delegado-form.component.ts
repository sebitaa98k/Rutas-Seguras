import { Component, signal, OnInit, effect, untracked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { DelegadoService } from '../../../core/services/delegado.service';
import { ColegioService, Sede, sedeUnicaOculta } from '../../../core/services/colegio.service';
import { AuthService } from '../../../core/services/auth.service';

import { avisarPasswordInicial } from '../../../core/utils/password-inicial';

@Component({
  selector: 'app-delegado-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './delegado-form.component.html',
  styleUrl: './delegado-form.component.scss'
})
export class DelegadoFormComponent implements OnInit {
  delegadoForm!: FormGroup;
  // El panel no usa zone.js: con un signal detrás, la pantalla se actualiza sola cuando
  // responde el servidor (antes el botón quedaba "guardando" y el error no aparecía).
  private readonly enviando = signal(false);
  get isSubmitting(): boolean { return this.enviando(); }
  set isSubmitting(valor: boolean) { this.enviando.set(valor); }
  isEditMode = false;
  delegadoId: number | null = null;
  sedes: Sede[] = [];
  sedesCargadas = false;

  /** Se lee con getRawValue porque al editar el control queda deshabilitado. */
  get tipoDelegado(): 'autorizado' | 'sede' {
    return this.delegadoForm?.getRawValue().tipo_delegado;
  }

  /** Colegio de una sola sede: el inspector queda en ella sin mostrar el selector. */
  get sedeOculta(): boolean {
    return !!sedeUnicaOculta(this.sedes);
  }

  get tituloFormulario(): string {
    const esDelegadoColegio = this.tipoDelegado === 'sede';
    if (this.isEditMode) {
      return esDelegadoColegio ? 'Editar delegado del colegio' : 'Editar persona autorizada';
    }
    return esDelegadoColegio ? 'Registrar delegado del colegio' : 'Registrar persona autorizada';
  }

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private route: ActivatedRoute,
    private delegadoService: DelegadoService,
    private colegioService: ColegioService,
    private authService: AuthService
  ) {
    // Delegado nuevo: al cambiar el colegio de arriba se recargan las sedes al tiro.
    effect(() => {
      const colegioId = this.colegioService.selectedColegioId();
      untracked(() => {
        const editando = Boolean(this.route.snapshot.paramMap.get('id'));
        if (editando || this.authService.currentUser()?.colegioId || !this.delegadoForm) return;
        if (colegioId === this.colegioDeLasSedes) return;
        this.delegadoForm.patchValue({ sede_id: null });
        this.cargarSedes();
      });
    });
  }

  ngOnInit(): void {
    this.initForm();
    this.cargarSedes();

    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      this.delegadoId = Number(idParam);
      this.isEditMode = true;
      this.delegadoService.getDelegadoById(this.delegadoId).subscribe({
        next: (delegado) => {
          if (delegado) {
            const colegioDelDelegado = delegado.sedes_responsable?.[0]?.colegio_id;
            if (colegioDelDelegado && colegioDelDelegado !== this.colegioDeLasSedes) {
              this.cargarSedes(colegioDelDelegado);
            }
            this.delegadoForm.patchValue({
              nombre: delegado.first_name || '',
              apellido: delegado.last_name || '',
              rut: delegado.rut,
              correo: delegado.usuario || delegado.email,
              telefono: delegado.telefono
              ,tipo_delegado: delegado.tipo_delegado === 'inspector' || delegado.sedes_responsable?.length
                ? 'sede' : 'autorizado'
              ,sede_id: delegado.sedes_responsable?.[0]?.id || null
            });
            // Una vez creado, el tipo (persona autorizada o delegado del colegio) no se cambia.
            this.delegadoForm.get('tipo_delegado')?.disable();
          }
        },
        error: (err) => console.error('Error al obtener delegado:', err)
      });
    }
  }

  initForm(): void {
    this.delegadoForm = this.fb.group({
      nombre: ['', [Validators.required, Validators.minLength(2)]],
      apellido: ['', [Validators.required, Validators.minLength(2)]],
      rut: ['', [Validators.required]],
      correo: ['', [Validators.required, Validators.email]],
      telefono: ['', [Validators.required]],
      tipo_delegado: ['autorizado', Validators.required]
      ,sede_id: [null]
    });
  }

  /** Colegio cuyas sedes están cargadas (para no recargar lo mismo). */
  private colegioDeLasSedes: number | null = null;

  /** Al editar se pasan las sedes del colegio del propio delegado, no las del filtro de arriba. */
  cargarSedes(colegioDelDelegado?: number | null): void {
    const usuario = this.authService.currentUser();
    const colegioId = colegioDelDelegado || usuario?.colegioId || this.colegioService.selectedColegioId();
    this.colegioDeLasSedes = colegioId ?? null;
    this.sedes = [];
    if (!colegioId) {
      this.sedesCargadas = true;
      return;
    }

    this.colegioService.getSedes(colegioId).subscribe({
      next: (sedes) => {
        this.sedes = sedes || [];
        this.sedesCargadas = true;

        if (this.sedes.length === 0) {
          this.delegadoForm.patchValue({ sede_id: null });
        } else if (this.sedes.length === 1 && !this.delegadoForm.value.sede_id) {
          this.delegadoForm.patchValue({ sede_id: this.sedes[0].id });
        }
      },
      error: (err) => {
        console.error('Error al obtener las sedes:', err);
        this.sedesCargadas = true;
      }
    });
  }

  isFieldInvalid(fieldName: string): boolean {
    const field = this.delegadoForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  onSubmit(): void {
    // Un inspector siempre pertenece a una sede.
    if (this.tipoDelegado === 'sede' && !this.delegadoForm.value.sede_id) {
      alert(this.sedes.length
        ? 'Debe seleccionar la sede del inspector.'
        : 'El colegio no tiene sedes activas: crea una sede antes de registrar a un inspector.');
      return;
    }
    if (this.delegadoForm.invalid) {
      this.delegadoForm.markAllAsTouched();
      return;
    }

    this.isSubmitting = true;

    const formData = {
      nombre: this.delegadoForm.value.nombre.trim(),
      apellido: this.delegadoForm.value.apellido.trim(),
      first_name: this.delegadoForm.value.nombre.trim(),
      last_name: this.delegadoForm.value.apellido.trim(),
      rut: this.delegadoForm.value.rut,
      email: this.delegadoForm.value.correo,
      usuario: this.delegadoForm.value.correo,
      telefono: this.delegadoForm.value.telefono,
      // El backend recibe 'sede' o 'autorizado' (lo traduce a 'inspector').
      tipo_delegado: this.delegadoForm.getRawValue().tipo_delegado
      ,sede_id: this.tipoDelegado === 'sede' ? this.delegadoForm.value.sede_id : null
    };

    if (this.isEditMode && this.delegadoId) {
      this.delegadoService.actualizarDelegado(this.delegadoId, formData).subscribe({
        next: (res) => {
          this.isSubmitting = false;
          alert(res.message || 'Delegado actualizado exitosamente.');
          this.router.navigate(['/delegados']);
        },
        error: (err) => {
          console.error('Error al actualizar delegado:', err);
          this.isSubmitting = false;
          alert(err.error?.message || 'Error al actualizar el delegado.');
        }
      });
    } else {
      this.delegadoService.crearDelegado(formData as any).subscribe({
        next: (res: any) => {
          this.isSubmitting = false;
          avisarPasswordInicial(res);
          this.router.navigate(['/delegados']);
        },
        error: (err) => {
          console.error('Error al crear delegado:', err);
          this.isSubmitting = false;
          let msg = 'Error al registrar el delegado.';
          if (err.error?.errors) {
            const firstKey = Object.keys(err.error.errors)[0];
            msg = Array.isArray(err.error.errors[firstKey]) ? err.error.errors[firstKey][0] : err.error.errors[firstKey];
          } else if (err.error?.message) {
            msg = err.error.message;
          }
          alert(msg);
        }
      });
    }
  }

  onCancel(): void {
    this.router.navigate(['/delegados']);
  }
}
