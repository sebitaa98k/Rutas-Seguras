import { Component, signal, OnInit, effect, untracked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { ApoderadoService, Estudiante } from '../../../core/services/apoderado.service';
import { ColegioService, Sede, sedeUnicaOculta } from '../../../core/services/colegio.service';
import { AuthService } from '../../../core/services/auth.service';
import { REGION_METROPOLITANA } from '../../../shared/chile-territorio';
import { CURSOS } from '../../../shared/cursos';
import { SelectorUbicacionComponent, UbicacionSeleccionada } from '../../../shared/selector-ubicacion/selector-ubicacion.component';

import { avisarPasswordInicial } from '../../../core/utils/password-inicial';

@Component({
  selector: 'app-apoderado-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, SelectorUbicacionComponent],
  templateUrl: './apoderado-form.component.html',
  styleUrl: './apoderado-form.component.scss'
})
export class ApoderadoFormComponent implements OnInit {
  readonly cursos = CURSOS;
  apoderadoForm!: FormGroup;
  estudianteForm!: FormGroup;
  
  // El panel no usa zone.js: con un signal detrás, la pantalla se actualiza sola cuando
  // responde el servidor (antes el botón quedaba "guardando" y el error no aparecía).
  private readonly enviando = signal(false);
  get isSubmitting(): boolean { return this.enviando(); }
  set isSubmitting(valor: boolean) { this.enviando.set(valor); }
  isEditMode = false;
  apoderadoId: number | null = null;

  // Lista temporal de estudiantes asociados al apoderado
  estudiantesList: Estudiante[] = [];
  showEstudianteModal = false;
  sedes: Sede[] = [];

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private route: ActivatedRoute,
    private apoderadoService: ApoderadoService,
    private colegioService: ColegioService,
    private authService: AuthService
  ) {
    // Apoderado nuevo: al cambiar el colegio de arriba se recargan las sedes para sus hijos.
    effect(() => {
      const colegioId = this.colegioService.selectedColegioId();
      untracked(() => {
        const editando = Boolean(this.route.snapshot.paramMap.get('id'));
        if (editando || this.authService.currentUser()?.colegioId) return;
        if (colegioId === this.colegioDeLasSedes) return;
        this.cargarSedes();
      });
    });
  }

  ngOnInit(): void {
    this.initApoderadoForm();
    this.cargarSedes();
    this.initEstudianteForm();

    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      this.apoderadoId = Number(idParam);
      this.isEditMode = true;
      this.apoderadoService.getApoderadoById(this.apoderadoId).subscribe({
        next: (apoderado) => {
          if (apoderado) {
            this.apoderadoForm.patchValue({
              ...apoderado,
              nombre: apoderado.first_name || '',
              apellido: apoderado.last_name || ''
            });
            this.estudiantesList = apoderado.estudiantes ? [...apoderado.estudiantes] : [];
          }
        },
        error: (err) => console.error('Error al obtener apoderado:', err)
      });
    }
  }

initApoderadoForm(): void {
  this.apoderadoForm = this.fb.group({
    correo: ['', [
      Validators.required,
      Validators.email
    ]],

    rut: ['', [
      Validators.required,
      Validators.pattern('^[0-9]{7,8}-[0-9kK]{1}$')
    ]],

    nombre: ['', [Validators.required, Validators.minLength(2)]],
    apellido: ['', [Validators.required, Validators.minLength(2)]],

    telefono: ['', [
      Validators.required,
      Validators.pattern(
        '^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\\s\\./0-9]*$'
      )
    ]]
  });
}

  initEstudianteForm(): void {
    this.estudianteForm = this.fb.group({
      rut: ['', [Validators.required, Validators.pattern('^[0-9]{7,8}-[0-9kK]{1}$')]],
      nombre: ['', [Validators.required, Validators.minLength(2)]],
      apellido: ['', [Validators.required, Validators.minLength(2)]],
      fecha_nacimiento: ['', [Validators.required]],
      curso: ['', [Validators.required]],
      sede: [null, [Validators.required]],
      direccion_retiro: ['', [Validators.required]],
      comuna: ['', [Validators.required]],
      region: ['', [Validators.required]],
      latitud: [null, [Validators.required]],
      longitud: [null],
      estado_matricula: ['pendiente', [Validators.required]],
      activo: [true]
    });
  }

  isFieldInvalid(form: FormGroup, fieldName: string): boolean {
    const field = form.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  ubicacionRetiroCambio(ubicacion: UbicacionSeleccionada): void {
    this.estudianteForm.patchValue({
      direccion_retiro: ubicacion.direccion,
      comuna: ubicacion.comuna,
      region: ubicacion.region,
      latitud: ubicacion.latitud,
      longitud: ubicacion.longitud,
    });
    this.estudianteForm.get('direccion_retiro')?.markAsTouched();
  }

  // Métodos del Modal de Estudiantes
  openEstudianteModal(): void {
    this.estudianteForm.reset({
      region: REGION_METROPOLITANA,
      estado_matricula: 'pendiente',
      activo: true,
      // Colegio de una sola sede: el hijo queda en ella sin elegirla.
      sede: sedeUnicaOculta(this.sedes)?.id ?? null
    });
    this.showEstudianteModal = true;
  }

  closeEstudianteModal(): void {
    this.showEstudianteModal = false;
  }

  /** Sedes del colegio que se administra: cada hijo queda en una. */
  /** Colegio cuyas sedes están cargadas (para no recargar lo mismo). */
  private colegioDeLasSedes: number | null = null;

  cargarSedes(): void {
    const colegioId = this.authService.currentUser()?.colegioId || this.colegioService.selectedColegioId();
    this.colegioDeLasSedes = colegioId ?? null;
    this.sedes = [];
    if (!colegioId) return;
    this.colegioService.getSedes(colegioId).subscribe({
      next: (sedes) => (this.sedes = sedes || []),
      error: (err) => console.error('Error al cargar las sedes:', err)
    });
  }

  nombreSede(id: number | null | undefined): string {
    return this.sedes.find(sede => sede.id === id)?.nombre || '';
  }

  /** Colegio de una sola sede: no se muestra ni se pide la sede de los hijos. */
  get sedeOculta(): boolean {
    return !!sedeUnicaOculta(this.sedes);
  }

  addEstudiante(): void {
    if (this.estudianteForm.invalid) {
      this.estudianteForm.markAllAsTouched();
      return;
    }

    const newEstudiante: Estudiante = {
      ...this.estudianteForm.value,
      id: Date.now()
    };

    this.estudiantesList.push(newEstudiante);
    this.closeEstudianteModal();
  }

  removeEstudiante(index: number): void {
    this.estudiantesList.splice(index, 1);
  }

  // Guardar Apoderado + Estudiantes
  onSubmit(): void {
  if (this.apoderadoForm.invalid) {
    this.apoderadoForm.markAllAsTouched();
    return;
  }

  this.isSubmitting = true;

  const formData = {
    nombre: this.apoderadoForm.value.nombre.trim(),
    apellido: this.apoderadoForm.value.apellido.trim(),
    first_name: this.apoderadoForm.value.nombre.trim(),
    last_name: this.apoderadoForm.value.apellido.trim(),
    rut: this.apoderadoForm.value.rut,
    usuario: this.apoderadoForm.value.correo,
    telefono: this.apoderadoForm.value.telefono,
    // En creación el backend guarda apoderado e hijos en una sola transacción.
    // Los ids de esta lista son solamente temporales y no se envían.
    estudiantes: this.estudiantesList.map(({ id, ...estudiante }) => estudiante)
  };

  if (this.isEditMode && this.apoderadoId) {
    this.apoderadoService.actualizarApoderado(
      this.apoderadoId,
      formData
    ).subscribe({
      next: () => {
        this.isSubmitting = false;
        this.router.navigate(['/apoderados']);
      },
      error: (err) => {
        console.error('Error al actualizar apoderado:', err);
        this.isSubmitting = false;
        alert(
          err.error?.message ||
          'Error al actualizar el apoderado.'
        );
      }
    });

  } else {
    this.crear(formData);
  }
}

  /** Crea al apoderado o, si su RUT ya tiene cuenta en otro colegio, ofrece vincularlo a este. */
  private crear(formData: any): void {
    this.apoderadoService.crearApoderado(formData).subscribe({
      next: (response) => {
        this.isSubmitting = false;
        if (response?.vinculado) {
          alert(response.message);
        } else {
          avisarPasswordInicial(response);
        }
        this.router.navigate(['/apoderados']);
      },
      error: (err) => {
        console.error('❌ ERROR AL CREAR APODERADO:', err);

        const existente = err.status === 409 ? err.error?.apoderado_existente : null;
        if (existente && !formData.vincular) {
          const vincular = confirm(
            `${err.error.message}

${existente.nombre} · ${existente.email}

` +
            '¿Vincularlo a este colegio? No se crea otra cuenta ni se cambia su contraseña.'
          );
          if (vincular) {
            this.crear({ ...formData, vincular: true });
            return;
          }
        }

        this.isSubmitting = false;

        // Primero el mensaje claro del servidor (ej. "Elige un colegio…"); el detalle técnico solo si no hay.
        alert(
          err.error?.message && err.error.message !== 'Error al registrar el apoderado.'
            ? err.error.message
            : err.error?.errors
              ? JSON.stringify(err.error.errors)
              : err.error?.message || 'Error al crear el apoderado.'
        );
      }
    });
  }

  onCancel(): void {
    this.router.navigate(['/apoderados']);
  }
}
