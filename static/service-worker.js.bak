const CACHE_NAME = 'hlcarerp-v2';
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
    if (url.origin !== self.location.origin) return;

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

    if (req.mode === 'navigate') {
        event.respondWith(
            fetch(req)
                .then((response) => {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(c => c.put(req, clone));
                    return response;
                })
                .catch(() => caches.match(req).then(c => c || caches.match(OFFLINE_URL)))
        );
        return;
    }

    event.respondWith(
        caches.match(req).then((cached) => {
            if (cached) return cached;
            return fetch(req).then((response) => {
                if (response && response.status === 200) {
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