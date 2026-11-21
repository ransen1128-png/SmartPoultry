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
            const actions=tr.insertCell();actions.className='flock-actions-cell';
            const group=document.createElement('div');group.className='flock-actions';group.setAttribute('role','group');group.setAttribute('aria-label','Actions for flock '+flock.flock_id);actions.append(group);
            const edit=document.createElement('button');edit.type='button';edit.className='btn btn-sm flock-action-edit';
            const editIcon=document.createElement('i');editIcon.className='bi bi-pencil-square';editIcon.setAttribute('aria-hidden','true');
            edit.append(editIcon,document.createTextNode(flock.in_history?'View / Edit':'Edit'));edit.addEventListener('click',()=>openFlockHistoryEditor(flock.id));group.append(edit);
            tr.insertCell(actions.cellIndex).textContent=flock.days_since_placement==null?'Not recorded':flock.days_since_placement+' days';
            tr.insertCell(actions.cellIndex).textContent=flock.ready_from?flock.ready_from+' to '+flock.readiness_window_end:'—';
            if(!flock.in_history){
                const remove=document.createElement('button');remove.type='button';remove.className='btn btn-sm flock-action-delete';
                const deleteIcon=document.createElement('i');deleteIcon.className='bi bi-trash';deleteIcon.setAttribute('aria-hidden','true');
                remove.append(deleteIcon,document.createTextNode('Delete'));remove.addEventListener('click',()=>confirmDeleteFlock(flock.id,flock.flock_id));group.append(remove);
            }
        }
        for(const [body,message] of [[current,'No current flocks.'],[history,'No completed flocks yet.']])if(!body.rows.length){const cell=body.insertRow().insertCell();cell.colSpan=11;cell.textContent=message;}
        document.getElementById('flockHistoryBtn').textContent='History ('+records.filter(row=>row.in_history).length+')';
    } catch(error){showMessageDialog(error.message,'Flocks');}
}
// Finish closing history before opening its editor; Bootstrap supports one modal at a time.
function openFlockHistoryEditor(id) {
    const history = document.getElementById('flockHistoryPanel');
    if (!history.classList.contains('show')) { editFlock(id); return; }
    history.addEventListener('hidden.bs.modal', () => editFlock(id), {once: true});
    bootstrap.Modal.getOrCreateInstance(history).hide();
}
