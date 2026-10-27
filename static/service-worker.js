const CACHE_NAME = 'hlcarerp-v5';

const PRECACHE = [
  '/',
  '/estoque',
  '/clientes',
  '/ordens',
  '/veiculos',
  '/static/manifest.json',
  '/static/js/offline-db.js',
  '/static/js/offline-queue.js',
  '/static/js/offline-sync.js',
  '/static/css/offline.css'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;

      return fetch(event.request).then(response => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => {
        // Se for navegação, tenta devolver a página inicial do cache
        if (event.request.mode === 'navigate') {
          return caches.match('/') || caches.match('/estoque');
        }
        return new Response('Offline', { status: 503 });
      });
    })
  );
});