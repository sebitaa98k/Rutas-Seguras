import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  AceptacionTerminos,
  AuditoriaService,
  EventoAuditoria,
  FiltrosAuditoria,
  RecorridoAuditoria,
  TerminosPendiente, CambioBiometria, ConsentimientoBiometria } from '../../core/services/auditoria.service';
import { alCambiarColegio } from '../../core/utils/al-cambiar-colegio';

@Component({
  selector: 'app-auditoria-lista',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './auditoria-lista.component.html',
  styleUrl: './auditoria-lista.component.scss'
})
export class AuditoriaListaComponent implements OnInit {
  recorridos: RecorridoAuditoria[] = [];
  filtros: FiltrosAuditoria = { desde: '', hasta: '', buscar: '', soloAtrasos: false };
  abiertos = new Set<number>();
  cargando = false;
  error = '';
  tolerancia = 10;
  limite = 100;

  vista: 'recorridos' | 'terminos' = 'recorridos';
  aceptaciones: AceptacionTerminos[] = [];
  pendientes: TerminosPendiente[] = [];
  cambiosBiometria: CambioBiometria[] = [];
  consentimientosBiometria: ConsentimientoBiometria[] = [];
  versionTerminos = '';
  limiteTerminos = 200;
  buscarTerminos = '';
  cargandoTerminos = false;
  errorTerminos = '';

  constructor(
    private auditoriaService: AuditoriaService,
    private cdr: ChangeDetectorRef
  ) {
    alCambiarColegio(() => (this.vista === 'terminos' ? this.cargarTerminos() : this.cargar()));
  }

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    this.cargando = true;
    this.error = '';
    this.auditoriaService.getRecorridos(this.filtros).subscribe({
      next: (respuesta) => {
        this.recorridos = respuesta.recorridos;
        this.tolerancia = respuesta.tolerancia_atraso_minutos;
        this.limite = respuesta.limite;
        this.cargando = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.recorridos = [];
        this.error = err?.error?.message || 'No se pudo cargar la auditoría.';
        this.cargando = false;
        this.cdr.markForCheck();
      }
    });
  }

  cambiarVista(vista: 'recorridos' | 'terminos'): void {
    this.vista = vista;
    if (vista === 'terminos') {
      this.cargarTerminos();
    }
  }

  cargarTerminos(): void {
    this.cargandoTerminos = true;
    this.errorTerminos = '';
    this.auditoriaService.getTerminos(this.buscarTerminos).subscribe({
      next: (respuesta) => {
        this.aceptaciones = respuesta.aceptaciones;
        this.pendientes = respuesta.pendientes;
        this.cambiosBiometria = respuesta.cambios_biometria || [];
        this.consentimientosBiometria = respuesta.consentimientos_biometria || [];
        this.versionTerminos = respuesta.version_vigente;
        this.limiteTerminos = respuesta.limite;
        this.cargandoTerminos = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.aceptaciones = [];
        this.pendientes = [];
        this.cambiosBiometria = [];
        this.consentimientosBiometria = [];
        this.errorTerminos = err?.error?.message || 'No se pudo cargar la auditoría de términos.';
        this.cargandoTerminos = false;
        this.cdr.markForCheck();
      }
    });
  }

  limpiar(): void {
    this.filtros = { desde: '', hasta: '', buscar: '', soloAtrasos: false };
    this.cargar();
  }

  alternar(id: number): void {
    if (this.abiertos.has(id)) {
      this.abiertos.delete(id);
    } else {
      this.abiertos.add(id);
    }
  }

  /** Solo el administrador de plataforma, sin colegio elegido, ve recorridos de varios colegios. */
  get variosColegios(): boolean {
    return new Set(this.recorridos.map(r => r.colegio_nombre)).size > 1;
  }

  get cantidadAtrasados(): number {
    return this.recorridos.filter(r => r.atrasado).length;
  }

  get cantidadFaltas(): number {
    return this.recorridos.reduce(
      (total, r) => total + r.alumnos.filter(a => a.estado === 'ausente').length,
      0
    );
  }

  get cantidadEmergencias(): number {
    return this.recorridos.reduce(
      (total, r) => total + r.eventos.filter(e => e.tipo === 'emergencia').length,
      0
    );
  }

  textoSentido(recorrido: RecorridoAuditoria): string {
    return recorrido.sentido === 'hacia_colegio' ? 'Ida (casa → colegio)' : 'Vuelta (colegio → casa)';
  }

  textoEstado(recorrido: RecorridoAuditoria): string {
    if (recorrido.estado === 'finalizado') return 'Finalizado';
    return recorrido.estado === 'en_curso' ? 'En curso' : 'Sin iniciar';
  }

  textoAtraso(recorrido: RecorridoAuditoria): string {
    if (recorrido.hora_programada === null) return 'Sin horario';
    if (recorrido.minutos_atraso === null) return recorrido.estado === 'finalizado' ? 'Sin dato' : 'Pendiente';
    return recorrido.atrasado ? `${recorrido.minutos_atraso} min de atraso` : 'A tiempo';
  }

  textoPersona(evento: EventoAuditoria | null): string {
    if (!evento?.persona_nombre) return '';
    const rut = evento.persona_rut ? `, RUT ${evento.persona_rut}` : '';
    return `${evento.persona_nombre} (${evento.persona_rol}${rut})`;
  }

  textoEvento(evento: EventoAuditoria): string {
    return [evento.estudiante_nombre, evento.metodo, this.textoPersona(evento), evento.detalle]
      .filter(Boolean)
      .join(' · ');
  }
}
