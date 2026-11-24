(function () {
    'use strict';

    var root = document.documentElement;
    var sidebar = document.getElementById('appSidebar');
    var toggle = document.getElementById('sidebarToggle');
    if (!sidebar || !toggle) return;

    // Phones: the menu stays closed behind a Menu button so each page opens on its content.
    var mobileToggle = document.getElementById('sidebarMobileToggle');
    if (mobileToggle) {
        mobileToggle.addEventListener('click', function () {
            var open = sidebar.classList.toggle('sidebar-mobile-open');
            mobileToggle.setAttribute('aria-expanded', String(open));
            mobileToggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
            mobileToggle.querySelector('i').className = open ? 'bi bi-x-lg' : 'bi bi-list';
        });
    }

    var STORAGE_KEY = 'sp-sidebar-collapsed';
    var tooltip = document.createElement('div');
    tooltip.className = 'sidebar-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    tooltip.hidden = true;
    document.body.appendChild(tooltip);

    function isCollapsed() {
        return root.classList.contains('sidebar-collapsed');
    }

    function syncToggle() {
        var collapsed = isCollapsed();
        var label = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
        toggle.setAttribute('aria-expanded', String(!collapsed));
        toggle.setAttribute('aria-label', label);
        toggle.setAttribute('data-label', label);
        toggle.querySelector('i').className = collapsed ? 'bi bi-chevron-double-right' : 'bi bi-chevron-double-left';
    }

    function hideTooltip() {
        tooltip.hidden = true;
    }

    function showTooltip(target) {
        var label = target.getAttribute('data-label');
        // Link labels only need a tooltip when the text is hidden; the toggle always gets one.
        if (!label || (!isCollapsed() && target !== toggle)) return hideTooltip();
        tooltip.textContent = label;
        tooltip.hidden = false;
        var rect = target.getBoundingClientRect();
        tooltip.style.left = (rect.right + 10) + 'px';
        tooltip.style.top = (rect.top + rect.height / 2 - tooltip.offsetHeight / 2) + 'px';
    }

    toggle.addEventListener('click', function () {
        root.classList.toggle('sidebar-collapsed');
        try { localStorage.setItem(STORAGE_KEY, isCollapsed() ? '1' : '0'); } catch (e) { /* storage unavailable */ }
        syncToggle();
        showTooltip(toggle);
    });

    sidebar.addEventListener('mouseover', function (event) {
        var target = event.target.closest('[data-label]');
        if (target && sidebar.contains(target)) showTooltip(target); else hideTooltip();
    });
    sidebar.addEventListener('mouseleave', hideTooltip);
    sidebar.addEventListener('focusin', function (event) {
        var target = event.target.closest('[data-label]');
        if (target) showTooltip(target);
    });
    sidebar.addEventListener('focusout', hideTooltip);
    sidebar.addEventListener('scroll', hideTooltip, { passive: true });

    syncToggle();
})();
