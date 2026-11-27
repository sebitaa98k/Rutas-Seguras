import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/** Pantalla principal de cada rol. */
export function rutaInicioDe(rol?: string | null): string {
  if (rol === 'apoderado') return '/apoderado/inicio';
  if (rol === 'conductor') return '/conductor/inicio';
  if (rol === 'delegado') return '/delegado/inicio';
  return '/home';
}

/** Con sesión iniciada no se vuelve a elegir usuario ni al login: se sale cerrando sesión. */
export const invitadoGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const usuario = authService.getUsuario();
  if (!authService.getToken() || !usuario) return true;
  if (usuario.debe_cambiar_password) return inject(Router).parseUrl('/cambiar-password');
  if (usuario.debe_aceptar_terminos) return inject(Router).parseUrl('/terminos');

  const inicio = rutaInicioDe(usuario.rol);
  return inicio === '/home' ? true : inject(Router).parseUrl(inicio);
};

export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  const token = authService.getToken();
  const usuario = authService.getUsuario();

  if (!token || !usuario) {
    router.navigate(['/login'], { replaceUrl: true });
    return false;
  }

  if (usuario.debe_cambiar_password) {
    return router.parseUrl('/cambiar-password');
  }

  if (usuario.debe_aceptar_terminos) {
    return router.parseUrl('/terminos');
  }

  const requiredRole = route.data?.['rol'];
  if (requiredRole && usuario.rol !== requiredRole) {
    if (usuario.rol === 'apoderado') {
      router.navigate(['/apoderado/inicio'], { replaceUrl: true });
    } else if (usuario.rol === 'conductor') {
      router.navigate(['/conductor/inicio'], { replaceUrl: true });
    } else if (usuario.rol === 'delegado') {
      router.navigate(['/delegado/inicio'], { replaceUrl: true });
    } else {
      router.navigate(['/login'], { replaceUrl: true });
    }
    return false;
  }

  return true;
};

/** Solo quien tiene sesión y aún debe cambiar su contraseña inicial. */
export const cambioPasswordGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const usuario = authService.getUsuario();
  if (!authService.getToken() || !usuario) return router.parseUrl('/login');
  return usuario.debe_cambiar_password ? true : router.parseUrl(rutaInicioDe(usuario.rol));
};

/** Se llega después de cambiar la contraseña inicial, si la hubo. */
export const terminosGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const usuario = authService.getUsuario();
  if (!authService.getToken() || !usuario) return router.parseUrl('/login');
  if (usuario.debe_cambiar_password) return router.parseUrl('/cambiar-password');
  return usuario.debe_aceptar_terminos ? true : router.parseUrl(rutaInicioDe(usuario.rol));
};
