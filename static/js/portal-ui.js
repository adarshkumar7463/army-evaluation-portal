(function () {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ready(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback);
    } else {
      callback();
    }
  }

  function addRevealMotion() {
    const selector = [
      '.army-card',
      '.metric-card',
      '.chart-box',
      '.search-wrapper',
      '.reg-card',
      '.dept-stat-card',
      '.default-stat-item',
      '.sub-event-card',
      '.alert'
    ].join(',');
    const items = Array.from(document.querySelectorAll(selector));
    if (!items.length) return;

    if (prefersReducedMotion || !('IntersectionObserver' in window)) {
      items.forEach((item) => item.classList.add('is-visible'));
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });

    items.forEach((item, index) => {
      item.classList.add('portal-reveal');
      item.style.transitionDelay = `${Math.min(index * 18, 180)}ms`;
      observer.observe(item);
    });
  }

  function addRipples() {
    document.addEventListener('click', (event) => {
      const target = event.target.closest('.btn, button, .sidebar-link, .nav-link, .page-link, .metric-card, .stat-card, .dept-stat-card');
      if (!target || prefersReducedMotion) return;

      const rect = target.getBoundingClientRect();
      const ripple = document.createElement('span');
      const size = Math.max(rect.width, rect.height);
      ripple.className = 'portal-ripple';
      ripple.style.width = `${size}px`;
      ripple.style.height = `${size}px`;
      ripple.style.left = `${event.clientX - rect.left}px`;
      ripple.style.top = `${event.clientY - rect.top}px`;

      const position = getComputedStyle(target).position;
      if (position === 'static') target.style.position = 'relative';
      target.style.overflow = 'hidden';
      target.appendChild(ripple);
      ripple.addEventListener('animationend', () => ripple.remove());
    });
  }

  function animateNumbers() {
    if (prefersReducedMotion) return;

    const numberNodes = document.querySelectorAll('.stat-value, .metric-value, .dept-stat-value, .default-stat-value, .distribution-number');
    numberNodes.forEach((node) => {
      const raw = node.textContent.trim().replace(/,/g, '');
      if (!/^\d+(\.\d+)?%?$/.test(raw)) return;

      const isPercent = raw.endsWith('%');
      const target = Number(raw.replace('%', ''));
      if (!Number.isFinite(target) || target === 0) return;

      const decimals = raw.includes('.') ? 1 : 0;
      const duration = 650;
      const start = performance.now();

      function tick(now) {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const value = target * eased;
        node.textContent = `${value.toFixed(decimals)}${isPercent ? '%' : ''}`;
        if (progress < 1) requestAnimationFrame(tick);
      }

      requestAnimationFrame(tick);
    });
  }

  function improveDataSurfaces() {
    document.querySelectorAll('tbody tr').forEach((row) => {
      row.classList.add('data-glow');
    });

    document.querySelectorAll('table').forEach((table) => {
      const wrapper = table.closest('.table-responsive, .agniveer-table-container, [style*="overflow"]');
      if (wrapper) wrapper.setAttribute('tabindex', '0');
    });
  }

  function addFormMicroInteractions() {
    document.addEventListener('focusin', (event) => {
      const field = event.target.closest('input, select, textarea');
      if (!field) return;
      const group = field.closest('.col-md-2, .col-md-3, .col-md-4, .col-md-5, .col-md-6, .col-md-7, .col-md-8, .col-md-12, .mb-3');
      if (group) group.classList.add('field-active');
    });

    document.addEventListener('focusout', (event) => {
      const field = event.target.closest('input, select, textarea');
      if (!field) return;
      const group = field.closest('.field-active');
      if (group) group.classList.remove('field-active');
    });
  }

  function refineCharts() {
    if (!window.Chart) return;

    const styles = getComputedStyle(document.documentElement);
    const text = styles.getPropertyValue('--portal-text').trim() || '#173546';
    const muted = styles.getPropertyValue('--portal-muted').trim() || '#526d7c';
    const line = styles.getPropertyValue('--portal-line').trim() || 'rgba(15, 95, 135, 0.24)';

    Chart.defaults.color = text;
    Chart.defaults.borderColor = line;
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.font.size = 10;
    Chart.defaults.responsive = true;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.plugins.legend.labels.color = muted;
    Chart.defaults.plugins.legend.labels.boxWidth = 10;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(20, 35, 45, 0.92)';
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;

    document.querySelectorAll('canvas').forEach((canvas) => {
      const box = canvas.closest('.chart-box, .army-card, .pie-chart-canvas');
      if (box) box.classList.add('portal-chart-shell');
      canvas.removeAttribute('height');
      canvas.style.width = '100%';
      const chart = Chart.getChart(canvas);
      if (chart) {
        chart.options.maintainAspectRatio = false;
        chart.options.responsive = true;
        if (chart.options.plugins?.legend?.labels) {
          chart.options.plugins.legend.labels.color = muted;
          chart.options.plugins.legend.labels.boxWidth = 10;
          chart.options.plugins.legend.labels.usePointStyle = true;
        }
        chart.resize();
        chart.update('none');
      }
    });
  }

  function initSidebarToggle() {
    const isCollapsible = document.body.classList.contains('portal-collapsible-sidebar');
    const expandBtn = document.getElementById('sidebarExpandBtn');
    const brand = document.querySelector('.sidebar-brand');
    const savedExpanded = localStorage.getItem('portal-sidebar-expanded') === 'true';
    document.body.classList.toggle('sidebar-expanded', !isCollapsible || savedExpanded);

    const toggleSidebarFn = () => {
      if (!document.body.classList.contains('portal-collapsible-sidebar')) return;
      const expanded = !document.body.classList.contains('sidebar-expanded');
      document.body.classList.toggle('sidebar-expanded', expanded);
      localStorage.setItem('portal-sidebar-expanded', String(expanded));
      if (expandBtn) {
        expandBtn.setAttribute('title', expanded ? 'Collapse navigation' : 'Expand navigation');
        expandBtn.setAttribute('aria-label', expanded ? 'Collapse navigation' : 'Expand navigation');
      }
    };

    if (brand) {
      brand.style.cursor = 'pointer';
      brand.addEventListener('click', (e) => {
        if (e.target.closest('#sidebarExpandBtn')) return;
        toggleSidebarFn();
      });
    }

    if (expandBtn) {
      expandBtn.style.display = 'none';
      expandBtn.addEventListener('click', toggleSidebarFn);
    }
  }

  refineCharts();

  ready(() => {
    document.documentElement.classList.add('portal-ui-ready');
    initSidebarToggle();
    refineCharts();
    addRevealMotion();
    addRipples();
    animateNumbers();
    improveDataSurfaces();
    addFormMicroInteractions();
    window.addEventListener('themeChanged', refineCharts);
  });
})();
