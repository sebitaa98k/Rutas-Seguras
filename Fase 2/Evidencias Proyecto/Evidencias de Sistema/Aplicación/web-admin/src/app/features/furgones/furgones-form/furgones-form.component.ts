import { Component, OnInit, computed, effect, signal, untracked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { FurgonesService, Furgon } from '../../../core/services/furgones.service';
import { ColegioService, Sede, sedeUnicaOculta } from '../../../core/services/colegio.service';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-furgones-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './furgones-form.component.html',
  styleUrl: './furgones-form.component.scss'
})
export class FurgonesFormComponent implements OnInit {
  furgonForm: FormGroup;
  isEditMode = signal(false);
  furgonId = signal<string | null>(null);
  colegioFurgon = signal<number | undefined>(undefined);
  guardando = signal(false);
  cargandoSedes = signal(true);
  sedes = signal<Sede[]>([]);
  /** Colegio de una sola sede: se usa sin mostrar el selector. */
  sedeOculta = computed(() => sedeUnicaOculta(this.sedes()));
  errorMensaje = signal('');

  constructor(
    private fb: FormBuilder,
    private route: ActivatedRoute,
    private router: Router,
    private furgonesService: FurgonesService,
    private colegioService: ColegioService,
    private authService: AuthService
  ) {
    this.furgonForm = this.fb.group({
      patente: ['', [Validators.required, Validators.pattern(/^[A-Z0-9-]{6,8}$/i)]],
      marcaModelo: ['', Validators.required],
      capacidad: ['', [Validators.required, Validators.min(1)]],
      sede: [null, Validators.required],
      estado: ['disponible', Validators.required]
    });

    // Furgón nuevo: si el admin de plataforma cambia el colegio de arriba, se recargan las sedes al tiro.
    effect(() => {
      const colegioId = this.colegioService.selectedColegioId();
      untracked(() => this.alCambiarColegioDelFiltro(colegioId));
    });
  }

  private alCambiarColegioDelFiltro(colegioId: number | null): void {
    const editando = Boolean(this.route.snapshot.paramMap.get('id'));
    if (editando || this.authService.currentUser()?.colegioId) return;
    if ((colegioId ?? undefined) === this.colegioFurgon()) return;
    this.furgonForm.patchValue({ sede: null });
    this.cargarSedes();
  }

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      // Al editar, las sedes se cargan con el colegio del propio furgón (ver cargarFurgon).
      this.isEditMode.set(true);
      this.furgonId.set(id);
      this.cargarFurgon(id);
    } else {
      this.cargarSedes();
    }
  }

  /**
   * Sedes donde puede quedar el furgón. Al editar se usan las de SU colegio: el admin de
   * plataforma puede tener otro colegio (o ninguno) elegido en el filtro de arriba.
   */
  cargarSedes(colegioDelFurgon?: number): void {
    const colegioId = colegioDelFurgon
      || this.authService.currentUser()?.colegioId
      || this.colegioService.selectedColegioId();
    this.errorMensaje.set('');
    if (!colegioId) {
      this.colegioFurgon.set(undefined);
      this.sedes.set([]);
      this.cargandoSedes.set(false);
      this.errorMensaje.set('Elige un colegio en el selector de arriba a la derecha para registrar el furgón.');
      return;
    }
    this.colegioFurgon.set(colegioId);
    this.cargandoSedes.set(true);
    this.colegioService.getSedes(colegioId).subscribe({
      next: sedes => {
        this.sedes.set(sedes || []);
        const unica = this.sedeOculta();
        if (unica) this.furgonForm.patchValue({ sede: unica.id });
        this.cargandoSedes.set(false);
      },
      error: error => {
        console.error('Error al cargar sedes:', error);
        this.sedes.set([]);
        this.cargandoSedes.set(false);
        this.errorMensaje.set('No fue posible cargar las sedes del colegio.');
      }
    });
  }

  cargarFurgon(id: string): void {
    this.furgonesService.getFurgon(id).subscribe({
      next: (furgon) => {
        if (furgon) {
          this.colegioFurgon.set(furgon.colegio);
          this.cargarSedes(furgon.colegio);
          this.furgonForm.patchValue({
            patente: furgon.patente,
            marcaModelo: furgon.marcaModelo || furgon.marca_modelo || '',
            capacidad: furgon.capacidad,
            sede: furgon.sede ?? null,
            estado: furgon.estado
          });
        }
      },
      error: error => {
        console.error('Error al cargar furgón:', error);
        this.errorMensaje.set('No fue posible cargar el furgón solicitado.');
      }
    });
  }

  onSubmit(): void {
    if (this.furgonForm.invalid) {
      this.furgonForm.markAllAsTouched();
      return;
    }

    this.guardando.set(true);
    this.errorMensaje.set('');
    const formVal = this.furgonForm.value;
    const furgonData: Furgon = {
      patente: formVal.patente,
      marcaModelo: formVal.marcaModelo,
      capacidad: Number(formVal.capacidad),
      estado: formVal.estado,
      sede: formVal.sede,
      colegio: this.sedes().find(sede => sede.id === formVal.sede)?.colegio ?? this.colegioFurgon()
    };

    if (this.isEditMode() && this.furgonId()) {
      this.furgonesService.actualizarFurgon(this.furgonId()!, furgonData).subscribe({
        next: () => {
          this.guardando.set(false);
          this.router.navigate(['/furgones']);
        },
        error: (error) => {
          this.guardando.set(false);
          this.errorMensaje.set(this.extraerError(error));
        }
      });
    } else {
      this.furgonesService.crearFurgon(furgonData).subscribe({
        next: () => {
          this.guardando.set(false);
          this.router.navigate(['/furgones']);
        },
        error: (error) => {
          this.guardando.set(false);
          this.errorMensaje.set(this.extraerError(error));
        }
      });
    }
  }

  private extraerError(error: any): string {
    const detalle = error?.error;
    if (detalle?.message || detalle?.detail) {
      return detalle.message || detalle.detail;
    }
    if (detalle && typeof detalle === 'object') {
      const campo = Object.keys(detalle)[0];
      if (campo) {
        const valor = detalle[campo];
        return Array.isArray(valor) ? `${campo}: ${valor[0]}` : `${campo}: ${valor}`;
      }
    }
    return 'No fue posible guardar el furgón.';
  }

  cancelar(): void {
    this.router.navigate(['/furgones']);
  }
}
