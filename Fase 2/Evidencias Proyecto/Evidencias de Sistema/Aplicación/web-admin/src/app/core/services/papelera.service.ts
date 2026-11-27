import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface ItemPapelera {
  id: number;
  tipo: string;
  nombre: string;
  detalle: string;
  desactivado_en: string | null;
  /** Quedó en una sede que se cerró al bajar de plan: se mueve al colegio en vez de reactivarse. */
  puede_mover?: boolean;
}

export interface GrupoPapelera {
  tipo: string;
  titulo: string;
  items: ItemPapelera[];
}

/** Lo desactivado del panel: nada se borra, se puede reactivar. */
@Injectable({ providedIn: 'root' })
export class PapeleraService {
  private readonly apiUrl = `${environment.apiBaseUrl}/papelera/`;

  constructor(private http: HttpClient) {}

  listar(): Observable<GrupoPapelera[]> {
    return this.http.get<GrupoPapelera[]>(this.apiUrl);
  }

  /** Borra de verdad. Lo que tiene historial de recorridos no se borra (responde 409). */
  eliminarDefinitivo(item: ItemPapelera): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}${item.tipo}/${item.id}/`);
  }

  /** Lo deja activo en el colegio (su sede principal). Solo para lo que quedó en una sede cerrada al bajar de plan. */
  moverAlColegio(item: ItemPapelera): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}${item.tipo}/${item.id}/mover-al-colegio/`, {});
  }

  reactivar(item: ItemPapelera): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}${item.tipo}/${item.id}/reactivar/`, {});
  }
}
