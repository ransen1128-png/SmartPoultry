(() => {
    const bell = document.getElementById('adminNotificationBell');
    if (!bell) return;
    let loading = false;
    async function refreshNotifications() {
        if (loading || document.hidden) return;
        loading = true;
        try {
            const response = await fetch(bell.dataset.pollUrl, {headers: {'Accept': 'application/json'}, cache: 'no-store'});
            if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
            const data = await response.json();
            const badge = document.getElementById('adminNotificationCount');
            badge.textContent = data.count;
            badge.hidden = data.count === 0;
            document.getElementById('adminFeedbackCount').textContent = data.feedback_count;
            const items = document.getElementById('adminResetNotificationItems');
            items.replaceChildren();
            for (const item of data.requests) {
                const link = document.createElement('a');
                link.className = 'dropdown-item text-wrap py-2';
                link.href = item.url;
                link.textContent = 'Password reset requested by ' + item.username;
                items.append(link);
            }
            if (!data.requests.length) {
                const empty = document.createElement('p');
                empty.className = 'text-muted small px-3 mb-2';
                empty.textContent = 'No pending password reset requests.';
                items.append(empty);
            }
        } catch (_) {
            // Retain the rendered notification list during a temporary outage.
        } finally {
            loading = false;
        }
    }
    bell.addEventListener('show.bs.dropdown', refreshNotifications);
    document.addEventListener('visibilitychange', refreshNotifications);
    window.setInterval(refreshNotifications, 30000);
})();
