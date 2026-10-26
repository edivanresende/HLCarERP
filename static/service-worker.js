const CACHE_NAME = 'hlcarerp-v3';
const OFFLINE_URL = '/offline.html';

const PRECACHE = [
    '/',
    '/clientes',
    '/veiculos',
    '/ordens',
    '/estoque',
    '/static/logo_hlcar.png',
    '/static/manifest.json',
    '/static/js/offline-db.js',
    '/static/js/offline-queue.js',
    '/static/js/offline-sync.js',
    '/static/css/offline.css',
    OFFLINE_URL
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(PRECACHE).catch(() => {}))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const req = event.request;
    const url = new URL(req.url);

    // Ignora requisições de outros domínios
    if (url.origin !== self.location.origin) return;

    // APIs: tenta online, se falhar retorna resposta offline
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(req).catch(() =>
                new Response(JSON.stringify({ offline: true }), {
                    status: 503,
                    headers: { 'Content-Type': 'application/json' }
                })
            )
        );
        return;
    }

    // Navegação (páginas HTML)
    if (req.mode === 'navigate') {
        event.respondWith(
            fetch(req)
                .then((response) => {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(c => c.put(req, clone));
                    return response;
                })
                .catch(() => caches.match(req).then(cached => cached || caches.match(OFFLINE_URL)))
        );
        return;
    }

    // Outros recursos (CSS, JS, imagens, etc.)
    event.respondWith(
        caches.match(req).then((cached) => {
            if (cached) return cached;
            return fetch(req).then((response) => {
                if (response && response.status === 200 && response.type === 'basic') {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(c => c.put(req, clone));
                }
                return response;
            }).catch(() => new Response('', { status: 408 }));
        })
    );
});

self.addEventListener('sync', (event) => {
    if (event.tag === 'hlcarerp-sync') {
        event.waitUntil(
            self.clients.matchAll().then(clients =>
                clients.forEach(c => c.postMessage({ type: 'SYNC_NOW' }))
            )
        );
    }
});