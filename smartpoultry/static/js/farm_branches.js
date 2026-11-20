/* AJAX is progressive enhancement: the same owner-scoped forms support normal POSTs. */
(() => {
    const list = document.getElementById('branchList');
    const search = document.getElementById('branchSearchForm');
    if (!list || !search) return;
    const pending = new WeakSet();
    let searchController;
    let revision = 0;
    function updateList(data) {
        list.innerHTML = data.html;
        list.inert = false;
        if (data.query !== undefined) search.elements.q.value = data.query;
    }
    function clearErrors(form) {
        form.querySelectorAll('[data-branch-error]').forEach(node => node.remove());
        form.querySelectorAll('[aria-invalid]').forEach(node => {node.removeAttribute('aria-invalid');node.classList.remove('is-invalid');});
    }
    function fieldErrors(form, errors) {
        for (const [name, details] of Object.entries(errors || {})) {
            const field = form.elements.namedItem(name);
            if (!field) continue;
            field.setAttribute('aria-invalid', 'true');field.classList.add('is-invalid');
            const text = document.createElement('div');text.dataset.branchError='';text.className='invalid-feedback';
            text.textContent=details.map(error => error.message).join(' ');field.after(text);
        }
    }
    async function closeSavedForm(form) {
        delete form.dataset.spDirty;
        const modal = form.closest('.modal');
        if (!modal || !modal.classList.contains('show')) return;
        await new Promise(resolve => {
            modal.addEventListener('hidden.bs.modal', resolve, {once:true});
            bootstrap.Modal.getInstance(modal).hide();
        });
        if (modal.id !== 'addBranchModal') bootstrap.Modal.getInstance(modal)?.dispose();
    }
    document.addEventListener('submit', async event => {
        const form = event.target.closest('[data-branch-form]');
        if (!form) return;
        event.preventDefault();
        if (pending.has(form) || !form.reportValidity()) return;
        pending.add(form);clearErrors(form);
        const buttons = [...form.querySelectorAll('[type=submit]')];buttons.forEach(button => button.disabled=true);
        const data = new FormData(form);data.set('q', search.elements.q.value);
        try {
            const response = await fetch(form.getAttribute('action'), {method:'POST',body:data,
                headers:{'Accept':'application/json','X-CSRFToken':form.elements.csrfmiddlewaretoken.value}});
            if (response.redirected || !response.headers.get('content-type')?.includes('application/json') || response.status >= 500) throw new Error('unconfirmed');
            const result = await response.json();
            if (!response.ok) {
                fieldErrors(form,result.errors);
                const errors = Object.values(result.errors || {}).flat();
                SmartPoultry.notify({type:'warning',message:errors.map(error=>error.message).join('\n') || result.error || 'Unable to save this branch.'});
                return;
            }
            revision++;searchController?.abort();
            await closeSavedForm(form);
            updateList(result);
            if (form.id === 'addBranchForm') form.reset();
            const url = new URL(location.href);
            if (result.query) url.searchParams.set('q',result.query);else url.searchParams.delete('q');
            history.replaceState(null,'',url);
            SmartPoultry.notify({type:'success',title:result.message,message:'Your farm branch list has been updated.'});
        } catch (_) {
            SmartPoultry.notify({type:'error',title:'Connection Error!',message:'The result could not be confirmed. Check your branch list before retrying.'});
        } finally {pending.delete(form);buttons.forEach(button=>button.disabled=false);}
    });
    search.addEventListener('submit',async event => {
        event.preventDefault();
        const current = ++revision;
        list.inert = true;
        searchController?.abort();searchController=new AbortController();
        const url = new URL(location.href);url.searchParams.set('q',search.elements.q.value);
        try {
            const response=await fetch(url,{headers:{'Accept':'application/json'},signal:searchController.signal});
            if (!response.ok || response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error();
            const result=await response.json();
            if (revision === current) {updateList(result);history.replaceState(null,'',url);}
        } catch (error) {
            if(error.name!=='AbortError') SmartPoultry.notify({type:'error',title:'Connection Error!',message:'Unable to search branches. Please try again.'});
        } finally { if (revision === current) list.inert = false; }
    });
    const initiallyOpen=document.getElementById('openBranchModal');
    if(initiallyOpen) bootstrap.Modal.getOrCreateInstance(document.getElementById(initiallyOpen.dataset.modalId)).show();
})();
