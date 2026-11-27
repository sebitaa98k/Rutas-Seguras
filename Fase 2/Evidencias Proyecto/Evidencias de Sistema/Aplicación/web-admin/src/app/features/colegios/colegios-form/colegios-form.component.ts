import { Component, OnInit, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ColegioService, Colegio, PLANES_COLEGIO, PlanColegio } from '../../../core/services/colegio.service';
import { AuthService } from '../../../core/services/auth.service';
import { REGION_METROPOLITANA } from '../../../shared/chile-territorio';
import { SelectorUbicacionComponent, UbicacionSeleccionada } from '../../../shared/selector-ubicacion/selector-ubicacion.component';

@Component({
  selector: 'app-colegios-form',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule, SelectorUbicacionComponent],
  templateUrl: './colegios-form.component.html',
  styleUrl: './colegios-form.component.scss'
})
export class ColegiosFormComponent implements OnInit {
  private colegioService = inject(ColegioService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private authService = inject(AuthService);

  /** El administrador de un colegio solo actualiza el teléfono y el correo de contacto. */
  readonly soloContacto = this.authService.currentUser()?.role === 'ADMIN_COLEGIO';
  readonly rutaVolver = this.soloContacto ? '/mi-colegio' : '/colegios';

  esEdicion = signal(false);
  colegioId = signal<number | null>(null);
  guardando = signal(false);
  readonly planes = PLANES_COLEGIO;
  /** Plan guardado, para avisar antes de dejar de ser multisede. */
  planOriginal = signal<PlanColegio>('basico');

  formData = signal<Partial<Colegio>>({
    nombre: '',
    rbd: '',
    direccion: '',
    comuna: '',
    region: REGION_METROPOLITANA,
    latitud: null,
    longitud: null,
    telefono: '',
    email_contacto: '',
    plan: 'basico',
    activo: true
  });

  ngOnInit(): void {
    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      const id = parseInt(idParam, 10);
      if (!isNaN(id)) {
        this.esEdicion.set(true);
        this.colegioId.set(id);
        this.cargarColegio(id);
      }
    }
  }

  cargarColegio(id: number): void {
    this.colegioService.getColegio(id).subscribe({
      next: (data) => {
        this.formData.set({
          nombre: data.nombre,
          rbd: data.rbd || '',
          direccion: data.direccion || '',
          comuna: data.comuna || '',
          region: data.region || '',
          latitud: data.latitud ?? null,
          longitud: data.longitud ?? null,
          telefono: data.telefono || '',
          email_contacto: data.email_contacto || '',
          plan: data.plan || 'basico',
          activo: data.activo
        });
        this.planOriginal.set(data.plan || 'basico');
      },
      error: () => {
        alert('No se pudo cargar la información del colegio.');
        this.router.navigate(['/colegios']);
      }
    });
  }

  ubicacionCambio(ubicacion: UbicacionSeleccionada): void {
    this.formData.update(data => ({
      ...data,
      direccion: ubicacion.direccion,
      comuna: ubicacion.comuna,
      region: ubicacion.region,
      latitud: ubicacion.latitud,
      longitud: ubicacion.longitud,
    }));
  }

  /** Todos los datos del colegio son obligatorios. Devuelve el primero que falta. */
  private faltante(data: Partial<Colegio>): string | null {
    const requeridos: [unknown, string][] = this.soloContacto
      ? [
          [data.telefono, 'Debe ingresar el teléfono institucional.'],
          [data.email_contacto, 'Debe ingresar el correo de contacto.'],
        ]
      : [
          [data.nombre, 'Debe ingresar un nombre para el colegio.'],
          [data.rbd, 'Debe ingresar el RBD del colegio.'],
          [data.telefono, 'Debe ingresar el teléfono institucional.'],
          [data.direccion, 'Debe ingresar la dirección del colegio.'],
          [data.region, 'Debe seleccionar la región del colegio.'],
          [data.comuna, 'Debe seleccionar la comuna del colegio.'],
          [data.latitud, 'Debe marcar la ubicación del colegio en el mapa.'],
          [data.email_contacto, 'Debe ingresar el correo de contacto.'],
        ];
    const vacio = requeridos.find(([valor]) => valor == null || String(valor).trim() === '');
    return vacio ? vacio[1] : null;
  }

  /** Muestra el mensaje del servidor, sea un texto o los errores de cada campo. */
  private mensajeDeError(err: any, porDefecto: string): string {
    const datos = err?.error;
    if (datos?.message) return datos.message;
    if (datos && typeof datos === 'object') {
      const primero = Object.values(datos)[0];
      if (Array.isArray(primero) && primero.length) return String(primero[0]);
      if (typeof primero === 'string') return primero;
    }
    return porDefecto;
  }

  guardar(): void {
    const data = this.formData();
    const falta = this.faltante(data);
    if (falta) {
      alert(falta);
      return;
    }

    const dejaDeSerMultisede = this.esEdicion() && this.planOriginal() === 'avanzado' && data.plan !== 'avanzado';
    if (dejaDeSerMultisede && !confirm(
      'El colegio dejará de ser multisede. Solo se mantendrá la sede principal: las demás sedes se desactivarán ' +
      'junto con sus estudiantes, furgones, rutas e inspectores (quedan en la papelera). ¿Continuar?'
    )) {
      return;
    }

    this.guardando.set(true);

    if (this.esEdicion() && this.colegioId()) {
      const cambios = this.soloContacto
        ? { telefono: data.telefono, email_contacto: data.email_contacto }
        : data;
      this.colegioService.updateColegio(this.colegioId()!, cambios).subscribe({
        next: (res: any) => {
          this.guardando.set(false);
          const base = this.soloContacto ? 'Datos de contacto actualizados.' : 'Colegio actualizado exitosamente.';
          alert(res?.message ? `${base}

${res.message}` : base);
          this.router.navigate([this.rutaVolver]);
        },
        error: (err) => {
          this.guardando.set(false);
          alert(this.mensajeDeError(err, 'Error al actualizar colegio.'));
        }
      });
    } else {
      this.colegioService.createColegio(data).subscribe({
        next: () => {
          this.guardando.set(false);
          alert('Colegio creado exitosamente.');
          this.router.navigate(['/colegios']);
        },
        error: (err) => {
          this.guardando.set(false);
          alert(this.mensajeDeError(err, 'Error al crear colegio.'));
        }
      });
    }
  }
}
