const CACHE_NAME = 'hlcarerp-v4';
const OFFLINE_URL = '/offline.html';

const PRECACHE = [
    '/',
    '/clientes',
    '/veiculos',
    '/ordens',
    '/estoque',
    '/static/manifest.json',
    '/static/js/offline-db.js',
    '/static/js/offline-queue.js',
    '/static/js/offline-sync.js',
    '/static/css/offline.css'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(PRECACHE).catch(err => {
                console.warn('Algum arquivo do precache falhou:', err);
            });
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    const req = event.request;
    const url = new URL(req.url);

    if (url.origin !== location.origin) return;

    // Páginas de navegação
    if (req.mode === 'navigate') {
        event.respondWith(
            fetch(req)
                .then(res => {
                    const copy = res.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(req, copy));
                    return res;
                })
                .catch(() => caches.match(req).then(cached => cached || caches.match('/')))
        );
        return;
    }

    // Outros arquivos
    event.respondWith(
        caches.match(req).then(cached => {
            if (cached) return cached;
            return fetch(req).then(res => {
                if (res.status === 200) {
                    const copy = res.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(req, copy));
                }
                return res;
            }).catch(() => new Response('', { status: 503 }));
        })
    );
});