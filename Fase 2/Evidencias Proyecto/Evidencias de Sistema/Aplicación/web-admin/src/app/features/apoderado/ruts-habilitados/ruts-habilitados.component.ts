import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApoderadoService, EstudianteHabilitado, RutHabilitado } from '../../../core/services/apoderado.service';
import { AuthService } from '../../../core/services/auth.service';
import { ColegioService } from '../../../core/services/colegio.service';
import { alCambiarColegio } from '../../../core/utils/al-cambiar-colegio';

type Pestana = 'estudiantes' | 'apoderados';

/**
 * Habilitación para registrarse desde la app. El colegio habilita a cada estudiante junto con el RUT de su
 * apoderado; con eso el apoderado queda habilitado solo. Así, cuando agrega a su hijo, el colegio no lo
 * elige él (puede tener hijos en varios colegios).
 */
@Component({
  selector: 'app-ruts-habilitados',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './ruts-habilitados.component.html',
  styleUrl: './ruts-habilitados.component.scss'
})
export class RutsHabilitadosComponent implements OnInit {
  private authService = inject(AuthService);
  private colegioService = inject(ColegioService);

  pestana: Pestana = 'estudiantes';

  // Estudiantes habilitados
  estudiantes: EstudianteHabilitado[] = [];
  limiteEstudiantes = 500;
  buscarEstudiante = '';
  estadoEstudiante = '';
  textoPares = '';
  resultadoPares = '';
  cargandoEstudiantes = false;
  guardandoPares = false;
  errorEstudiantes = '';

  // Apoderados habilitados (se generan al habilitar a sus hijos)
  ruts: RutHabilitado[] = [];
  limite = 500;
  buscar = '';
  estado = '';
  cargando = false;
  error = '';

  constructor(
    private apoderadoService: ApoderadoService,
    private cdr: ChangeDetectorRef
  ) {
    alCambiarColegio(() => this.recargar());
  }

  ngOnInit(): void {
    this.recargar();
  }

  /** El administrador de plataforma habilita en el colegio elegido en el selector de arriba. */
  get sinColegioElegido(): boolean {
    return this.authService.currentUser()?.role === 'ADMIN_PLATAFORMA' && !this.colegioService.selectedColegioId();
  }

  cambiarPestana(pestana: Pestana): void {
    this.pestana = pestana;
  }

  private recargar(): void {
    this.cargarEstudiantes();
    this.cargar();
  }

  private mensajeDe(err: any, respaldo: string): string {
    return err?.error?.message || err?.error?.colegio_id || respaldo;
  }

  // ------------------------------------------------------------ estudiantes

  cargarEstudiantes(): void {
    this.cargandoEstudiantes = true;
    this.errorEstudiantes = '';
    this.apoderadoService.getEstudiantesHabilitados(this.buscarEstudiante, this.estadoEstudiante).subscribe({
      next: (respuesta) => {
        this.estudiantes = respuesta.estudiantes;
        this.limiteEstudiantes = respuesta.limite;
        this.cargandoEstudiantes = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.estudiantes = [];
        this.errorEstudiantes = this.mensajeDe(err, 'No se pudieron cargar los estudiantes habilitados.');
        this.cargandoEstudiantes = false;
        this.cdr.markForCheck();
      }
    });
  }

  habilitar(): void {
    if (!this.textoPares.trim() || this.guardandoPares || this.sinColegioElegido) return;
    this.guardandoPares = true;
    this.resultadoPares = '';
    this.errorEstudiantes = '';
    this.apoderadoService.habilitarEstudiantes(this.textoPares).subscribe({
      next: (respuesta) => {
        const partes = [`Estudiantes habilitados: ${respuesta.agregados}.`];
        if (respuesta.cuentas_vinculadas) {
          partes.push(`Apoderados con cuenta en otro colegio vinculados a este: ${respuesta.cuentas_vinculadas} (se les avisó en la app).`);
        }
        if (respuesta.repetidos.length) {
          partes.push(`Ya estaban habilitados: ${respuesta.repetidos.join(', ')}.`);
        }
        if (respuesta.en_otro_colegio.length) {
          partes.push(`Ya están habilitados en otro colegio: ${respuesta.en_otro_colegio.join(', ')}.`);
        }
        if (respuesta.en_otro_rol?.length) {
          partes.push(
            `No se habilitaron porque uno de los RUT ya se usa con otro rol en Rutas Seguras ` +
            `(apoderado, conductor, inspector o estudiante; un RUT es una sola persona): ${respuesta.en_otro_rol.join(', ')}.`
          );
        }
        if (respuesta.ya_registrados.length) {
          partes.push(`Ya están inscritos (no necesitan habilitación): ${respuesta.ya_registrados.join(', ')}.`);
        }
        if (respuesta.formato_invalido.length) {
          partes.push(`Líneas con errores (revisa los dos RUT y su dígito verificador): ${respuesta.formato_invalido.length}.`);
        }
        this.resultadoPares = partes.join(' ');
        // Lo que tuvo errores queda escrito para poder corregirlo.
        this.textoPares = respuesta.formato_invalido.join('\n');
        this.guardandoPares = false;
        this.recargar();
      },
      error: (err) => {
        this.errorEstudiantes = this.mensajeDe(err, 'No se pudieron habilitar los estudiantes.');
        this.guardandoPares = false;
        this.cdr.markForCheck();
      }
    });
  }

  quitarEstudiante(entrada: EstudianteHabilitado): void {
    if (!confirm(`¿Quitar la habilitación del estudiante ${entrada.rut}? Su apoderado ya no podrá inscribirlo desde la app. Quedará en la papelera y podrás reactivarla.`)) return;
    this.apoderadoService.quitarEstudianteHabilitado(entrada.id).subscribe({
      next: () => this.cargarEstudiantes(),
      error: (err) => alert(this.mensajeDe(err, 'No se pudo quitar la habilitación.'))
    });
  }

  get variosColegiosEstudiantes(): boolean {
    return new Set(this.estudiantes.map((item) => item.colegio_id)).size > 1;
  }

  // ------------------------------------------------------------ apoderados

  cargar(): void {
    this.cargando = true;
    this.error = '';
    this.apoderadoService.getRutsHabilitados(this.buscar, this.estado).subscribe({
      next: (respuesta) => {
        this.ruts = respuesta.ruts;
        this.limite = respuesta.limite;
        this.cargando = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.ruts = [];
        this.error = this.mensajeDe(err, 'No se pudieron cargar los RUT.');
        this.cargando = false;
        this.cdr.markForCheck();
      }
    });
  }

  eliminar(entrada: RutHabilitado): void {
    if (!confirm(`¿Quitar el RUT ${entrada.rut} de la lista? Ya no servirá para registrarse. Quedará en la papelera y podrás reactivarlo.`)) return;
    this.apoderadoService.eliminarRutHabilitado(entrada.id).subscribe({
      next: () => this.cargar(),
      error: (err) => alert(this.mensajeDe(err, 'No se pudo quitar el RUT.'))
    });
  }

  liberar(entrada: RutHabilitado): void {
    const cuenta = entrada.cuenta ? `${entrada.cuenta.nombre} (${entrada.cuenta.email})` : 'la cuenta asociada';
    if (!confirm(`Se desactivará ${cuenta} y el RUT ${entrada.rut} quedará disponible. ¿Continuar?`)) return;
    this.apoderadoService.liberarRutHabilitado(entrada.id).subscribe({
      next: () => this.cargar(),
      error: (err) => alert(this.mensajeDe(err, 'No se pudo liberar el RUT.'))
    });
  }

  get variosColegios(): boolean {
    return new Set(this.ruts.map((item) => item.colegio_id)).size > 1;
  }
}
