/* Login uses field-specific validation and a generic authentication error. */
(() => {
    const form = document.getElementById('loginForm');
    if (!form) return;
    const email = document.getElementById('email');
    const password = document.getElementById('password');
    function message(field, text) {
        const feedback = document.getElementById(field.id + 'Error');
        feedback.textContent = text;feedback.hidden = !text;
        field.classList.toggle('is-invalid', !!text);
        if (text) field.setAttribute('aria-invalid', 'true');else field.removeAttribute('aria-invalid');
    }
    function clearCredentialError() {
        if (form.dataset.credentialError !== 'true') return;
        message(email, '');message(password, '');
        email.setAttribute('aria-describedby', 'emailError');
        form.dataset.credentialError = 'false';
    }
    form.addEventListener('submit', event => {
        clearCredentialError();
        const emailError = !email.value.trim() ? 'Email is required.' : email.validity.typeMismatch ? 'Enter a valid email address.' : '';
        const passwordError = !password.value ? 'Password is required.' : '';
        message(email, emailError);message(password, passwordError);
        if (emailError || passwordError) {
            event.preventDefault();
            (emailError ? email : password).focus();
        }
    });
    for (const field of [email, password]) field.addEventListener('input', () => {
        clearCredentialError();
        message(field, '');
    });
})();
