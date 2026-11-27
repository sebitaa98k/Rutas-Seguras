import { inject } from '@angular/core';
import { CanActivateFn, Router, UrlTree } from '@angular/router';
import { catchError, map, Observable, of } from 'rxjs';

import { FeedbackService } from '../services/feedback.service';
import { NotificationService } from '../services/notification.service';

/** Parámetros con que la pantalla de la ruta abre el escaneo facial. */
const PARAMETROS_DE_ACCION = ['modo', 'ruta_id', 'subida_general'];

interface ParadaApi {
  estudiante_id: number;
  estudiante_nombre: string;
  estado?: string;
  completada?: boolean;
  abordo?: boolean;
  no_recibido?: boolean;
}

interface RutaApi {
  id: number;
  estado: string;
  sentido: 'hacia_colegio' | 'desde_colegio';
  reparto_iniciado_en?: string | null;
  paradas?: ParadaApi[];
}

type Decision = { params: Record<string, string | number> } | { aviso: string };

/** La parada aún por resolver, con la misma regla que usa la pantalla de la ruta. */
function sinResolver(parada: ParadaApi): boolean {
  return parada.estado !== 'entregado'
    && !parada.no_recibido
    && parada.estado !== 'ausente'
    && !parada.completada
    && parada.estado !== 'no_asiste';
}

/** Qué escaneo corresponde según el momento de la ruta. */
export function decidirEscaneoFacial(ruta: RutaApi | null): Decision {
  if (!ruta || ruta.estado !== 'en_ruta') {
    return { aviso: 'No tienes una ruta en curso. Inicia tu ruta para escanear.' };
  }
  if (ruta.sentido === 'hacia_colegio') {
    return { params: { modo: 'abordar' } };
  }
  if (!ruta.reparto_iniciado_en) {
    return { params: { ruta_id: ruta.id, modo: 'abordar', subida_general: 1 } };
  }
  // Durante el reparto se entrega al niño de la parada actual: la primera pendiente, en el orden del servidor.
  const actual = (ruta.paradas || []).find(sinResolver);
  if (!actual || !actual.abordo) {
    return { aviso: 'No quedan casas por entregar. La recepción en el colegio se registra con el QR del inspector.' };
  }
  return {
    params: {
      ruta_id: ruta.id,
      estudiante_id: actual.estudiante_id,
      estudiante_nombre: actual.estudiante_nombre,
      modo: 'entregar'
    }
  };
}

/**
 * Al abrir el escaneo facial sin indicar la acción (por ejemplo, desde la barra inferior),
 * consulta la ruta y entra en el modo que corresponde, o avisa si no hay ruta en curso.
 */
export const accionFacialGuard: CanActivateFn = (route): Observable<boolean | UrlTree> | boolean => {
  if (PARAMETROS_DE_ACCION.some(parametro => route.queryParamMap.has(parametro))) {
    return true;
  }
  const router = inject(Router);
  const feedback = inject(FeedbackService);
  return inject(NotificationService).obtenerMiRuta().pipe(
    catchError(() => of(null)),
    map((ruta: RutaApi | null) => {
      const decision = decidirEscaneoFacial(ruta);
      if ('aviso' in decision) {
        void feedback.show(decision.aviso, 'warning');
        return router.parseUrl('/conductor/ruta-activa');
      }
      return router.createUrlTree(['/conductor/escaneo-facial'], { queryParams: decision.params });
    })
  );
};
