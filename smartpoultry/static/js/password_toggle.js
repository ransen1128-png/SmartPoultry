(() => {
    function setVisibility(button, visible) {
        const field = document.getElementById(button.dataset.passwordToggle);
        if (!field) return;
        field.type = visible ? 'text' : 'password';
        button.setAttribute('aria-pressed', String(visible));
        const label = (visible ? 'Hide ' : 'Show ') + button.dataset.passwordLabel;
        button.setAttribute('aria-label', label);
        button.title = label;
        button.querySelector('[data-eye-open]').toggleAttribute('hidden', visible);
        button.querySelector('[data-eye-closed]').toggleAttribute('hidden', !visible);
    }
    const buttons = document.querySelectorAll('[data-password-toggle]');
    for (const button of buttons) {
        button.addEventListener('click', () => {
            const field = document.getElementById(button.dataset.passwordToggle);
            if (field) setVisibility(button, field.type === 'password');
        });
    }
    // Do not save a revealed password in a browser history snapshot.
    window.addEventListener('pagehide', () => {
        for (const button of buttons) setVisibility(button, false);
    });
})();
