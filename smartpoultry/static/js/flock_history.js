async function loadFlocks() {
    try {
        const records=[];let url='/api/flocks/';
        while(url) {const response=await fetch(url);if(!response.ok)throw new Error('Unable to load flocks.');const data=await response.json();records.push(...(data.results || []));url=data.next;}
        records.sort((a,b)=>(a.branch_name || 'Unassigned').localeCompare(b.branch_name || 'Unassigned') || b.date_added.localeCompare(a.date_added));
        const current=document.getElementById('flocksBody'),history=document.getElementById('flockHistoryBody');
        current.replaceChildren();history.replaceChildren();
        for(const flock of records) {
            const body=flock.in_history?history:current,tr=body.insertRow();
            [flock.branch_name || 'Unassigned',flock.flock_id,flock.breed,flock.quantity,flock.in_history?flock.history_reason:flock.status,flock.acquisition_source_display,flock.acquisition_source==='unknown'?'Not recorded':'₱'+Number(flock.purchase_total).toFixed(2),flock.date_added].forEach(value=>tr.insertCell().textContent=value);
            const actions=tr.insertCell();const edit=document.createElement('button');edit.type='button';edit.className='btn btn-sm btn-info me-1';edit.textContent=flock.in_history?'View / Edit':'Edit';edit.addEventListener('click',()=>editFlock(flock.id));actions.append(edit);
            if(!flock.in_history){const remove=document.createElement('button');remove.type='button';remove.className='btn btn-sm btn-danger';remove.textContent='Delete';remove.addEventListener('click',()=>confirmDeleteFlock(flock.id,flock.flock_id));actions.append(remove);}
        }
        for(const [body,message] of [[current,'No current flocks.'],[history,'No completed flocks yet.']])if(!body.rows.length){const cell=body.insertRow().insertCell();cell.colSpan=9;cell.textContent=message;}
        document.getElementById('flockHistoryBtn').textContent='History ('+records.filter(row=>row.in_history).length+')';
    } catch(error){showMessageDialog(error.message,'Flocks');}
}
document.addEventListener('DOMContentLoaded',()=>document.getElementById('flockHistoryBtn').addEventListener('click',()=>{
    const panel=document.getElementById('flockHistoryPanel');panel.hidden=!panel.hidden;
    document.getElementById('flockHistoryBtn').setAttribute('aria-expanded',String(!panel.hidden));
    if(!panel.hidden)panel.scrollIntoView({behavior:'smooth',block:'nearest'});
}));
