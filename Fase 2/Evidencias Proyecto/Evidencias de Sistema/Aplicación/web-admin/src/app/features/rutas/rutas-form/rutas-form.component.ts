import { Component, OnInit, computed, effect, signal, untracked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { RutasService, Ruta } from '../../../core/services/rutas.service';
import { ColegioService, Colegio, Sede, sedeUnicaOculta } from '../../../core/services/colegio.service';
import { ConductorService, Conductor } from '../../../core/services/conductor.service';
import { FurgonesService, Furgon } from '../../../core/services/furgones.service';
import { EstudianteService, Estudiante } from '../../../core/services/estudiante.service';

@Component({
  selector: 'app-rutas-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './rutas-form.component.html',
  styleUrl: './rutas-form.component.scss'
})
export class RutasFormComponent implements OnInit {
  rutaForm: FormGroup;
  isEditMode = signal(false);
  rutaId = signal<string | null>(null);
  guardando = signal(false);
  cargando = signal(true);
  errorMensaje = signal('');
  /** Con el recorrido en curso el formulario queda solo para mirar. */
  rutaEnCurso = signal(false);
  colegios = signal<Colegio[]>([]);
  sedes = signal<Sede[]>([]);
  /** Colegio de una sola sede: se usa sin mostrar el selector. */
  sedeOculta = computed(() => sedeUnicaOculta(this.sedes()));
  conductores = signal<Conductor[]>([]);
  furgones = signal<Furgon[]>([]);
  estudiantes = signal<Estudiante[]>([]);

  constructor(
    private fb: FormBuilder,
    private route: ActivatedRoute,
    private router: Router,
    private rutasService: RutasService,
    private colegioService: ColegioService,
    private conductorService: ConductorService,
    private furgonesService: FurgonesService,
    private estudianteService: EstudianteService
  ) {
    this.rutaForm = this.fb.group({
      nombre: ['', Validators.required],
      colegio: [null, Validators.required],
      sede: [null, Validators.required],
      // Pueden quedar en blanco (por ejemplo, para intercambiar furgones); sin ellos la ruta no se puede iniciar.
      conductor_id: [null],
      furgon: [null],
      estudiantes: [[]],
      sentido: ['hacia_colegio', Validators.required],
      hora_programada: [null, Validators.required],
      estado: ['activa', Validators.required]
    });

    // Al cambiar la sede se quitan los estudiantes elegidos que son de otra sede.
    this.rutaForm.get('sede')?.valueChanges.subscribe(sede => {
      const sedeId = Number(sede);
      if (!sedeId) return;
      const deOtraSede = new Set(
        this.estudiantes().filter(e => e.sede && e.sede !== sedeId).map(e => e.id)
      );
      const actuales = this.estudiantesSeleccionados();
      const quedan = actuales.filter(id => !deOtraSede.has(id));
      if (quedan.length !== actuales.length) this.rutaForm.get('estudiantes')?.setValue(quedan);
    });

    // Ruta nueva: el colegio del formulario sigue al de arriba y se recargan sus sedes al tiro.
    effect(() => {
      const colegioId = this.colegioService.selectedColegioId();
      untracked(() => {
        const editando = Boolean(this.route.snapshot.paramMap.get('id'));
        if (editando || this.cargando() || !colegioId) return;
        if (Number(this.rutaForm.value.colegio) === colegioId) return;
        if (!this.colegios().some(colegio => colegio.id === colegioId)) return;
        this.rutaForm.patchValue({ colegio: colegioId });
        void this.onColegioChange();
      });
    });
  }

  async ngOnInit(): Promise<void> {
    const id = this.route.snapshot.paramMap.get('id');
    this.isEditMode.set(Boolean(id));
    this.rutaId.set(id);
    try {
      const [colegios, conductores, furgones, estudiantes] = await Promise.all([
        this.colegioService.getColegios(true),
        firstValueFrom(this.conductorService.getConductores()),
        firstValueFrom(this.furgonesService.getFurgones()),
        this.estudianteService.getEstudiantes()
      ]);
      this.colegios.set(colegios);
      this.conductores.set(conductores);
      this.furgones.set(furgones);
      this.estudiantes.set(estudiantes);

      if (id) {
        const ruta = await firstValueFrom(this.rutasService.getRuta(id));
        await this.cargarSedes(ruta.colegio);
        this.rutaForm.patchValue(ruta);
        if (ruta.estado === 'en_ruta') {
          this.rutaEnCurso.set(true);
          this.errorMensaje.set('No se puede editar la ruta mientras está en curso. Espera a que el conductor la finalice.');
        }
      } else {
        const colegioId = this.colegioService.selectedColegioId() ?? colegios[0]?.id ?? null;
        if (colegioId) {
          this.rutaForm.patchValue({ colegio: colegioId });
          await this.cargarSedes(colegioId);
        }
      }
    } catch (error) {
      this.errorMensaje.set('No fue posible cargar los datos necesarios para la ruta.');
    } finally {
      this.cargando.set(false);
    }
  }

  async cargarSedes(colegioId: number): Promise<void> {
    this.sedes.set(await firstValueFrom(this.colegioService.getSedes(colegioId)));
    const unica = this.sedeOculta();
    if (unica) this.rutaForm.patchValue({ sede: unica.id });
  }

  async onColegioChange(): Promise<void> {
    const colegioId = Number(this.rutaForm.value.colegio);
    this.rutaForm.patchValue({ sede: null, conductor_id: null, furgon: null, estudiantes: [] });
    this.sedes.set([]);
    if (colegioId) await this.cargarSedes(colegioId);
  }

  colegioSeleccionado(): Colegio | undefined {
    const id = Number(this.rutaForm.value.colegio);
    return this.colegios().find(colegio => colegio.id === id);
  }

  sedeSeleccionada(): Sede | undefined {
    const sedeId = Number(this.rutaForm.value.sede);
    return this.sedes().find(sede => sede.id === sedeId);
  }

  conductoresDisponibles(): Conductor[] {
    const colegioId = Number(this.rutaForm.value.colegio);
    return this.conductores().filter(c => !c.colegio_id || c.colegio_id === colegioId);
  }

  furgonesDisponibles(): Furgon[] {
    const colegioId = Number(this.rutaForm.value.colegio);
    const sedeId = Number(this.rutaForm.value.sede);
    return this.furgones().filter(f =>
      (!f.colegio || f.colegio === colegioId) &&
      (!sedeId || !f.sede || f.sede === sedeId) &&
      f.estado !== 'mantenimiento'
    );
  }

  estudiantesDisponibles(): Estudiante[] {
    const colegioId = Number(this.rutaForm.value.colegio);
    const sedeId = Number(this.rutaForm.value.sede);
    return this.estudiantes().filter(e =>
      e.colegio === colegioId &&
      // La ruta va a una sede: solo sus estudiantes.
      (!sedeId || !e.sede || e.sede === sedeId) &&
      e.ubicacion_confirmada === true &&
      e.latitud !== null && e.latitud !== undefined &&
      e.longitud !== null && e.longitud !== undefined
    );
  }

  estudiantesSeleccionados(): number[] {
    return (this.rutaForm.get('estudiantes')?.value || []).map(Number);
  }

  estudianteSeleccionado(estudianteId: number): boolean {
    return this.estudiantesSeleccionados().includes(estudianteId);
  }

  alternarEstudiante(estudianteId: number, event: Event): void {
    const seleccionado = (event.target as HTMLInputElement).checked;
    const ids = new Set(this.estudiantesSeleccionados());
    seleccionado ? ids.add(estudianteId) : ids.delete(estudianteId);
    const control = this.rutaForm.get('estudiantes');
    control?.setValue([...ids]);
    control?.markAsDirty();
    control?.markAsTouched();
  }

  todosSeleccionados(): boolean {
    const disponibles = this.estudiantesDisponibles();
    return disponibles.length > 0 && disponibles.every(e => this.estudianteSeleccionado(e.id));
  }

  algunosSeleccionados(): boolean {
    const cantidad = this.estudiantesDisponibles()
      .filter(e => this.estudianteSeleccionado(e.id)).length;
    return cantidad > 0 && cantidad < this.estudiantesDisponibles().length;
  }

  alternarTodos(event: Event): void {
    const seleccionar = (event.target as HTMLInputElement).checked;
    const disponiblesIds = new Set(this.estudiantesDisponibles().map(e => e.id));
    const ids = new Set(this.estudiantesSeleccionados());
    disponiblesIds.forEach(id => seleccionar ? ids.add(id) : ids.delete(id));
    const control = this.rutaForm.get('estudiantes');
    control?.setValue([...ids]);
    control?.markAsDirty();
    control?.markAsTouched();
  }

  onSubmit(): void {
    if (this.rutaForm.invalid) {
      this.rutaForm.markAllAsTouched();
      return;
    }
    this.guardando.set(true);
    this.errorMensaje.set('');
    const value = this.rutaForm.getRawValue();
    const ruta: Ruta = {
      ...value,
      hora_programada: value.hora_programada || null,
      colegio: Number(value.colegio),
      sede: value.sede == null || value.sede === '' ? null : Number(value.sede),
      conductor_id: Number(value.conductor_id),
      furgon: Number(value.furgon),
      estudiantes: (value.estudiantes || []).map(Number)
    };
    const request = this.isEditMode() && this.rutaId()
      ? this.rutasService.actualizarRuta(this.rutaId()!, ruta)
      : this.rutasService.crearRuta(ruta);
    request.subscribe({
      next: () => this.router.navigate(['/rutas']),
      error: error => {
        const detail = error?.error;
        this.errorMensaje.set(
          detail?.message || (detail && typeof detail === 'object'
            ? Object.values(detail).flat().join(' ')
            : 'No fue posible guardar la ruta.')
        );
        this.guardando.set(false);
      }
    });
  }

  cancelar(): void {
    this.router.navigate(['/rutas']);
  }
}
