/* Login uses field messages; other forms retain shared popup validation. */
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
    form.addEventListener('submit', event => {
        const emailError = !email.value.trim() ? 'Email required' : email.validity.typeMismatch ? 'Enter a valid email address' : '';
        const passwordError = !password.value ? 'Password required' : '';
        message(email, emailError);message(password, passwordError);
        if (emailError || passwordError) {
            event.preventDefault();
            (emailError ? email : password).focus();
        }
    });
    for (const field of [email, password]) field.addEventListener('input', () => {
        message(field, '');
        if (document.getElementById('passwordError').textContent === 'Incorrect Email and Password. Please try again') message(password, '');
    });
})();
