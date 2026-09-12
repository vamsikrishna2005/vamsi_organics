// Vamsi Organic Farms - Offline PWA Service Worker
const CACHE_NAME = 'vamsi-vegi-cache-v1';
const STATIC_ASSETS = [
    '/',
    '/static/manifest.json',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/js/store.js'
];

// Install Event - Pre-cache core assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS).catch(err => {
                console.warn('Some assets could not be pre-cached:', err);
            });
        }).then(() => self.skipWaiting())
    );
});

// Activate Event - Clean up outdated caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch Event - Network-first for fresh dynamic content with cache fallback
self.addEventListener('fetch', (event) => {
    // Only handle GET requests
    if (event.request.method !== 'GET') return;
    
    // Ignore chrome-extension and non-http(s) schemes
    if (!event.request.url.startsWith('http')) return;

    // Static files (icons, js, css) - Stale-while-revalidate
    if (event.request.url.includes('/static/')) {
        event.respondWith(
            caches.match(event.request).then((cachedResponse) => {
                const fetchPromise = fetch(event.request).then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseToCache);
                        });
                    }
                    return networkResponse;
                }).catch(() => cachedResponse);
                return cachedResponse || fetchPromise;
            })
        );
        return;
    }

    // HTML / API Requests - Network First, fallback to cache
    event.respondWith(
        fetch(event.request).then((networkResponse) => {
            return networkResponse;
        }).catch(() => {
            return caches.match(event.request).then((cached) => {
                if (cached) return cached;
                // Offline fallback response
                return new Response(
                    `<!DOCTYPE html>
                    <html lang="en">
                    <head><meta charset="UTF-8"><title>Offline - Vamsi Organic Farms</title></head>
                    <body style="font-family:sans-serif;text-align:center;padding:50px 20px;background:#f9fafb;color:#111827;">
                        <h1 style="color:#065f46;">🌾 Vamsi Organic Farms</h1>
                        <h3>You are currently offline</h3>
                        <p style="color:#6b7280;">Please check your internet connection to view live vegetable prices and place orders.</p>
                        <button onclick="location.reload()" style="background:#059669;color:#fff;border:none;padding:10px 20px;border-radius:10px;cursor:pointer;font-weight:bold;">Try Reconnecting</button>
                    </body>
                    </html>`,
                    { headers: { 'Content-Type': 'text/html' } }
                );
            });
        })
    );
});
