import { environment } from '../../environments/environment';

/** Demo: dirección del servidor elegida en el login. Solo existe si el .env de la app lo habilita. */
const CLAVE_SERVIDOR = 'servidor_api';
const PUERTO_API = '8000';
const PUERTO_GEO = '3000';

/** Convierte lo escrito ("192.168.43.20", "192.168.43.20:8000", "http://...") en la base del servidor. */
export function normalizarServidor(texto: string): string | null {
  const limpio = (texto || '').trim();
  if (!limpio || /\s/.test(limpio)) return null;
  try {
    const url = new URL(/^https?:\/\//i.test(limpio) ? limpio : `http://${limpio}`);
    if (!url.hostname) return null;
    const puerto = url.port || (url.protocol === 'http:' ? PUERTO_API : '');
    return `${url.protocol}//${url.hostname}${puerto ? ':' + puerto : ''}`;
  } catch {
    return null;
  }
}

/** Sin el botón habilitado no se usa ninguna dirección guardada antes: manda la del APK. */
export function obtenerServidor(): string | null {
  if (!environment.mostrarCampoServidor) return null;
  try {
    return localStorage.getItem(CLAVE_SERVIDOR);
  } catch {
    return null;
  }
}

/** Con null, la app vuelve a usar la dirección que trae el APK. */
export function guardarServidor(base: string | null): void {
  try {
    if (base) {
      localStorage.setItem(CLAVE_SERVIDOR, base);
    } else {
      localStorage.removeItem(CLAVE_SERVIDOR);
    }
  } catch {
    // Sin almacenamiento, la app sigue con la dirección que trae el APK.
  }
}

/** La dirección efectiva de una petición al backend o a la Geo API; las demás no cambian. */
export function aplicarServidor(url: string, base: string | null = obtenerServidor()): string {
  if (!base) return url;
  if (url.startsWith(environment.apiUrl)) {
    return `${base}/api${url.slice(environment.apiUrl.length)}`;
  }
  if (url.startsWith(environment.geoApiUrl)) {
    const { protocol, hostname } = new URL(base);
    return `${protocol}//${hostname}:${PUERTO_GEO}/api/geo${url.slice(environment.geoApiUrl.length)}`;
  }
  return url;
}
