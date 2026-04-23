// Service Worker for Offline Support
const CACHE_VERSION = 'v1-2026-04-20';
const STATIC_CACHE = `static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `dynamic-${CACHE_VERSION}`;
const API_CACHE = `api-${CACHE_VERSION}`;

// Static assets to cache on install
const STATIC_ASSETS = [
    '/',
    '/static/css/',
    '/static/js/',
    '/static/images/',
    '/offline.html'
];

// Install Event - Cache static assets
self.addEventListener('install', event => {
    console.log('Service Worker installing...');
    event.waitUntil(
        caches.open(STATIC_CACHE).then(cache => {
            console.log('Caching static assets');
            return cache.addAll(STATIC_ASSETS).catch(err => {
                console.log('Error caching static assets:', err);
                // Continue even if some assets fail to cache
            });
        }).then(() => self.skipWaiting())
    );
});

// Activate Event - Clean old caches
self.addEventListener('activate', event => {
    console.log('Service Worker activating...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== STATIC_CACHE && 
                        cacheName !== DYNAMIC_CACHE && 
                        cacheName !== API_CACHE) {
                        console.log('Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch Event - Network First, then Cache
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests and external resources
    if (request.method !== 'GET') {
        return;
    }

    // Handle API requests
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(networkFirst(request));
        return;
    }

    // Handle static assets
    if (url.pathname.match(/\.(css|js|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot)$/)) {
        event.respondWith(cacheFirst(request));
        return;
    }

    // Handle HTML pages
    if (request.headers.get('accept')?.includes('text/html')) {
        event.respondWith(networkFirst(request));
        return;
    }

    // Default: Network first
    event.respondWith(networkFirst(request));
});

// Network First Strategy
function networkFirst(request) {
    return fetch(request)
        .then(response => {
            if (!response || response.status !== 200 || response.type === 'error') {
                return cacheGetOrOffline(request);
            }

            // Cache successful responses
            const cache = request.url.includes('/api/') ? API_CACHE : DYNAMIC_CACHE;
            const responseToCache = response.clone();
            caches.open(cache).then(cache => {
                cache.put(request, responseToCache);
            });

            return response;
        })
        .catch(err => {
            console.log('Network request failed:', err);
            return cacheGetOrOffline(request);
        });
}

// Cache First Strategy
function cacheFirst(request) {
    return caches.match(request)
        .then(response => {
            if (response) {
                return response;
            }
            return fetch(request)
                .then(response => {
                    if (!response || response.status !== 200 || response.type === 'error') {
                        return offlineFallback(request);
                    }
                    const responseToCache = response.clone();
                    caches.open(DYNAMIC_CACHE).then(cache => {
                        cache.put(request, responseToCache);
                    });
                    return response;
                })
                .catch(err => offlineFallback(request));
        });
}

// Cache or Offline Fallback
function cacheGetOrOffline(request) {
    return caches.match(request)
        .then(response => {
            if (response) {
                return response;
            }
            return offlineFallback(request);
        });
}

// Offline Fallback
function offlineFallback(request) {
    if (request.headers.get('accept')?.includes('text/html')) {
        return caches.match('/offline.html').then(response => {
            return response || new Response('<h1>Offline - Unable to Load</h1>', {
                headers: { 'Content-Type': 'text/html' }
            });
        });
    }
    return new Response('Offline', { status: 503 });
}

// Background Sync for pending operations
self.addEventListener('sync', event => {
    if (event.tag === 'sync-pending-operations') {
        event.waitUntil(syncPendingOperations());
    }
});

function syncPendingOperations() {
    return idb.open('ArmyPortalDB').then(db => {
        const tx = db.transaction('pendingOperations', 'readonly');
        const store = tx.objectStore('pendingOperations');
        const pending = [];

        return new Promise((resolve, reject) => {
            const request = store.getAll();
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                const operations = request.result;
                resolve(Promise.all(operations.map(op => {
                    return fetch(op.url, {
                        method: op.method,
                        headers: op.headers,
                        body: op.body
                    }).then(response => {
                        if (response.ok) {
                            // Remove from pending
                            const tx2 = db.transaction('pendingOperations', 'readwrite');
                            tx2.objectStore('pendingOperations').delete(op.id);
                        }
                    });
                })));
            };
        });
    });
}

// Message Event - For communication with clients
self.addEventListener('message', event => {
    if (event.data.action === 'clearCache') {
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => caches.delete(cacheName))
            );
        });
    }
});
