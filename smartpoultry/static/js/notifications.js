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
    const pendingKey = 'smartpoultry-popup';
    const safe = value => {
        const text = String(value || '').trim();
        return /traceback|<!doctype|<html|exception at|sqlstate|postgresql:\/\/|secret_key|api[_ -]?key\s*[:=]/i.test(text)
            ? 'The request could not be completed. Please try again.' : text.slice(0, 700);
    };
    function classify(message, type = 'info', title = '') {
        const text = `${title} ${message}`.toLowerCase();
        if (/login-success/.test(type)) return ['success', 'Login Successful!'];
        if (/account-created/.test(type)) return ['success', 'Registration Successful!'];
        if (/password.*(match|mismatch)/.test(text)) return ['warning', 'Passwords Do Not Match!'];
        if (/(duplicate|already exists|already taken|already registered)/.test(text)) return ['warning', 'Record Already Exists!'];
        if (/(required|complete all|missing field)/.test(text)) return ['warning', 'Please Complete All Required Fields!'];
        if (/(stock|restock|cannot distribute)/.test(title.toLowerCase())) return ['warning', title];
        if (type.includes('error') || /(failed|unable|error|incorrect|could not)/.test(text)) {
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
        } finally { item.resolve(accepted); active = null; displayNext(); }
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
                    enqueue({type:response.status === 400 ? 'warning' : 'error', title:response.status === 400 ? 'Invalid Information!' : method === 'DELETE' ? 'Deletion Failed!' : ['PATCH','PUT'].includes(method) ? 'Update Failed!' : 'Failed to Add Record!', message});
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
                        enqueue(notice);
                    }, 100);
                }
                return response;
            } catch (error) {
                enqueue({type:'error',title:'Connection Error!',message:'Please check your connection and try again. The operation has not been confirmed.'});
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
        enqueue({type:'warning',title:field.validity.valueMissing ? 'Please Complete All Required Fields!' : /match/i.test(field.validationMessage) ? 'Passwords Do Not Match!' : 'Invalid Information!',message:safe(field.validationMessage)});
    }, true);
    const submitted = new WeakSet();
    document.addEventListener('submit', event => {
        const form = event.target;
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
        queueMicrotask(() => {
            if (event.defaultPrevented) return;
            submitted.add(form);
            form.querySelectorAll('[type=submit]').forEach(button => {button.setAttribute('aria-disabled','true');button.dataset.spSubmitting='true';});
        });
    }, true);
    window.addEventListener('pageshow', () => {
        document.querySelectorAll('form').forEach(form => submitted.delete(form));
        document.querySelectorAll('[data-sp-submitting]').forEach(button => {button.removeAttribute('aria-disabled');delete button.dataset.spSubmitting;});
    });
    document.addEventListener('input', event => {
        const form = event.target.closest('form');
        if (form && (form.method.toLowerCase() === 'post' || form.closest('.modal'))) form.dataset.spDirty = 'true';
    });
    document.addEventListener('reset', event => { delete event.target.dataset.spDirty; });
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
        const errors = [...document.querySelectorAll('.errorlist, form .text-danger')].map(node => node.textContent.trim()).filter(Boolean);
        if (errors.length) enqueue({type:'warning',message:errors.join('\n')});
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize); else initialize();
})();
