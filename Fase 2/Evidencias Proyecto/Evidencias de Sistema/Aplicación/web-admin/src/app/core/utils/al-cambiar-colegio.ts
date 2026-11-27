import { DestroyRef, inject } from '@angular/core';

/**
 * Ejecuta `recargar` cada vez que el administrador de plataforma cambia el colegio del selector superior.
 * Se llama desde el constructor del componente y deja de escuchar al destruirlo.
 */
export function alCambiarColegio(recargar: () => void): void {
  const escuchar = () => recargar();
  window.addEventListener('colegio-changed', escuchar);
  inject(DestroyRef).onDestroy(() => window.removeEventListener('colegio-changed', escuchar));
}
