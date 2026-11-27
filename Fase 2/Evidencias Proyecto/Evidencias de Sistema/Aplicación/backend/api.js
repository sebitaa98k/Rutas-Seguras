const http = require('http');

// Geo API: solo trazado de rutas por calles reales (OSRM).
// La búsqueda de direcciones se resuelve en Django (/api/geo/coincidencias/).
const PORT = 3000;
const OSRM_BASE_URL = 'http://router.project-osrm.org/route/v1/driving';
// Si OSRM no responde en este plazo, se cancela la consulta y los mapas siguen sin la línea por calles.
const TIEMPO_MAXIMO_OSRM_MS = 8000;

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Colegio-ID');
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    return res.end();
  }

  const urlObj = new URL(req.url, `http://localhost:${PORT}`);
  const pathname = urlObj.pathname;
  const params = urlObj.searchParams;

  try {
    // Trazado de ruta por calles reales (OSRM)
    if (pathname === '/api/geo/ruta' && req.method === 'GET') {
      const puntos = params.get('puntos');
      let coordenadas = '';

      if (puntos) {
        // Formato: lon,lat;lon,lat;lon,lat
        const lista = puntos
          .split(';')
          .map(valor => valor.trim())
          .filter(Boolean);

        if (lista.length < 2 || lista.some(valor => !/^-?\d+(\.\d+)?,-?\d+(\.\d+)?$/.test(valor))) {
          res.writeHead(400);
          return res.end(JSON.stringify({ error: 'Se requieren al menos dos puntos válidos para calcular la ruta' }));
        }
        coordenadas = lista.join(';');
      } else {
        const latOrigen = params.get('latOrigen');
        const lonOrigen = params.get('lonOrigen');
        const latDestino = params.get('latDestino');
        const lonDestino = params.get('lonDestino');

        if (!latOrigen || !lonOrigen || !latDestino || !lonDestino) {
          res.writeHead(400);
          return res.end(JSON.stringify({ error: 'Faltan coordenadas para calcular la ruta' }));
        }
        coordenadas = `${lonOrigen},${latOrigen};${lonDestino},${latDestino}`;
      }

      const osrmUrl = `${OSRM_BASE_URL}/${coordenadas}?overview=full&geometries=geojson&steps=false`;
      let data;
      try {
        const response = await fetch(osrmUrl, { signal: AbortSignal.timeout(TIEMPO_MAXIMO_OSRM_MS) });
        data = await response.json();
      } catch (error) {
        const sinRespuesta = error.name === 'TimeoutError' || error.name === 'AbortError';
        res.writeHead(sinRespuesta ? 504 : 502);
        return res.end(JSON.stringify({
          error: sinRespuesta
            ? 'El servicio de rutas no respondió a tiempo'
            : 'No se pudo consultar el servicio de rutas'
        }));
      }

      if (!data.routes || !data.routes.length) {
        res.writeHead(404);
        return res.end(JSON.stringify({ error: 'No se pudo trazar la ruta' }));
      }

      const puntosRuta = data.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
      const puntosAjustados = (data.waypoints || []).map(waypoint => ({
        latitud: waypoint.location[1],
        longitud: waypoint.location[0],
        distanciaAjusteMetros: waypoint.distance
      }));

      return res.end(JSON.stringify({
        distanciaMetros: data.routes[0].distance,
        duracionSegundos: data.routes[0].duration,
        puntosRuta,
        puntosAjustados
      }));
    }

    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Ruta no encontrada' }));

  } catch (error) {
    res.writeHead(500);
    res.end(JSON.stringify({ error: 'Error del servidor', detalle: error.message }));
  }
});

server.listen(PORT, () => {
  console.log(`Geo API activa en http://localhost:${PORT}`);
});
