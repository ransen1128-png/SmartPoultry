(() => {
    const form = document.getElementById('resetPasswordForm');
    const password = form.elements.new_password1;
    const confirm = form.elements.new_password2;
    const match = document.getElementById('resetPasswordMatch');
    const summary = document.getElementById('resetChecklistStatus');
    function update() {
        const checks = {
            length: password.value.length >= 8,
            uppercase: /[A-Z]/.test(password.value),
            lowercase: /[a-z]/.test(password.value),
            number: /[0-9]/.test(password.value),
            symbol: /[!-/:-@\[-`{-~]/.test(password.value),
        };
        document.querySelectorAll('[data-password-rule]').forEach(rule => {
            rule.dataset.met = String(checks[rule.dataset.passwordRule]);
        });
        summary.textContent = `${Object.values(checks).filter(Boolean).length} of 5 password requirements met.`;
        password.setCustomValidity(password.value && !Object.values(checks).every(Boolean)
            ? 'Use at least 8 characters with uppercase and lowercase letters, a number, and a special symbol.' : '');
        const same = confirm.value === password.value;
        if (confirm.value) {
            match.textContent = same ? 'Password match' : 'Password not match';
            match.classList.toggle('text-success', same);
            match.classList.toggle('text-danger', !same);
        } else if (!confirm.hasAttribute('data-server-error')) {
            match.textContent = '';
            match.classList.remove('text-success', 'text-danger');
        }
        confirm.setCustomValidity(confirm.value && !same ? 'Password not match' : '');
    }
    if (match.textContent.trim()) confirm.dataset.serverError = 'true';
    [password, confirm].forEach(field => field.addEventListener('input', () => {
        delete confirm.dataset.serverError;
        field.classList.remove('is-invalid');
        field.removeAttribute('aria-invalid');
        document.getElementById('resetPasswordRequired').textContent = '';
        update();
    }));
    form.addEventListener('invalid', event => {
        event.preventDefault();
        event.target.classList.add('is-invalid');
        event.target.setAttribute('aria-invalid', 'true');
        if (event.target === confirm) {
            match.textContent = 'Password not match';
            match.classList.remove('text-success');
            match.classList.add('text-danger');
        } else if (!password.value) {
            document.getElementById('resetPasswordRequired').textContent = 'New password is required.';
        }
        requestAnimationFrame(() => form.querySelector(':invalid')?.focus());
    }, true);
    form.addEventListener('submit', event => {
        update();
        if (!form.reportValidity()) event.preventDefault();
    });
    update();
})();
