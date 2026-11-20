(() => {
    const config = document.currentScript.dataset;
    const retry = document.getElementById('retryLogoutCleanup');
    let pending = false;
    async function finishLogout() {
        if (pending) return;
        pending = true;
        retry.hidden = true;
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 15000);
        try {
            // This response clears the bfcache after the old document is inactive.
            const response = await fetch(config.statusUrl, {credentials: 'same-origin', cache: 'no-store', signal: controller.signal, headers: {'Accept': 'application/json'}});
            if (!response.ok) throw new Error('Session check failed');
            const session = await response.json();
            if (!session.authenticated) {
                try {
                    localStorage.removeItem('smartpoultry-session-owner');
                    localStorage.setItem('smartpoultry-session-ended', String(Date.now()) + Math.random());
                } catch (_) { /* Server session checks work without local storage. */ }
            }
            window.location.replace(config.loginUrl);
        } catch (_) {
            document.getElementById('logoutProgress').textContent = 'Your session is signed out. Retry to finish clearing saved pages.';
            retry.hidden = false;
        } finally {
            clearTimeout(timer);
            pending = false;
        }
    }
    retry.addEventListener('click', finishLogout);
    window.addEventListener('pageshow', finishLogout);
})();
