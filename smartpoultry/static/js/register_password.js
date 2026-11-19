(() => {
    const password = document.getElementById('password');
    const confirm = document.getElementById('password2');
    const feedback = document.getElementById('passwordMatch');
    function update() {
        const checks = {
            length: password.value.length >= 8,
            uppercase: /[A-Z]/.test(password.value),
            lowercase: /[a-z]/.test(password.value),
            number: /[0-9]/.test(password.value),
            symbol: /[!-/:-@\[-`{-~]/.test(password.value),
        };
        for (const rule of document.querySelectorAll('[data-rule]')) {
            rule.dataset.met = String(checks[rule.dataset.rule]);
        }
        password.setCustomValidity(password.value && !Object.values(checks).every(Boolean)
            ? 'Use at least 8 characters with an uppercase letter, a lowercase letter, a number, and a special symbol.' : '');
        const mismatch = confirm.value && confirm.value !== password.value;
        confirm.setCustomValidity(mismatch ? 'Passwords do not match.' : '');
        feedback.textContent = confirm.value ? (mismatch ? 'Passwords do not match.' : 'Passwords match.') : 'Re-enter your password to make sure it matches.';
        feedback.style.color = confirm.value ? (mismatch ? '#b42318' : '#15803d') : '';
    }
    password.addEventListener('input', update);
    confirm.addEventListener('input', update);
    password.form.addEventListener('submit', (event) => {
        update();
        if (!password.form.reportValidity()) event.preventDefault();
    });
    update();
})();
