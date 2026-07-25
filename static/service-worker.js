const CACHE_NAME = "hlcarerp-v1";

const urlsToCache = [
    "/",
    "/static/css/style.css",
    "/static/logo_hlcar.png"
];

self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener("fetch", event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => response || fetch(event.request))
    );
});