(() => {
    function setVisibility(button, visible) {
        const field = document.getElementById(button.dataset.passwordToggle);
        if (!field) return;
        field.type = visible ? 'text' : 'password';
        button.setAttribute('aria-pressed', String(visible));
        const label = (visible ? 'Hide ' : 'Show ') + button.dataset.passwordLabel;
        button.setAttribute('aria-label', label);
        button.title = label;
        button.querySelector('[data-eye-open]').toggleAttribute('hidden', !visible);
        button.querySelector('[data-eye-closed]').toggleAttribute('hidden', visible);
    }
    function syncButton(button) {
        const field = document.getElementById(button.dataset.passwordToggle);
        if (!field) return;
        const hasPassword = field.value.length > 0;
        if (!hasPassword && field.type !== 'password') setVisibility(button, false);
        button.toggleAttribute('hidden', !hasPassword);
        if (hasPassword) setVisibility(button, field.type === 'text');
    }
    const buttons = document.querySelectorAll('[data-password-toggle]');
    for (const button of buttons) {
        button.addEventListener('click', () => {
            const field = document.getElementById(button.dataset.passwordToggle);
            if (field) setVisibility(button, field.type === 'password');
        });
        const field = document.getElementById(button.dataset.passwordToggle);
        field?.addEventListener('input', () => syncButton(button));
        field?.addEventListener('change', () => syncButton(button));
        syncButton(button);
    }
    // Browser password managers can populate after the first page paint.
    window.setTimeout(() => buttons.forEach(syncButton), 100);
    // Do not save a revealed password in a browser history snapshot.
    window.addEventListener('pagehide', () => {
        for (const button of buttons) setVisibility(button, false);
    });
})();
