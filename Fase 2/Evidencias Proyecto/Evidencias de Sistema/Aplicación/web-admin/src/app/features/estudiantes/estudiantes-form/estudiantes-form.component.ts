import { Component, OnInit, computed, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { EstudianteService } from '../../../core/services/estudiante.service';
import { ApoderadoService } from '../../../core/services/apoderado.service';
import { ColegioService, Colegio, Sede, sedeUnicaOculta } from '../../../core/services/colegio.service';
import { AuthService } from '../../../core/services/auth.service';
import { REGION_METROPOLITANA } from '../../../shared/chile-territorio';
import { CURSOS, cursosCon } from '../../../shared/cursos';
import { SelectorUbicacionComponent, UbicacionSeleccionada } from '../../../shared/selector-ubicacion/selector-ubicacion.component';

@Component({
  selector: 'app-estudiantes-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, SelectorUbicacionComponent],
  templateUrl: './estudiantes-form.component.html',
  styleUrl: './estudiantes-form.component.scss'
})
export class EstudiantesFormComponent implements OnInit {
  cursos: string[] = CURSOS;
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private estudianteService = inject(EstudianteService);
  private apoderadoService = inject(ApoderadoService);
  private colegioService = inject(ColegioService);
  private authService = inject(AuthService);

  estudianteForm!: FormGroup;
  // El panel no usa zone.js: con un signal detrás, la pantalla se actualiza sola cuando
  // responde el servidor (antes el botón quedaba "guardando" y el error no aparecía).
  private readonly enviando = signal(false);
  get isSubmitting(): boolean { return this.enviando(); }
  set isSubmitting(valor: boolean) { this.enviando.set(valor); }
  isEditMode = false;
  estudianteId: number | null = null;
  private readonly mensajeError = signal('');
  get errorMessage(): string { return this.mensajeError(); }
  set errorMessage(valor: string) {
    this.mensajeError.set(valor);
    // El aviso está arriba del formulario: se lleva la vista hasta él.
    if (valor) setTimeout(() => document.querySelector('.alert-danger')?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  }

  apoderados = signal<any[]>([]);
  /** Ventana "¿Es el apoderado correcto?" antes de guardar. */
  confirmandoApoderado = signal(false);
  /** Apoderado con que se cargó el estudiante (al editar): si cambia, también se confirma. */
  private apoderadoOriginal: number | null = null;
  sedes = signal<Sede[]>([]);
  /** Colegio de una sola sede: se usa sin mostrar el selector. */
  sedeOculta = computed(() => sedeUnicaOculta(this.sedes()));
  colegios = signal<Colegio[]>([]);
  cargandoSedes = signal(false);
  errorSedes = signal('');
  personasAutorizadas = signal<{ nombre: string; rut: string }[]>([]);
  inspectores = signal<string[]>([]);

  user = this.authService.currentUser;
  esAdminPlataforma = signal(false);

  ngOnInit(): void {
    const u = this.user();
    this.esAdminPlataforma.set(u?.role === 'ADMIN_PLATAFORMA' || u?.role === 'ADMIN');

    this.initForm();
    this.cargarApoderados();

    if (this.esAdminPlataforma()) {
      this.cargarColegios();
    } else if (u?.colegioId) {
      this.cargarSedes(u.colegioId);
    }

    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      this.estudianteId = Number(idParam);
      this.isEditMode = true;
      this.cargarEstudiante(this.estudianteId);
    }
  }

  initForm(): void {
    this.estudianteForm = this.fb.group({
      nombre: ['', [Validators.required, Validators.minLength(2)]],
      apellido: ['', [Validators.required, Validators.minLength(2)]],
      rut: ['', [Validators.required]],
      fecha_nacimiento: ['', Validators.required],
      colegio: [null, this.esAdminPlataforma() ? Validators.required : []],
      sede: [null, Validators.required],
      curso: ['', Validators.required],
      direccion_principal: ['', Validators.required],
      comuna: ['', Validators.required],
      region: [REGION_METROPOLITANA, Validators.required],
      // La casa debe quedar marcada en el mapa: el conductor la usa como parada.
      latitud: [null, Validators.required],
      longitud: [null],
      ubicacion_confirmada: [false],
      apoderado: [null, Validators.required]
    });
  }

  cargarApoderados(): void {
    this.apoderadoService.getApoderados().subscribe({
      next: (data) => this.apoderados.set(data || []),
      error: (err) => console.error('Error al cargar apoderados:', err)
    });
  }

  async cargarColegios(): Promise<void> {
    try {
      const data = await this.colegioService.getColegios(true);
      this.colegios.set(data || []);
    } catch (err) {
      console.error('Error al cargar colegios:', err);
    }
  }

  cargarSedes(colegioId: number): void {
    this.cargandoSedes.set(true);
    this.errorSedes.set('');
    this.sedes.set([]);
    this.colegioService.getSedes(colegioId).subscribe({
      next: (data) => {
        this.sedes.set(data || []);
        const unica = this.sedeOculta();
        if (unica) this.estudianteForm.patchValue({ sede: unica.id });
        this.cargandoSedes.set(false);
      },
      error: (err) => {
        console.error('Error al cargar sedes:', err);
        this.sedes.set([]);
        this.cargandoSedes.set(false);
        this.errorSedes.set('No fue posible cargar las sedes del colegio seleccionado.');
      }
    });
  }

  onColegioChange(): void {
    const colId = Number(this.estudianteForm.get('colegio')?.value);
    this.estudianteForm.patchValue({ sede: null });
    this.sedes.set([]);
    this.errorSedes.set('');
    if (Number.isInteger(colId) && colId > 0) {
      this.cargarSedes(colId);
    }
  }

  cargarEstudiante(id: number): void {
    this.estudianteService.getEstudianteById(id).subscribe({
      next: (est) => {
        if (est) {
          this.cursos = cursosCon(est.curso);
          this.estudianteForm.patchValue({
            nombre: est.nombre,
            apellido: est.apellido,
            rut: est.rut,
            fecha_nacimiento: est.fecha_nacimiento || '',
            colegio: est.colegio || null,
            sede: est.sede || null,
            curso: est.curso || '',
            direccion_principal: est.direccion_principal || '',
            comuna: est.comuna || '',
            region: est.region || '',
            latitud: est.latitud ?? null,
            longitud: est.longitud ?? null,
            ubicacion_confirmada: !!est.ubicacion_confirmada,
            direccion_alternativa: est.direccion_alternativa || '',
            apoderado: est.apoderado || null
          });
          this.apoderadoOriginal = est.apoderado || null;
          this.personasAutorizadas.set(est.personas_autorizadas || []);
          this.inspectores.set(est.inspectores || []);

          if (est.colegio) {
            this.cargarSedes(est.colegio);
          }
        }
      },
      error: (err) => {
        console.error('Error al cargar estudiante:', err);
        this.errorMessage = 'No se pudo cargar la información del estudiante.';
      }
    });
  }

  ubicacionCambio(ubicacion: UbicacionSeleccionada): void {
    this.estudianteForm.patchValue({
      direccion_principal: ubicacion.direccion,
      comuna: ubicacion.comuna,
      region: ubicacion.region,
      latitud: ubicacion.latitud,
      longitud: ubicacion.longitud,
      ubicacion_confirmada: ubicacion.latitud != null && ubicacion.longitud != null,
    });
    ['direccion_principal', 'comuna', 'region'].forEach(campo => this.estudianteForm.get(campo)?.markAsTouched());
  }

  /** Centra el mapa manual en la sede (o el colegio) del estudiante si tiene coordenadas. */
  get puntoReferencia(): { latitud?: number | string | null; longitud?: number | string | null } | undefined {
    const sedeId = Number(this.estudianteForm.get('sede')?.value);
    const sede = this.sedes().find(s => s.id === sedeId);
    if (sede?.latitud != null && sede?.longitud != null) return sede;
    const colegioId = Number(this.estudianteForm.get('colegio')?.value || this.user()?.colegioId);
    return this.colegios().find(c => c.id === colegioId);
  }

  get apoderadoElegido(): any {
    const id = this.estudianteForm.get('apoderado')?.value;
    return this.apoderados().find(apoderado => (apoderado.perfil_id || apoderado.id) === id);
  }

  isFieldInvalid(fieldName: string): boolean {
    const field = this.estudianteForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  onSubmit(): void {
    this.errorMessage = '';

    if (this.estudianteForm.invalid) {
      this.estudianteForm.markAllAsTouched();
      return;
    }

    // Al crear (o al cambiarle el apoderado) se pide confirmar que es el apoderado correcto.
    const apoderadoActual = this.estudianteForm.get('apoderado')?.value;
    if (!this.isEditMode || apoderadoActual !== this.apoderadoOriginal) {
      this.confirmandoApoderado.set(true);
      return;
    }
    this.enviar();
  }

  confirmarApoderado(): void {
    this.confirmandoApoderado.set(false);
    this.enviar();
  }

  revisarApoderado(): void {
    this.confirmandoApoderado.set(false);
    setTimeout(() => document.getElementById('apoderado')?.focus());
  }

  private enviar(): void {
    this.isSubmitting = true;
    const val = { ...this.estudianteForm.value };

    // Limpiar nulos/vacíos (las coordenadas se envían en null para poder quitarlas)
    Object.keys(val).forEach(k => {
      if (k === 'latitud' || k === 'longitud') return;
      if (val[k] === '' || val[k] === null) {
        delete val[k];
      }
    });

    if (this.isEditMode && this.estudianteId) {
      this.estudianteService.updateEstudiante(this.estudianteId, val).subscribe({
        next: () => {
          this.isSubmitting = false;
          this.router.navigate(['/estudiantes']);
        },
        error: (err) => {
          this.isSubmitting = false;
          this.errorMessage = this.extraerError(err);
        }
      });
    } else {
      this.estudianteService.createEstudiante(val).subscribe({
        next: () => {
          this.isSubmitting = false;
          this.router.navigate(['/estudiantes']);
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
        return Array.isArray(first) ? `${keys[0]}: ${first[0]}` : `${keys[0]}: ${first}`;
      }
    }
    return 'Ocurrió un error al guardar los datos del estudiante.';
  }

  onCancel(): void {
    this.router.navigate(['/estudiantes']);
  }
}
