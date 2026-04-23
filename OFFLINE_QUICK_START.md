# Offline & Online Mode - Quick Start Guide

## What's New? 🎯

Your Army Portal now works **completely offline and online**! Here's what was added:

---

## 🚀 Quick Features

### ✅ Works Anywhere, Anytime
- No internet? No problem! Keep working
- All changes saved locally, sync when online
- Automatic online/offline detection

### ✅ Install as App
- Use on desktop, mobile, tablet
- Access from home screen
- No browser needed (PWA)

### ✅ Automatic Sync
- Changes queue when offline
- Auto-sync when reconnected
- No manual work needed

### ✅ Smart Caching
- Pages cached automatically
- Data cached for offline use
- Old cache auto-cleaned

---

## ⚡ Getting Started (3 Steps)

### Step 1: Update Django Settings
No changes needed! Middleware already added to `settings.py`

### Step 2: Install Service Worker
Service worker auto-registers on page load. Check console:
```
✓ Service Worker registered
```

### Step 3: Test Offline
1. Open DevTools (F12)
2. Go to Network tab
3. Check "Offline"
4. Try using the app!

---

## 📱 Install as PWA

### Chrome/Edge (Desktop)
1. Click address bar icon: "Install app"
2. Click "Install"
3. Done! App is in your menu

### Android/Chrome
1. Menu (⋮) → "Install app"
2. Tap "Install"
3. Opens from home screen

### iPhone/Safari
1. Share button → "Add to Home Screen"
2. Name it "Army Portal"
3. Opens from home screen

---

## 📊 Files Added

```
✓ static/js/service-worker.js        - Caching & offline logic
✓ static/js/offline-manager.js        - Offline manager
✓ static/css/offline.css               - Offline UI styles  
✓ static/manifest.json                - PWA config
✓ templates/offline.html              - Offline page
✓ logs/offline_middleware.py          - Django middleware
✓ core/offline_views.py               - Offline API views
✓ army_portal/urls.py                 - Offline routes (UPDATED)
✓ army_portal/settings.py             - Middleware added (UPDATED)
✓ templates/base.html                 - Scripts added (UPDATED)
```

---

## 🎮 How to Use

### Online Mode (Normal)
- Everything works as before
- Faster with cached static assets
- Better battery life (cached assets)

### Offline Mode
```
1. Fill form/enter marks
2. Click Submit
3. See: "✓ Saved offline"
4. Changes stay local
5. Auto-sync when online
```

### Check Status
Look at top of page:
- 🟢 Green = Online
- 🔴 Red = Offline

---

## 🔧 Configuration

### Enable/Disable
In `settings.py`:
```python
OFFLINE_MODE_ENABLED = True  # Set to False to disable
```

### Cache Timeout
```python
OFFLINE_CACHE_TIMEOUT = 3600  # seconds (1 hour)
```

### Max Cache Size
```python
OFFLINE_MAX_CACHE_SIZE = 50 * 1024 * 1024  # 50MB
```

---

## 🐛 Troubleshooting

### Service Worker Not Working?
```javascript
// In console, check registration:
navigator.serviceWorker.getRegistrations()
  .then(r => console.log(r))
```

### Cache Not Updating?
1. DevTools → Application → Service Workers
2. Check "Update on reload"
3. Refresh page

### PWA Not Installing?
- Must use HTTPS (or localhost)
- Check manifest.json is valid
- Requires icons (in manifest)

### Manual Sync
```javascript
// Force sync in console:
window.offlineManager.syncPendingOperations();
```

---

## 📋 API Endpoints (New)

```
GET  /offline/                    - Offline page
POST /api/offline/sync/           - Sync queued operations
GET  /api/offline/cache/          - Cache status
POST /api/offline/cache/          - Cache data
GET  /api/offline/status/         - Check if online
```

---

## ⚠️ Important Notes

1. **First Load Required**
   - App must load once online to cache assets
   - Then works offline

2. **Storage Limits**
   - Device storage determines cache size
   - Auto-clears old data

3. **Security**
   - Use HTTPS in production
   - Data stored locally on device
   - Clear cache on shared devices

4. **Real-time Updates**
   - Offline = no live updates
   - Sync updates when reconnected

---

## 📚 Learn More

Read the full guide: [OFFLINE_MODE_GUIDE.md](OFFLINE_MODE_GUIDE.md)

---

## 🎉 Benefits

| Feature | Before | After |
|---------|--------|-------|
| Works Offline | ❌ | ✅ |
| Caching | ❌ | ✅ |
| PWA Install | ❌ | ✅ |
| Auto Sync | ❌ | ✅ |
| Offline Forms | ❌ | ✅ |
| Background Sync | ❌ | ✅ |

---

## 🚀 Next Steps

1. **Test Offline**
   - Turn off internet
   - Use the app
   - Check sync when online

2. **Install as PWA**
   - Use browser menu
   - "Install app"
   - Access from home screen

3. **Share with Team**
   - Everyone can use offline
   - No special setup needed
   - Auto-works!

---

**Ready to go offline? You're all set! 🎯**

For help, see: [OFFLINE_MODE_GUIDE.md](OFFLINE_MODE_GUIDE.md)

---

**Version:** 1.0  
**Date:** April 20, 2026  
**Status:** Production Ready ✅
