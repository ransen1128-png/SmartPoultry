/* Keep the operation key across uncertain network outcomes, including reloads. */
window.safeTransactionFetch=async function(url,options={}) {
    const raw=String(options.body || '');
    const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(url+'\n'+raw));
    const fingerprint=Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('');
    const slot='smartpoultry-pending:'+document.body.dataset.owner+':'+fingerprint;
    window.pendingFinancialKeys ||= new Map();
    let key=window.pendingFinancialKeys.get(slot);
    try{key ||= localStorage.getItem(slot);}catch(error){}
    key ||= crypto.randomUUID();
    window.pendingFinancialKeys.set(slot,key);
    try{localStorage.setItem(slot,key);}catch(error){}
    const headers=new Headers(options.headers);headers.set('Idempotency-Key',key);
    const response=await fetch(url,{...options,headers});
    if(response.status<500){
        await response.clone().json();
        window.pendingFinancialKeys.delete(slot);
        try{localStorage.removeItem(slot);}catch(error){}
    }
    return response;
};
