import { HttpErrorResponse, HttpEvent, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, Observable, throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import { aplicarServidor } from '../utils/servidor.util';

const PUBLIC_AUTH_PATHS = new Set([
  '/api/auth/login/',
  '/api/auth/login-admin/',
  '/api/auth/registro/',
  '/api/auth/colegios-registro/',
  '/api/auth/terminos/',
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

/** Una sesión abierta antes de exigirse los términos se entera aquí de que debe aceptarlos. */
const irATerminos = (router: Router): void => {
  try {
    const usuario = JSON.parse(localStorage.getItem('user') || 'null');
    if (usuario) {
      localStorage.setItem('user', JSON.stringify({ ...usuario, debe_aceptar_terminos: true }));
    }
  } catch {
    localStorage.removeItem('user');
  }
  if (!router.url.startsWith('/terminos')) {
    void router.navigateByUrl('/terminos', { replaceUrl: true });
  }
};

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const redirigirSiFaltanTerminos = catchError<HttpEvent<unknown>, Observable<HttpEvent<unknown>>>((error: HttpErrorResponse) => {
    if (error.status === 403 && error.error?.code === 'debe_aceptar_terminos') {
      irATerminos(router);
    }
    return throwError(() => error);
  });

  const token = localStorage.getItem('auth_token');
  const esPeticionBackend = req.url.startsWith(environment.apiUrl);
  const url = aplicarServidor(req.url);
  if (
    token &&
    esPeticionBackend &&
    !esEndpointPublicoAuth(req.url) &&
    !req.headers.has('Authorization')
  ) {
    const authReq = req.clone({
      url,
      headers: req.headers.set('Authorization', `Token ${token}`)
    });
    return next(authReq).pipe(redirigirSiFaltanTerminos);
  }
  return next(url === req.url ? req : req.clone({ url })).pipe(redirigirSiFaltanTerminos);
};
