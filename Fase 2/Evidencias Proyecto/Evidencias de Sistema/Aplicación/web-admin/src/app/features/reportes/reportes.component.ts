import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ReporteRecorridos, ReportesService } from '../../core/services/reportes.service';
import { descargarReportePdf, textoAtraso, textoFecha, textoPuntualidad } from './reporte-pdf';
import { alCambiarColegio } from '../../core/utils/al-cambiar-colegio';

@Component({
  selector: 'app-reportes',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './reportes.component.html',
  styleUrl: './reportes.component.scss'
})
export class ReportesComponent implements OnInit {
  reporte: ReporteRecorridos | null = null;
  desde = '';
  hasta = '';
  cargando = false;
  exportando = false;
  error = '';
  incluirSimulados = false;

  readonly textoPuntualidad = textoPuntualidad;
  readonly textoAtraso = textoAtraso;
  readonly textoFecha = textoFecha;

  constructor(
    private reportesService: ReportesService,
    private cdr: ChangeDetectorRef
  ) {
    alCambiarColegio(() => this.generar());
  }

  ngOnInit(): void {
    this.generar();
  }

  generar(): void {
    this.cargando = true;
    this.error = '';
    this.reportesService.getReporte(this.desde, this.hasta, this.incluirSimulados).subscribe({
      next: (reporte) => {
        this.reporte = reporte;
        this.desde = reporte.desde;
        this.hasta = reporte.hasta;
        this.cargando = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.reporte = null;
        this.error = err?.error?.message || 'No se pudo generar el reporte.';
        this.cargando = false;
        this.cdr.markForCheck();
      }
    });
  }

  async descargar(): Promise<void> {
    if (!this.reporte || this.exportando) return;
    this.exportando = true;
    this.error = '';
    try {
      await descargarReportePdf(this.reporte);
    } catch (err) {
      console.error('No se pudo generar el PDF:', err);
      this.error = 'No se pudo generar el PDF. Inténtalo nuevamente.';
    } finally {
      this.exportando = false;
      this.cdr.markForCheck();
    }
  }

  get variosColegios(): boolean {
    return this.reporte?.colegio_nombre === 'Todos los colegios';
  }
}
