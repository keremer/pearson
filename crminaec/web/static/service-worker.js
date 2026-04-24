const CACHE_NAME = 'emek-erp-cache-v1';

// These assets are cached instantly when the app is installed
const ASSETS_TO_CACHE = [
    '/api/inventory/scanner',
    '/static/css/style.css',
    '/static/manifest.json',
    'https://cdn-icons-png.flaticon.com/512/1341/1341496.png',
    'https://unpkg.com/html5-qrcode',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
];

// --- 1. INSTALL EVENT ---
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('📦 Pre-caching offline assets...');
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
    self.skipWaiting(); // Force the waiting service worker to become the active service worker
});

// --- 2. ACTIVATE EVENT ---
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== CACHE_NAME) {
                        console.log('🧹 Clearing old cache:', cache);
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// --- 3. FETCH EVENT (Network First, Fallback to Cache) ---
self.addEventListener('fetch', event => {
    // Only cache GET requests (POSTs are handled by our local offline queue!)
    if (event.request.method !== 'GET') return;

    event.respondWith(
        fetch(event.request).then(response => {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, responseClone));
            return response;
        }).catch(() => caches.match(event.request))
    );
});