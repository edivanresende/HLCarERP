const CACHE = 'hlcarerp-v10';

const PRECACHE = [
  '/',
  '/static/offline.html',
  '/static/manifest.json',
  '/static/offline-sync.js',
  '/static/css/bootstrap.min.css',
  '/static/js/bootstrap.bundle.min.js'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Não intercepta requisições para outros domínios
  if (url.origin !== location.origin) return;

  // Para navegação (páginas HTML)
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request)
        .then(response => {
          // Salva no cache a página visitada
          const copy = response.clone();
          caches.open(CACHE).then(cache => cache.put(e.request, copy));
          return response;
        })
        .catch(() => caches.match(e.request).then(r => r || caches.match('/static/offline.html')))
    );
    return;
  }

  // Para arquivos estáticos (css, js, imagens)
  if (e.request.destination === 'style' || 
      e.request.destination === 'script' || 
      e.request.destination === 'image') {
    e.respondWith(
      caches.match(e.request).then(cached => {
        return cached || fetch(e.request).then(response => {
          const copy = response.clone();
          caches.open(CACHE).then(cache => cache.put(e.request, copy));
          return response;
        });
      })
    );
    return;
  }

  // Demais requisições (API, formulários, etc.)
  e.respondWith(
    fetch(e.request)
      .then(response => {
        if (e.request.method === 'GET') {
          const copy = response.clone();
          caches.open(CACHE).then(cache => cache.put(e.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(e.request))
  );
});