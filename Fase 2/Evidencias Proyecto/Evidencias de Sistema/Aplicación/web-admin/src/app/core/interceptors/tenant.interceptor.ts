import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';
import { ColegioService } from '../services/colegio.service';

const PUBLIC_AUTH_PATHS = new Set([
  '/api/auth/login/',
  '/api/auth/login-admin/',
  '/api/auth/registro/',
  '/api/auth/registro-delegado/',
  '/api/auth/password-reset/',
  '/api/auth/password-reset/confirm/'
]);

export const esEndpointPublicoAuth = (url: string): boolean => {
  try {
    return PUBLIC_AUTH_PATHS.has(new URL(url, window.location.origin).pathname);
  } catch {
    return false;
  }
};

export const tenantInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const colegioService = inject(ColegioService);

  const token = authService.getToken();
  const user = authService.currentUser();
  const selectedColegioId = colegioService.selectedColegioId();
  const esRecursoGlobalDeColegios = req.url.includes('/api/colegios/');

  let headers = req.headers;

  if (token && !esEndpointPublicoAuth(req.url)) {
    headers = headers.set('Authorization', `Token ${token}`);
  }

  // Si el usuario es ADMINISTRADOR DE PLATAFORMA (o superadmin) y ha seleccionado un colegio en el selector global
  if (user && (user.role === 'ADMIN_PLATAFORMA' || user.role === 'ADMIN')) {
    if (selectedColegioId !== null && !esRecursoGlobalDeColegios) {
      headers = headers.set('X-Colegio-ID', String(selectedColegioId));
    }
  }

  const clonedReq = req.clone({ headers });
  return next(clonedReq);
};
