/**
 * Arma la configuración de la app para el APK a partir de mobile-app/.env (no se sube a git).
 * Se ejecuta solo antes de `npm run build`. Sin .env, usa los valores de desarrollo (127.0.0.1).
 *
 * Variables:
 *   API_URL                 Dirección de Django, ej: http://192.168.1.101:8000/api
 *   GEO_API_URL             Dirección del servicio de mapas, ej: http://192.168.1.101:3000/api/geo
 *   MOSTRAR_CAMPO_SERVIDOR  true para mostrar el botón "Servidor" en el login (solo demostraciones)
 */
const fs = require('fs');
const path = require('path');

const raiz = path.join(__dirname, '..');
const archivoEnv = path.join(raiz, '.env');
const destino = path.join(raiz, 'src', 'environments', 'environment.local.ts');

const POR_DEFECTO = {
  API_URL: 'http://127.0.0.1:8000/api',
  GEO_API_URL: 'http://127.0.0.1:3000/api/geo',
  MOSTRAR_CAMPO_SERVIDOR: 'false'
};

function leerEnv(ruta) {
  if (!fs.existsSync(ruta)) return {};
  const valores = {};
  for (const linea of fs.readFileSync(ruta, 'utf8').split(/\r?\n/)) {
    const limpia = linea.trim();
    if (!limpia || limpia.startsWith('#') || !limpia.includes('=')) continue;
    const posicion = limpia.indexOf('=');
    valores[limpia.slice(0, posicion).trim()] = limpia.slice(posicion + 1).trim().replace(/^["']|["']$/g, '');
  }
  return valores;
}

const env = { ...POR_DEFECTO, ...leerEnv(archivoEnv) };
const sinBarraFinal = (url) => url.replace(/\/+$/, '');
const configuracion = {
  production: true,
  apiUrl: sinBarraFinal(env.API_URL),
  geoApiUrl: sinBarraFinal(env.GEO_API_URL),
  mostrarCampoServidor: env.MOSTRAR_CAMPO_SERVIDOR.toLowerCase() === 'true'
};

fs.writeFileSync(
  destino,
  '// Generado por scripts/generar-entorno.js desde mobile-app/.env. No editar ni subir a git.\n' +
    `export const environment = ${JSON.stringify(configuracion, null, 2)};\n`,
  'utf8'
);

console.log(fs.existsSync(archivoEnv) ? 'Configuración tomada de mobile-app/.env:' : 'Sin mobile-app/.env: se usan valores de desarrollo.');
console.log(`  API: ${configuracion.apiUrl}`);
console.log(`  Mapas: ${configuracion.geoApiUrl}`);
console.log(`  Botón "Servidor" en el login: ${configuracion.mostrarCampoServidor ? 'sí' : 'no'}`);
