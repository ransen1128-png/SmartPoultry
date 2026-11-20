(() => {
    const config = document.currentScript.dataset;
    const root = document.documentElement;
    const ownerKey = 'smartpoultry-session-owner';
    const logoutKey = 'smartpoultry-session-ended';
    let pending = null;
    let leaving = false;
    function hidePrivateContent() { root.setAttribute('data-session-checking', ''); }
    function goToLogin() {
        leaving = true;
        hidePrivateContent();
        window.location.replace(config.loginUrl);
    }
    function verifySession() {
        hidePrivateContent();
        if (pending || leaving) return pending;
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 15000);
        pending = fetch(config.statusUrl, {
            credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
            headers: {'Accept': 'application/json'},
        }).then(async response => {
            if (!response.ok) throw new Error('Session check failed');
            const session = await response.json();
            if (!session.authenticated || String(session.user_id) !== config.userId) {
                goToLogin();
            } else if (!leaving) {
                root.removeAttribute('data-session-checking');
            }
        }).catch(goToLogin).finally(() => {
            window.clearTimeout(timeout);
            pending = null;
        });
        return pending;
    }
    // Mask the document before it can become a browser Back/Forward snapshot.
    window.addEventListener('pagehide', hidePrivateContent);
    window.addEventListener('pageshow', event => {
        const navigation = performance.getEntriesByType('navigation')[0];
        if (event.persisted || navigation?.type === 'back_forward') verifySession();
        else if (!leaving && !pending) root.removeAttribute('data-session-checking');
    });
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) verifySession();
    });
    window.addEventListener('focus', verifySession);
    window.addEventListener('storage', event => {
        if (event.key === logoutKey || (event.key === ownerKey && event.newValue !== config.userId)) verifySession();
    });
    try { localStorage.setItem(ownerKey, config.userId); } catch (_) { /* Storage may be disabled. */ }

    document.addEventListener('click', async event => {
        const link = event.target.closest('a[href]');
        if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        const target = new URL(link.href, window.location.href);
        if (target.origin !== location.origin || target.pathname !== config.logoutUrl) return;
        event.preventDefault();
        if (leaving) return;
        leaving = true;
        hidePrivateContent();
        const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value
            || document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.slice('csrftoken='.length) || '';
        try {
            const response = await fetch(config.logoutUrl, {
                method: 'POST', credentials: 'same-origin', cache: 'no-store',
                headers: {'Accept': 'application/json', 'X-CSRFToken': decodeURIComponent(token)},
            });
            if (!response.ok || !(await response.json()).logged_out) throw new Error('Logout failed');
            try { localStorage.setItem(logoutKey, String(Date.now()) + Math.random()); } catch (_) { /* Back checks still work. */ }
            goToLogin();
        } catch (_) {
            // Use the normal server logout when a fetch or CSRF check fails.
            window.location.replace(config.logoutUrl);
        }
    });
})();
