// Light/Dark Theme Manager
class ThemeManager {
  constructor() {
    this.htmlElement = document.documentElement;
    this.storageKey = 'army-portal-theme';
    this.prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
    
    this.init();
  }

  init() {
    // Check for saved theme preference or system preference
    const savedTheme = this.getSavedTheme();
    const systemTheme = this.getSystemTheme();
    const theme = savedTheme || systemTheme;

    // Apply theme without transition on load
    this.htmlElement.classList.add('no-transition');
    this.setTheme(theme);
    
    // Remove no-transition class after initial load
    setTimeout(() => {
      this.htmlElement.classList.remove('no-transition');
    }, 50);

    // Listen for system theme changes
    this.prefersDark.addEventListener('change', (e) => {
      if (!this.getSavedTheme()) {
        this.setTheme(e.matches ? 'dark' : 'light');
      }
    });

    // Create and setup toggle button
    this.setupToggleButton();
  }

  getSavedTheme() {
    return localStorage.getItem(this.storageKey);
  }

  getSystemTheme() {
    return this.prefersDark.matches ? 'dark' : 'light';
  }

  setTheme(theme) {
    // Validate theme
    if (theme !== 'light' && theme !== 'dark') {
      theme = 'dark';
    }

    // Set data attribute
    this.htmlElement.setAttribute('data-theme', theme);

    // Update Bootstrap theme
    this.htmlElement.setAttribute('data-bs-theme', theme);

    // Save preference
    localStorage.setItem(this.storageKey, theme);

    // Dispatch event for other listeners
    const event = new CustomEvent('themeChanged', { detail: { theme } });
    window.dispatchEvent(event);

    // Update toggle button icon
    this.updateToggleIcon(theme);
  }

  toggleTheme() {
    const currentTheme = this.htmlElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    this.setTheme(newTheme);
  }

  setupToggleButton() {
    const toggle = document.getElementById('themeToggle');
    if (toggle) {
      toggle.addEventListener('click', () => this.toggleTheme());
      this.updateToggleIcon(this.htmlElement.getAttribute('data-theme'));
    }
  }

  updateToggleIcon(theme) {
    const toggle = document.getElementById('themeToggle');
    if (toggle) {
      const icon = toggle.querySelector('i');
      if (icon) {
        icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
      }
    }
  }
}

// Initialize theme manager on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.themeManager = new ThemeManager();
});

// ============================================
// Offline Status Badge Manager
// ============================================

class OfflineStatusBadge {
  constructor() {
    this.badge = null;
    this.init();
  }

  init() {
    this.createBadge();
    this.updateStatus();
    
    // Listen for online/offline events
    window.addEventListener('online', () => this.updateStatus());
    window.addEventListener('offline', () => this.updateStatus());
  }

  createBadge() {
    // Find the page header right section
    const pageHeader = document.querySelector('.page-header');
    if (!pageHeader) return;

    const rightSection = pageHeader.querySelector('.d-flex.align-items-center.gap-3.no-print');
    if (!rightSection) return;

    // Create badge element
    this.badge = document.createElement('div');
    this.badge.className = 'offline-status-badge online';
    this.badge.innerHTML = `
      <span class="status-dot"></span>
      <span class="badge-text">Online</span>
    `;

    // Insert before the profile link
    rightSection.insertBefore(this.badge, rightSection.firstChild);
  }

  updateStatus() {
    if (!this.badge) return;

    const isOnline = navigator.onLine;
    const badgeText = this.badge.querySelector('.badge-text');

    if (isOnline) {
      this.badge.classList.remove('offline');
      this.badge.classList.add('online');
      badgeText.textContent = 'Online';
    } else {
      this.badge.classList.remove('online');
      this.badge.classList.add('offline');
      badgeText.textContent = 'Offline';
    }
  }
}

// Initialize offline badge on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.offlineStatusBadge = new OfflineStatusBadge();
});

// ============================================
// Integration with Offline Manager
// ============================================

// Update badge when offline manager initializes
document.addEventListener('DOMContentLoaded', () => {
  if (window.offlineManager) {
    // Listen for online/offline from offline manager
    const originalGoOnline = window.offlineManager.goOnline.bind(window.offlineManager);
    const originalGoOffline = window.offlineManager.goOffline.bind(window.offlineManager);

    window.offlineManager.goOnline = function() {
      originalGoOnline();
      if (window.offlineStatusBadge) {
        window.offlineStatusBadge.updateStatus();
      }
    };

    window.offlineManager.goOffline = function() {
      originalGoOffline();
      if (window.offlineStatusBadge) {
        window.offlineStatusBadge.updateStatus();
      }
    };
  }
});

// Keyboard shortcut to toggle theme (Ctrl/Cmd + Shift + T)
document.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key === 'T') {
    event.preventDefault();
    if (window.themeManager) {
      window.themeManager.toggleTheme();
    }
  }
});
