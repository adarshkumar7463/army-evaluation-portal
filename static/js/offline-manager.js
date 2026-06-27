// Offline Detection and UI Management
class OfflineManager {
    constructor() {
        this.isOnline = navigator.onLine;
        this.offlineIndicatorId = 'offline-indicator';
        this.syncQueue = [];
        this.initializeIndexedDB();
        this.setupEventListeners();
        this.registerServiceWorker();
    }

    // Setup online/offline event listeners
    setupEventListeners() {
        window.addEventListener('online', () => this.goOnline());
        window.addEventListener('offline', () => this.goOffline());
    }

    // Register Service Worker
    registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/js/service-worker.js')
                .then(registration => {
                    console.log('Service Worker registered:', registration);
                })
                .catch(err => {
                    console.log('Service Worker registration failed:', err);
                });
        }
    }

    // Initialize IndexedDB for offline data storage
    initializeIndexedDB() {
        const dbRequest = indexedDB.open('ArmyPortalDB', 1);

        dbRequest.onerror = () => {
            console.error('IndexedDB initialization failed');
        };

        dbRequest.onsuccess = (event) => {
            this.db = event.target.result;
            console.log('IndexedDB initialized');
        };

        dbRequest.onupgradeneeded = (event) => {
            const db = event.target.result;
            
            // Create object stores if they don't exist
            if (!db.objectStoreNames.contains('offlineData')) {
                db.createObjectStore('offlineData', { keyPath: 'id' });
            }
            if (!db.objectStoreNames.contains('pendingOperations')) {
                db.createObjectStore('pendingOperations', { keyPath: 'id', autoIncrement: true });
            }
            if (!db.objectStoreNames.contains('syncQueue')) {
                db.createObjectStore('syncQueue', { keyPath: 'id', autoIncrement: true });
            }
        };
    }

    // Handle going online
    goOnline() {
        this.isOnline = true;
        // Offline indicator is handled by the active app shell.
        this.syncPendingOperations();
        console.log('Application is online');
    }

    // Handle going offline
    goOffline() {
        this.isOnline = false;
        // Offline indicator is handled by the active app shell.
        console.log('Application is offline');
    }

    // Sync pending operations when online
    syncPendingOperations() {
    saveOfflineData(key, data) {
        if (!this.db) return Promise.reject('DB not initialized');

        return new Promise((resolve, reject) => {
            const tx = this.db.transaction('offlineData', 'readwrite');
            const store = tx.objectStore('offlineData');
            const request = store.put({
                id: key,
                data: data,
                timestamp: Date.now()
            });

            request.onerror = () => reject(request.error);
            request.onsuccess = () => resolve(request.result);
        });
    }

    // Get data from IndexedDB
    getOfflineData(key) {
        if (!this.db) return Promise.reject('DB not initialized');

        return new Promise((resolve, reject) => {
            const tx = this.db.transaction('offlineData', 'readonly');
            const store = tx.objectStore('offlineData');
            const request = store.get(key);

            request.onerror = () => reject(request.error);
            request.onsuccess = () => resolve(request.result?.data);
        });
    }

    // Queue an operation for sync when online
    queueOperation(method, url, data = null) {
        if (!this.db) {
            console.error('Cannot queue operation - DB not initialized');
            return Promise.reject('DB not initialized');
        }

        return new Promise((resolve, reject) => {
            const tx = this.db.transaction('syncQueue', 'readwrite');
            const store = tx.objectStore('syncQueue');
            const operation = {
                method: method,
                url: url,
                data: data,
                timestamp: Date.now(),
                retries: 0
            };

            const request = store.add(operation);
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.syncQueue.push(operation);
                resolve(request.result);
            };
        });
    }

    // Sync pending operations when online
    syncPendingOperations() {
        if (!this.isOnline || !this.db) return;

        const tx = this.db.transaction('syncQueue', 'readwrite');
        const store = tx.objectStore('syncQueue');

        return new Promise((resolve) => {
            const request = store.getAll();
            request.onsuccess = () => {
                const operations = request.result;
                if (operations.length === 0) {
                    resolve([]);
                    return;
                }

                Promise.all(operations.map((op, idx) => {
                    return fetch(op.url, {
                        method: op.method,
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.getCookie('csrftoken')
                        },
                        body: op.data ? JSON.stringify(op.data) : null
                    }).then(response => {
                        if (response.ok) {
                            store.delete(op.id || idx);
                            return { success: true, id: op.id };
                        }
                        return { success: false, id: op.id };
                    }).catch(err => {
                        console.error('Sync error:', err);
                        return { success: false, id: op.id };
                    });
                })).then(results => {
                    const synced = results.filter(r => r.success).length;
                    console.log(`Synced ${synced} of ${results.length} operations`);
                    resolve(results);
                });
            };
        });
    }

    // Get CSRF token from cookies
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let cookie of cookies) {
                cookie = cookie.trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Intercept form submissions for offline queueing
    setupFormInterception() {
        document.addEventListener('submit', (event) => {
            const form = event.target;
            const isOfflineQueued = form.getAttribute('data-offline-queue') === 'true';

            if (!this.isOnline && isOfflineQueued) {
                event.preventDefault();
                const formData = new FormData(form);
                const data = Object.fromEntries(formData);
                
                this.queueOperation(form.method, form.action, data)
                    .then(() => {
                        this.showNotification('✓ Saved offline. Will sync when online.', 'info');
                    })
                    .catch(err => {
                        this.showNotification('✗ Failed to save offline', 'error');
                    });
            }
        });
    }

    // Show notification
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = message;
        notification.style.cssText = `
            position: fixed;
            top: 70px;
            right: 20px;
            background: ${type === 'error' ? '#ef5350' : '#52b788'};
            color: white;
            padding: 12px 20px;
            border-radius: 4px;
            z-index: 10000;
            font-size: 14px;
        `;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 3000);
    }

    // Prefetch critical data
    prefetchData(urls) {
        if (!navigator.onLine) return Promise.resolve();

        return Promise.all(
            urls.map(url => {
                return fetch(url)
                    .then(response => response.json())
                    .then(data => this.saveOfflineData(url, data))
                    .catch(err => console.log('Prefetch failed for', url, err));
            })
        );
    }
}

// Initialize Offline Manager when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.offlineManager = new OfflineManager();
    window.offlineManager.setupFormInterception();
});

// Expose methods globally for use in templates
window.saveOfflineData = (key, data) => window.offlineManager?.saveOfflineData(key, data);
window.getOfflineData = (key) => window.offlineManager?.getOfflineData(key);
window.queueOperation = (method, url, data) => window.offlineManager?.queueOperation(method, url, data);
window.syncNow = () => window.offlineManager?.syncPendingOperations();
