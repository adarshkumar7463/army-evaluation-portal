# Offline Mode Guide - Army Evaluation Portal

## Overview

The Army Evaluation Portal now supports **complete offline functionality**. Users can continue working without an internet connection, and all changes will automatically sync when they reconnect.

---

## Features

### 1. **Offline Detection**
- Real-time online/offline status indicator
- Visual indicator at the top of every page (green = online, red = offline)
- Automatic detection of network changes

### 2. **Progressive Web App (PWA)**
- Install the application on your device
- Works offline like a native app
- Automatic updates when online
- Quick access from home screen (mobile)

### 3. **Automatic Caching**
- **Static Assets**: CSS, JavaScript, images cached on first load
- **API Responses**: Recent data cached automatically
- **User Data**: Previously viewed pages cached for offline access
- **Smart Cache Management**: Old cached data automatically cleared

### 4. **Offline Queuing**
- Fill and submit forms while offline
- Changes are queued and automatically synced when online
- Visual indicator shows when data is queued
- Notifications confirm saved status

### 5. **IndexedDB Storage**
- Local database for storing offline data
- Persistent storage even after browser closes
- Unlimited storage (depends on device)
- Automatic sync when reconnected

### 6. **Service Worker**
- Background sync of pending operations
- Efficient resource loading
- Network-first strategy for dynamic content
- Cache-first strategy for static assets

---

## How to Use

### Installing as a PWA

**On Desktop (Chrome/Edge):**
1. Click the "Install app" icon in the address bar
2. Click "Install"
3. The app will appear in your applications menu

**On Mobile (Chrome/Firefox):**
1. Open the menu (three dots)
2. Tap "Install app" or "Add to Home screen"
3. The app will appear on your home screen

### Working Offline

**Viewing Content:**
- All previously loaded pages are cached
- Scroll through cached data without internet
- Charts and dashboards load from cache

**Submitting Data:**
1. Fill in a form or enter evaluation marks
2. Click Submit
3. System automatically queues the operation
4. A notification confirms: "Saved offline. Will sync when online."
5. When online, changes sync automatically

**Checking Sync Status:**
- Green indicator at top = data is syncing
- "✓ Online" = connected to server
- "🔴 Offline Mode" = working offline

### Manual Sync

If you want to manually trigger sync:
```javascript
// In browser console
window.offlineManager.syncPendingOperations();
```

---

## Technical Architecture

### File Structure

```
army_portal/
├── static/
│   ├── js/
│   │   ├── service-worker.js          # SW for caching
│   │   └── offline-manager.js          # Offline logic
│   ├── css/
│   │   └── offline.css                 # Offline UI styles
│   └── manifest.json                   # PWA manifest
├── templates/
│   └── offline.html                    # Offline fallback page
├── logs/
│   └── offline_middleware.py           # Django middleware
├── core/
│   └── offline_views.py                # Offline API views
└── army_portal/
    ├── settings.py                     # Updated with middleware
    └── urls.py                         # Offline routes added
```

### Caching Strategy

**Service Worker uses two strategies:**

1. **Network First** (for dynamic content)
   - Try network first
   - Fall back to cache if offline
   - Cache successful responses
   - Used for HTML pages and API calls

2. **Cache First** (for static assets)
   - Check cache first
   - Network only if not cached
   - Update cache from network
   - Used for CSS, JS, images

### Storage

**IndexedDB Databases:**
- `offlineData`: Stores cached API responses
- `syncQueue`: Stores operations pending sync
- `pendingOperations`: Tracks pending requests

---

## API Endpoints

### Offline Sync
```
POST /api/offline/sync/
Body: {
  "operations": [
    {
      "method": "POST",
      "url": "/evaluation/1/marks/",
      "data": {...}
    }
  ]
}
```

### Cache Management
```
GET  /api/offline/cache/        # List cached items
POST /api/offline/cache/        # Cache new item
DELETE /api/offline/cache/      # Clear cache
```

### Status Check
```
GET /api/offline/status/        # Check if server is online
```

---

## Configuration

### Enable/Disable Offline Features

**In `settings.py`:**

```python
# Offline Mode Settings (Optional)
OFFLINE_MODE_ENABLED = True  # Default: True
OFFLINE_CACHE_TIMEOUT = 3600  # Seconds (1 hour)
OFFLINE_MAX_CACHE_SIZE = 50 * 1024 * 1024  # 50MB
```

### Customizing Offline UI

Edit `static/css/offline.css` to customize:
- Indicator color and position
- Notification styles
- Offline modal appearance
- Cache info display

---

## Browser Support

| Browser | Offline | PWA | Service Worker |
|---------|---------|-----|----------------|
| Chrome  | ✓       | ✓   | ✓             |
| Firefox | ✓       | ✓   | ✓             |
| Safari  | ✓       | ⚠️  | ⚠️            |
| Edge    | ✓       | ✓   | ✓             |
| Opera   | ✓       | ✓   | ✓             |

*⚠️ = Limited support, but functional*

---

## Troubleshooting

### Service Worker Not Registering

1. Check browser console for errors
2. Ensure HTTPS is used (or localhost for development)
3. Clear browser cache and reload

```javascript
// In console:
navigator.serviceWorker.getRegistrations()
  .then(regs => console.log('Registered SWs:', regs))
```

### Cache Not Updating

1. Open DevTools → Application → Service Workers
2. Check "Update on reload"
3. Clear site data

### Sync Not Working

1. Check IndexedDB in DevTools
2. Ensure you have pending operations
3. Manually trigger: `window.offlineManager.syncPendingOperations()`

### PWA Not Installing

1. Must be HTTPS (or localhost)
2. Manifest.json must be valid
3. Service Worker must be registered
4. Requires 192x192 and 512x512 icons

---

## Performance Tips

### For Users

1. **Prefetch Important Pages**
   - Visit dashboard and key pages while online
   - Data will be cached for offline use

2. **Manage Storage**
   - Offline cache has size limits
   - Old data auto-clears after 24 hours
   - Manually clear in Settings if needed

3. **Monitor Sync**
   - Watch for sync notifications
   - Ensure all changes complete before disconnecting
   - Check sync status before important actions

### For Developers

1. **Add Offline Queueing to Forms**
   ```html
   <form method="POST" data-offline-queue="true">
     <!-- Form fields -->
   </form>
   ```

2. **Prefetch Critical Data**
   ```javascript
   window.offlineManager.prefetchData([
     '/api/evaluations/',
     '/api/departments/',
     '/api/users/'
   ])
   ```

3. **Monitor Cache Size**
   ```javascript
   // Check in console
   caches.keys().then(names => {
     names.forEach(name => {
       caches.open(name).then(cache => {
         cache.keys().then(requests => {
           console.log(`${name}: ${requests.length} items`);
         });
       });
     });
   });
   ```

---

## Security Considerations

### Sensitive Data
- IndexedDB is **local** - not encrypted
- Use HTTPS to prevent interception
- Clear cache before public computer use

### Authentication
- Login tokens cached in sessionStorage
- Auto-clear on logout
- Offline actions respect user permissions

### CSRF Protection
- CSRF tokens maintained offline
- Automatically included in sync operations

---

## Limitations

1. **Cannot create new resources offline**
   - Must be connected to create new items
   - Can edit existing cached items

2. **Real-time updates**
   - Live data updates paused offline
   - Auto-sync when reconnected

3. **File uploads**
   - Must be online to upload files
   - Can be queued for background upload

4. **Large datasets**
   - May exceed device storage
   - Older data auto-cleared

---

## Future Enhancements

- [ ] Background sync API for file uploads
- [ ] Conflict resolution for simultaneous edits
- [ ] Encrypted offline storage option
- [ ] Offline collaborative editing
- [ ] Periodic sync statistics
- [ ] Custom cache size management

---

## Support & Debugging

### Enable Debug Mode
```javascript
// In console
localStorage.setItem('DEBUG_OFFLINE', 'true');
// Service Worker will log all operations
```

### View Service Worker Logs
```javascript
navigator.serviceWorker.controller.postMessage({
  action: 'getDebugInfo'
});
```

### Uninstall/Reset Offline Mode
```javascript
// Clear everything
if ('caches' in window) {
  caches.keys().then(names => {
    names.forEach(name => caches.delete(name));
  });
}
// Then restart browser
```

---

## FAQ

**Q: Will my data be lost if offline?**
A: No, data is saved locally and synced when online.

**Q: Can I use offline with multiple tabs?**
A: Yes, but sync is coordinated across tabs to avoid conflicts.

**Q: How much data can be cached?**
A: Typically 50MB-100MB depending on device.

**Q: Does offline mode affect performance?**
A: No, it may improve performance by using cached data.

**Q: What happens if sync fails?**
A: Operations remain queued and retry when online.

---

## Contact & Support

For issues or feature requests, contact the IT team.

---

**Last Updated:** April 20, 2026
**Version:** 1.0
