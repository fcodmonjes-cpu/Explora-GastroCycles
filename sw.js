// Service worker del ATA Handbook.
//
// ESTRATEGIA: network-first, cache como red de emergencia. La app es una
// herramienta de operación en vivo: mostrar una versión vieja del handbook a
// hora de servicio es peor que no mostrar nada. Por eso SIEMPRE se pide a la
// red primero; el cache solo entra cuando el wifi del lodge se cae.
//
// NO se cachea nada de Firebase ni de terceros: los datos vivos (viajeros,
// comandas, café) tienen que ser siempre frescos, y las fuentes de Google se
// resuelven con el cache propio del browser.
//
// PARA MATARLO (si algún día estorba): borrar el registro en index.html
// (bloque "PWA") y publicar este archivo con solo un addEventListener
// 'install' que llame a self.registration.unregister(). Sin eso, un service
// worker sobrevive a los deploys.

const CACHE = 'ata-handbook-v1';
const CORE  = ['/', '/index.html', '/favicon.svg', '/manifest.webmanifest',
               '/assets/icon-180.png', '/assets/icon-192.png', '/assets/icon-512.png'];

self.addEventListener('install', e => {
  // skipWaiting: la versión nueva toma el control en la siguiente carga, sin
  // esperar a que se cierren todas las pestañas.
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  // Solo GET del propio origen. Firebase, Google Fonts y cualquier otra cosa
  // pasan de largo sin tocar el cache.
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  e.respondWith(
    fetch(req)
      .then(resp => {
        if (resp && resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE).then(c => c.put(req, copy));
        }
        return resp;
      })
      .catch(() => caches.match(req).then(hit => hit || caches.match('/index.html')))
  );
});
