/* Shared dialogs. Native dialog supplies focus trapping, Escape and a top layer
   above editing modals, with no external library or network dependency. */
(() => {
    'use strict';
    if (window.SmartPoultry) return;
    const dialog = document.getElementById('appDialog');
    const confirmation = document.getElementById('appConfirmDialog');
    const queue = [];
    let active = null;
    let lastNotice = null;
    let lastForm = null;
    let errorId = 0;
    let invalidFocusPending = false;
    const fieldMessages = new WeakMap();
    const pendingKey = 'smartpoultry-popup';
    const safe = value => {
        const text = String(value || '').trim();
        return /traceback|<!doctype|<html|exception at|sqlstate|postgresql:\/\/|secret_key|api[_ -]?key\s*[:=]/i.test(text)
            ? 'The request could not be completed. Please try again.' : text.slice(0, 700);
    };
    function classify(message, type = 'info', title = '') {
        const text = `${title} ${message}`.toLowerCase();
        if (/account-created/.test(type)) return ['success', 'Registration Successful!'];
        if (type.includes('success')) return ['success', /password/.test(text) ? 'Password Changed Successfully!' : /delet/.test(text) ? 'Successfully Deleted!' : /add|creat/.test(text) ? 'Successfully Added!' : /updat/.test(text) ? 'Successfully Updated!' : 'Changes Saved Successfully!'];
        if (/password.*(match|mismatch)/.test(text)) return ['warning', 'Passwords Do Not Match!'];
        if (/(duplicate|already exists|already taken|already registered)/.test(text)) return ['warning', 'Record Already Exists!'];
        if (/(required|complete all|missing field)/.test(text)) return ['warning', 'Please Complete All Required Fields!'];
        if (/(stock|restock|cannot distribute)/.test(title.toLowerCase())) return ['warning', title];
        if (type.includes('error') || /(failed|unable|error|incorrect|could not|cannot|unavailable|insufficient|not enough|not (?:saved|generated|available|found|allowed)|must be|please (?:choose|select|enter|check|complete))/.test(text)) {
            if (/password.*incorrect|incorrect password/.test(text)) return ['error', 'Incorrect Password!'];
            if (/login/.test(title.toLowerCase())) return ['error', 'Login Failed!'];
            if (/registration/.test(title.toLowerCase())) return ['error', 'Registration Failed!'];
            return ['error', /delet/.test(text) ? 'Deletion Failed!' : /updat/.test(text) ? 'Update Failed!' : /add|creat/.test(text) ? 'Failed to Add Record!' : 'Operation Failed!'];
        }
        if (type.includes('warning') || /invalid/.test(text)) return ['warning', 'Invalid Information!'];
        if (type.includes('success') || /(successfully|saved|generated)/.test(text)) {
            return ['success', /password/.test(text) ? 'Password Changed Successfully!' : /delet/.test(text) ? 'Successfully Deleted!' : /add|creat/.test(text) ? 'Successfully Added!' : /updat/.test(text) ? 'Successfully Updated!' : 'Changes Saved Successfully!'];
        }
        return [type, title || 'Notification'];
    }
    const visible = node => node instanceof Element && node.isConnected && node.getClientRects().length > 0;
    function contextFor(preferred) {
        if (typeof preferred === 'string') preferred = document.querySelector(preferred);
        if (visible(preferred)) return preferred;
        const focused = document.activeElement?.closest('form');
        if (visible(focused) && (focused.method.toLowerCase() === 'post' || focused.closest('.modal'))) return focused;
        const modal = document.querySelector('.modal.show .modal-body');
        if (visible(modal)) return [...modal.querySelectorAll('form')].find(visible) || modal;
        if (visible(lastForm) && (lastForm.method.toLowerCase() === 'post' || lastForm.closest('.modal'))) return lastForm;
        const forms = [...document.querySelectorAll('form')].filter(form => visible(form) && form.method.toLowerCase() === 'post');
        if (forms.length === 1) return forms[0];
        return document.querySelector('.app-content, main, .register-container, .reset-container') || document.body;
    }
    function clearField(field) {
        const node = fieldMessages.get(field);
        if (!node) return;
        const description = (field.getAttribute('aria-describedby') || '').split(' ').filter(id => id && id !== node.id).join(' ');
        if (description) field.setAttribute('aria-describedby',description);else field.removeAttribute('aria-describedby');
        field.removeAttribute('aria-invalid');field.classList.remove('is-invalid');
        delete field.dataset.spInvalid;node.remove();fieldMessages.delete(field);
    }
    function clearContext(context) {
        context.querySelectorAll('[data-sp-invalid]').forEach(clearField);
        context.querySelectorAll('[data-sp-inline-message]').forEach(node => node.remove());
    }
    function fieldError(field, message) {
        if (!visible(field) || field.type === 'hidden') return false;
        let node = fieldMessages.get(field);
        if (!node?.isConnected) {
            node = document.createElement('div');node.id = `sp-field-error-${++errorId}`;
            node.className = 'sp-field-error';node.dataset.spFieldError = '';node.setAttribute('role','alert');
            const wrapper = field.closest('.password-field, .settings-password-input, .form-check');
            (wrapper || field).after(node);fieldMessages.set(field,node);
        }
        node.textContent = safe(message);
        field.setAttribute('aria-invalid','true');field.classList.add('is-invalid');field.dataset.spInvalid='true';
        const descriptions = new Set((field.getAttribute('aria-describedby') || '').split(' ').filter(Boolean));
        descriptions.add(node.id);field.setAttribute('aria-describedby',[...descriptions].join(' '));
        return true;
    }
    function errorText(value) {
        if (Array.isArray(value)) return value.map(errorText).join(' ');
        if (value && typeof value === 'object') return value.message ? errorText(value.message) : Object.values(value).map(errorText).join(' ');
        return safe(value);
    }
    function inlineNotice(notice) {
        const context = contextFor(notice.target);
        const form = context.matches('form') ? context : context.closest('form') || [...context.querySelectorAll('form')].find(visible);
        if (notice.field && fieldError(notice.field,notice.message)) return Promise.resolve(false);
        const general = [];
        let hasFieldErrors = false;
        if (notice.errors && form) {
            for (const [name, errors] of Object.entries(notice.errors)) {
                let field = form.elements.namedItem(name);
                if (field && !(field instanceof Element)) field = field[0];
                const text = errorText(errors);
                if (!text) continue;
                if (field && fieldError(field,text)) hasFieldErrors = true;else general.push(text);
            }
            if (!general.length && hasFieldErrors) return Promise.resolve(false);
        }
        const message = general.length ? general.join('\n') : notice.message;
        // Django and module-specific forms may already render this exact error.
        const existing = [...context.querySelectorAll('.errorlist, .alert-danger, .alert-warning, .text-danger, .invalid-feedback')]
            .find(node => visible(node) && node.textContent.trim() === message);
        if (existing) return Promise.resolve(false);
        let node = [...context.children].find(child => child.hasAttribute('data-sp-inline-message'));
        if (!node) {node=document.createElement('div');node.dataset.spInlineMessage='';context.prepend(node);}
        node.className='sp-inline-message';node.dataset.type=notice.type;
        node.setAttribute('role',notice.type === 'info' ? 'status' : 'alert');
        node.replaceChildren();
        if (notice.title && !['Notification','Message','Invalid Information!','Please Complete All Required Fields!'].includes(notice.title)) {
            const title=document.createElement('strong');title.className='sp-inline-title';title.textContent=notice.title;node.append(title);
        }
        const text=document.createElement('span');text.textContent=message;node.append(text);
        return Promise.resolve(false);
    }
    function displayNext() {
        if (active || !queue.length) return;
        active = queue.shift();
        const target = active.confirm ? confirmation : dialog;
        target.dataset.type = active.type;
        target.querySelector('h2').textContent = active.title;
        target.querySelector('p').textContent = active.message;
        target.querySelector('.sp-popup-icon').textContent = {success:'\u2713',error:'\u00d7',warning:'!',question:'?',info:'i'}[active.type] || 'i';
        target.showModal();
        target.querySelector(active.confirm ? '.sp-popup-cancel' : '.sp-popup-ok').focus();
    }
    function enqueue(options) {
        const message = safe(options.message);
        const [type, title] = classify(message, options.type, options.title);
        const validationTitle = type === 'warning' && /required|match|already|invalid/i.test(title);
        const notice = {...options, message, type:options.confirm ? 'question' : type, title:validationTitle ? title : options.title || title};
        if (!notice.confirm && notice.type !== 'success') return inlineNotice(notice);
        const key = JSON.stringify([notice.type, notice.title, notice.message, notice.confirm]);
        const duplicate = [active, ...queue].find(entry => entry?.key === key);
        if (duplicate) return duplicate.promise;
        // An API observer and its caller may report the same outcome. Keep one.
        if (!notice.confirm && !notice.title.match(/stock/i) && lastNotice && Date.now()-lastNotice.time < 500 &&
            (lastNotice.type === notice.type || (['warning','error'].includes(lastNotice.type) && ['warning','error'].includes(notice.type)))) return lastNotice.promise;
        notice.key = key;
        notice.promise = new Promise(resolve => { notice.resolve = resolve; });
        if (!notice.confirm) lastNotice = {type:notice.type,time:Date.now(),promise:notice.promise};
        queue.push(notice); displayNext();
        return notice.promise;
    }
    async function finish(accepted) {
        if (!active || active.closing) return;
        const item = active; item.closing = true;
        const target = item.confirm ? confirmation : dialog;
        target.classList.add('sp-popup-closing');
        await new Promise(resolve => setTimeout(resolve, 120));
        target.close(); target.classList.remove('sp-popup-closing');
        // Preserve stock workflow lifecycle listeners while replacing Bootstrap dialogs.
        try {
            if (accepted && item.onConfirm) item.onConfirm();
            target.dispatchEvent(new Event('hidden.bs.modal'));
        } finally {
            item.resolve(accepted);
            if (lastNotice?.promise === item.promise) lastNotice = null;
            active = null; displayNext();
        }
    }
    dialog.querySelector('.sp-popup-ok').onclick = () => finish(true);
    dialog.querySelector('.sp-popup-close').onclick = () => finish(false);
    confirmation.querySelector('.sp-popup-cancel').onclick = () => finish(false);
    confirmation.querySelector('#appConfirmDialogConfirm').onclick = () => finish(true);
    [dialog, confirmation].forEach(node => node.addEventListener('cancel', event => { event.preventDefault(); finish(false); }));
    window.SmartPoultry = {
        notify: options => enqueue(options),
        confirm: (message, title = 'Confirm Action') => enqueue({confirm:true,message,title}),
    };
    window.showAppDialog = (message, title = '') => enqueue({message,title});
    window.showAppConfirmDialog = (message, onConfirm, title = 'Confirm Action') => enqueue({confirm:true,message,title,onConfirm});
    window.alert = message => window.showAppDialog(message);

    const nativeFetch = window.fetch.bind(window);
    const writes = new Map();
    window.fetch = async (input, options = {}) => {
        const url = new URL(input instanceof Request ? input.url : input, location.href);
        const method = String(options.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
        const api = url.origin === location.origin && url.pathname.startsWith('/api/');
        const write = api && !['GET','HEAD','OPTIONS'].includes(method);
        if (!api) return nativeFetch(input, options);
        const key = `${method}:${url.href}:${typeof options.body === 'string' ? options.body : ''}`;
        if (write && writes.has(key)) return (await writes.get(key)).clone();
        const button = write && document.activeElement?.matches('button') ? document.activeElement : null;
        const sourceContext = contextFor(button?.form || button?.closest('.modal')?.querySelector('.modal-body'));
        if (write) clearContext(sourceContext);
        const wasDisabled = button?.disabled;
        if (button) button.disabled = true;
        const task = (async () => {
            try {
                const response = await nativeFetch(input, options);
                const json = response.headers.get('content-type')?.includes('application/json');
                const result = json && response.status !== 204 ? await response.clone().json().catch(() => null) : null;
                if (!response.ok || response.redirected || (write && response.status !== 204 && (!json || result === null)) || (result && (result.success === false || result.error || ['error','failed'].includes(result.status)))) {
                    const validation = result && typeof result === 'object' ? Object.entries(result).map(([field,value]) => `${field.replaceAll('_',' ')}: ${Array.isArray(value) ? value.join(' ') : typeof value === 'object' ? 'Please check this information.' : value}`).join('\n') : '';
                    const message = response.status >= 500 || !json ? 'The server could not complete this request. Please try again.' : safe(validation || 'Please check your information and try again.');
                    enqueue({type:response.status === 400 ? 'warning' : 'error', title:response.status === 400 ? 'Invalid Information!' : method === 'DELETE' ? 'Deletion Failed!' : ['PATCH','PUT'].includes(method) ? 'Update Failed!' : 'Failed to Add Record!', message,
                        target:sourceContext,errors:response.status === 400 && result && typeof result === 'object' ? result : null});
                } else if (write && response.status === 202) {
                    enqueue({type:'info',title:'Request Received',message:'Your request is being processed. The result will appear when it is ready.'});
                } else if (write) {
                    const title = method === 'DELETE' ? 'Successfully Deleted!' : ['PATCH','PUT'].includes(method) ? 'Successfully Updated!' : 'Successfully Added!';
                    const notice = {type:'success', title, message:'Your operation was completed successfully.', owner:document.body.dataset.owner || '', time:Date.now()};
                    try { sessionStorage.setItem(pendingKey, JSON.stringify(notice)); } catch (_) {}
                    const savedForm = button?.form || button?.closest('.modal')?.querySelector('form');
                    if (savedForm) delete savedForm.dataset.spDirty;
                    setTimeout(() => {
                        try { sessionStorage.removeItem(pendingKey); } catch (_) {}
                        enqueue({...notice,target:sourceContext});
                    }, 100);
                }
                return response;
            } catch (error) {
                enqueue({type:'error',title:'Connection Error!',message:'Please check your connection and try again. The operation has not been confirmed.',target:sourceContext});
                throw error;
            }
        })();
        if (write) writes.set(key, task);
        try { return (await task).clone(); } finally {
            if (write) writes.delete(key);
            if (button && !wasDisabled) button.disabled = false;
        }
    };

    // Capture invalid fields once per validation pass, retaining entered values.
    document.addEventListener('invalid', event => {
        const field = event.target;
        if (field.closest('[data-inline-validation]')) return;
        event.preventDefault();
        enqueue({type:'warning',message:safe(field.validationMessage),field});
        if (visible(field) && !invalidFocusPending) {
            invalidFocusPending = true;
            requestAnimationFrame(() => {
                invalidFocusPending = false;
                if (!document.querySelector('dialog[open]')) field.focus();
            });
        }
    }, true);
    const submitted = new WeakSet();
    document.addEventListener('submit', event => {
        const form = event.target;
        lastForm = form;
        if (form.method.toLowerCase() !== 'post') return;
        if (submitted.has(form)) { event.preventDefault(); event.stopImmediatePropagation(); return; }
        const message = event.submitter?.dataset.confirm || form.dataset.confirm;
        if (message && form.dataset.confirmed !== 'true') {
            event.preventDefault(); event.stopImmediatePropagation();
            window.showAppConfirmDialog(message, () => {form.dataset.confirmed='true';form.requestSubmit(event.submitter || undefined);});
            return;
        }
        delete form.dataset.confirmed;
        // Native POST navigation: keep submitter values in the submitted payload.
        // Wait until all submit listeners have completed validation/AJAX handling.
        // A microtask can run between capture and target listeners.
        window.setTimeout(() => {
            if (event.defaultPrevented) return;
            submitted.add(form);
            form.querySelectorAll('[type=submit]').forEach(button => {button.setAttribute('aria-disabled','true');button.dataset.spSubmitting='true';});
        }, 0);
    }, true);
    window.addEventListener('pageshow', () => {
        document.querySelectorAll('form').forEach(form => submitted.delete(form));
        document.querySelectorAll('[data-sp-submitting]').forEach(button => {button.removeAttribute('aria-disabled');delete button.dataset.spSubmitting;});
    });
    document.addEventListener('input', event => {
        clearField(event.target);
        const form = event.target.closest('form');
        if (form) [...form.children].filter(node=>node.hasAttribute('data-sp-inline-message')).forEach(node=>node.remove());
        if (form && (form.method.toLowerCase() === 'post' || form.closest('.modal'))) form.dataset.spDirty = 'true';
    });
    document.addEventListener('reset', event => { delete event.target.dataset.spDirty;clearContext(event.target); });
    document.addEventListener('click',event=>{
        const form = event.target.closest('form') || event.target.closest('.modal')?.querySelector('form');
        if(form) lastForm=form;
    },true);
    document.addEventListener('click', event => {
        const close = event.target.closest('[data-bs-dismiss=modal]');
        const modal = close?.closest('.modal') || (event.target.classList.contains('modal') ? event.target : null);
        if (!modal?.querySelector('form[data-sp-dirty]')) return;
        event.preventDefault(); event.stopImmediatePropagation();
        window.SmartPoultry.confirm('Discard unsaved changes?').then(confirmed => {
            if (confirmed) { modal.querySelectorAll('form').forEach(form => delete form.dataset.spDirty);bootstrap.Modal.getInstance(modal)?.hide(); }
        });
    }, true);
    document.addEventListener('keydown', event => {
        const modal = event.target.closest('.modal.show');
        if (event.key !== 'Escape' || !modal?.querySelector('form[data-sp-dirty]') || active) return;
        event.preventDefault(); event.stopImmediatePropagation();
        window.SmartPoultry.confirm('Discard unsaved changes?').then(confirmed => {
            if (confirmed) {modal.querySelectorAll('form').forEach(form => delete form.dataset.spDirty);bootstrap.Modal.getInstance(modal)?.hide();}
        });
    }, true);
    document.addEventListener('hide.bs.modal', event => {
        const modal = event.target;
        if (!modal.querySelector('form[data-sp-dirty]') || modal.dataset.spDiscard === 'true') { delete modal.dataset.spDiscard; return; }
        // Programmatic successful saves must be able to close their editing window.
        if (!modal.contains(document.activeElement) || !document.activeElement.matches('[data-bs-dismiss=modal]')) return;
        event.preventDefault();
        window.SmartPoultry.confirm('Discard unsaved changes?').then(confirmed => {
            if (confirmed) { modal.dataset.spDiscard='true';modal.querySelectorAll('form').forEach(form => delete form.dataset.spDirty);bootstrap.Modal.getInstance(modal).hide(); }
        });
    });
    document.addEventListener('click', event => {
        const link = event.target.closest('a[href]');
        if (!link || event.defaultPrevented || event.ctrlKey || event.metaKey || event.shiftKey || link.target === '_blank' || !/cancel|\bback\b|already have/i.test(link.textContent)) return;
        if (!document.querySelector('form[data-sp-dirty]')) return;
        event.preventDefault();
        window.SmartPoultry.confirm('Discard unsaved changes?').then(confirmed => {if(confirmed) location.href=link.href;});
    });
    function initialize() {
        try {
            const notice = JSON.parse(sessionStorage.getItem(pendingKey));
            sessionStorage.removeItem(pendingKey);
            if (notice && Date.now()-notice.time < 60000 && notice.owner === (document.body.dataset.owner || '')) enqueue(notice);
        } catch (_) {}
        document.querySelectorAll('[data-popup-message]').forEach(node => enqueue({type:node.dataset.level,message:node.textContent,title:node.dataset.title}));
        // Django field errors already render inline; do not duplicate them.
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize); else initialize();
})();
