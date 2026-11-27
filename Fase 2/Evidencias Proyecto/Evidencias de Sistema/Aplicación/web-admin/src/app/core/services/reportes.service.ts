import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface IndicadoresReporte {
  recorridos: number;
  con_horario: number;
  puntuales: number;
  porcentaje_puntualidad: number | null;
  atraso_promedio_minutos: number | null;
  viajes: number;
  no_subio: number;
  inasistencias: number;
  entregados: number;
  no_recibidos: number;
  emergencias: number;
  sin_registro: number;
}

export interface FilaReporte extends IndicadoresReporte {
  nombre: string;
  colegio_nombre: string;
}

export interface ReporteRecorridos {
  desde: string;
  hasta: string;
  colegio_nombre: string;
  tolerancia_atraso_minutos: number;
  incluye_simulados: boolean;
  resumen: IndicadoresReporte;
  por_ruta: FilaReporte[];
  por_conductor: FilaReporte[];
  por_estudiante: FilaReporte[];
}

@Injectable({ providedIn: 'root' })
export class ReportesService {
  private readonly apiUrl = `${environment.apiBaseUrl}/reportes/recorridos/`;

  constructor(private http: HttpClient) {}

  getReporte(desde: string, hasta: string, incluirSimulados = false): Observable<ReporteRecorridos> {
    let params = new HttpParams();
    if (incluirSimulados) params = params.set('incluir_simulados', '1');
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http.get<ReporteRecorridos>(this.apiUrl, { params });
  }
}
