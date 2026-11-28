(() => {
    const password = document.getElementById('password');
    const confirm = document.getElementById('password2');
    const feedback = document.getElementById('passwordMatch');
    const firstQuestion = document.getElementById('id_question_one');
    const secondQuestion = document.getElementById('id_question_two');
    const recoveryError = document.getElementById('recoveryQuestionError');

    function updateRecoveryQuestions() {
        const duplicate = firstQuestion.value !== '' && firstQuestion.value === secondQuestion.value;
        const message = duplicate ? 'Choose two different recovery questions.' : '';
        secondQuestion.setCustomValidity(message);
        recoveryError.textContent = message;
        secondQuestion.classList.toggle('is-invalid', duplicate);
        if (duplicate) secondQuestion.setAttribute('aria-invalid', 'true');
        else secondQuestion.removeAttribute('aria-invalid');
    }
    function update() {
        const checks = {
            length: password.value.length >= 8,
            uppercase: /[A-Z]/.test(password.value),
            lowercase: /[a-z]/.test(password.value),
            number: /[0-9]/.test(password.value),
            symbol: /[!-/:-@\[-`{-~]/.test(password.value),
        };
        for (const rule of document.querySelectorAll('[data-rule]')) {
            const met = checks[rule.dataset.rule];
            rule.dataset.met = String(met);
            const status = rule.querySelector('[data-rule-status]');
            if (status) status.textContent = met ? 'Met: ' : 'Not met: ';
        }
        const summary = document.getElementById('passwordChecklistStatus');
        const summaryText = Object.values(checks).filter(Boolean).length + ' of 5 password requirements met.';
        if (summary && summary.textContent !== summaryText) summary.textContent = summaryText;
        password.setCustomValidity(password.value && !Object.values(checks).every(Boolean)
            ? 'Use at least 8 characters with an uppercase letter, a lowercase letter, a number, and a special symbol.' : '');
        const mismatch = confirm.value && confirm.value !== password.value;
        confirm.setCustomValidity(mismatch ? 'Passwords do not match.' : '');
        feedback.textContent = confirm.value ? (mismatch ? 'Passwords do not match.' : 'Passwords match.') : 'Re-enter your password to make sure it matches.';
        feedback.style.color = confirm.value ? (mismatch ? '#b42318' : '#15803d') : '';
        feedback.dataset.state = mismatch ? 'error' : confirm.value ? 'success' : 'neutral';
        confirm.classList.toggle('is-invalid', Boolean(mismatch));
        if (mismatch) confirm.setAttribute('aria-invalid', 'true');
        else confirm.removeAttribute('aria-invalid');
    }
    // This field owns its single feedback line; other fields retain shared validation.
    confirm.addEventListener('invalid', event => {
        event.preventDefault();
        feedback.textContent = confirm.validationMessage;
        feedback.style.color = '#b42318';
        feedback.dataset.state = 'error';
        confirm.classList.add('is-invalid');
        confirm.setAttribute('aria-invalid', 'true');
        requestAnimationFrame(() => {
            if (password.form.querySelector(':invalid') === confirm) confirm.focus();
        });
    });
    password.addEventListener('input', update);
    confirm.addEventListener('input', update);
    password.form.addEventListener('submit', (event) => {
        update();
        updateRecoveryQuestions();
        if (!password.form.reportValidity()) event.preventDefault();
    });
    firstQuestion.addEventListener('change', updateRecoveryQuestions);
    secondQuestion.addEventListener('change', updateRecoveryQuestions);
    secondQuestion.setAttribute('aria-describedby', recoveryError.id);
    secondQuestion.setAttribute('data-inline-validation', '');
    secondQuestion.addEventListener('invalid', event => {
        if (!secondQuestion.validity.customError) return;
        event.preventDefault();
        if (password.form.querySelector(':invalid') === secondQuestion) secondQuestion.focus();
    });
    updateRecoveryQuestions();
    update();
})();
