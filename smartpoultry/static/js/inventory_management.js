/* Branch/flock inventory tracking. Server checks all ownership and stock rules. */
let flockOptions=[];
async function pagedInventoryRecords(url) {
    const rows=[];
    while(url) {const response=await fetch(url);if(!response.ok)throw new Error('Unable to load records.');const data=await response.json();rows.push(...(data.results || []));url=data.next;}
    return rows;
}
function updateReceivingFlocks() {
    const select=document.getElementById('distributionFlock');
    select.replaceChildren(new Option('Branch stock — no flock assigned',''));
    flockOptions.filter(row=>String(row.branch)===document.getElementById('distributionBranch').value && row.status==='active').forEach(row=>select.add(new Option(row.flock_id,row.id)));
}
async function setMinimum(id) {
    const item=inventoryItems.get(Number(id));
    document.getElementById('minimumItemName').textContent=item.name+' ('+item.unit+')';
    document.getElementById('minimumValue').value=item.minimum_stock ?? '';
    document.getElementById('minimumItemId').value=id;
    bootstrap.Modal.getOrCreateInstance(document.getElementById('minimumStockModal')).show();
}
async function saveMinimum() {
    if(!document.getElementById('minimumStockForm').reportValidity())return;
    const value=document.getElementById('minimumValue').value;
    const button=document.getElementById('saveMinimumBtn');button.disabled=true;
    try {
        const response=await fetch('/api/inventory/items/'+document.getElementById('minimumItemId').value+'/',{method:'PATCH',headers:{'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')},body:JSON.stringify({minimum_stock:value===''?null:value})});
        if(!response.ok)throw new Error('Unable to update minimum stock.');
        bootstrap.Modal.getInstance(document.getElementById('minimumStockModal')).hide();await loadInventory();
    } catch(error) {showAppDialog(error.message,'Inventory');}finally {button.disabled=false;}
}
function requestReversal(distribution) {
    document.getElementById('reverseDistributionId').value=distribution.id;
    document.getElementById('reverseDistributionLabel').textContent=distribution.item_name+' — '+distribution.quantity+' '+distribution.unit+' to '+distribution.branch_name;
    document.getElementById('reverseReason').value='';
    const history=document.getElementById('distributionModal');
    history.addEventListener('hidden.bs.modal',()=>bootstrap.Modal.getOrCreateInstance(document.getElementById('reverseDistributionModal')).show(),{once:true});
    bootstrap.Modal.getInstance(history).hide();
}
async function confirmReversal() {
    if(!document.getElementById('reverseDistributionForm').reportValidity())return;
    const button=document.getElementById('confirmReverseBtn');button.disabled=true;
    try {
        const response=await fetch('/api/inventory/distributions/'+document.getElementById('reverseDistributionId').value+'/reverse/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')},body:JSON.stringify({reason:document.getElementById('reverseReason').value})});
        if(!response.ok)throw new Error('Unable to reverse this distribution.');
        const dialog=document.getElementById('reverseDistributionModal');
        dialog.addEventListener('hidden.bs.modal',()=>showDistributionModal(null,false),{once:true});
        bootstrap.Modal.getInstance(dialog).hide();await loadInventory();
    } catch(error) {showAppDialog(error.message,'Distribution');} finally {button.disabled=false;}
}
async function loadInventory() {
    const records=await pagedInventoryRecords('/api/inventory/items/');
    const body=document.getElementById('inventoryBody');body.replaceChildren();inventoryItems.clear();
    for(const item of records) {
        inventoryItems.set(Number(item.id),item);
        const row=body.insertRow();
        [item.item_type,item.name,item.date_added,formatQuantity(item.quantity,item.unit),'₱'+Number(item.cost_per_unit).toFixed(2),'₱'+Number(item.total_value).toFixed(2),item.minimum_stock==null?'Disabled':item.minimum_stock+' '+item.unit+(item.is_low_stock?' — LOW STOCK':'')].forEach(value=>{row.insertCell().textContent=value;});
        if(item.is_low_stock)row.className='table-warning';
        const actions=row.insertCell();actions.className='text-end';
        [['Distribute',()=>openDistribution(item.id)],['Minimum stock',()=>setMinimum(item.id)],['Delete',()=>deleteItem(item.id)]].forEach(([label,action])=>{const button=document.createElement('button');button.type='button';button.className='btn btn-sm btn-outline-primary me-1 mb-1';button.textContent=label;button.addEventListener('click',action);actions.append(button);});
    }
}
async function loadDistributionHistory(inventoryId=null) {
    const body=document.getElementById('distributionHistoryBody');body.replaceChildren();
    try {
        const rows=await pagedInventoryRecords('/api/inventory/distributions/'+(inventoryId?'?inventory='+inventoryId:''));
        if(!rows.length){const cell=body.insertRow().insertCell();cell.colSpan=8;cell.textContent='No distributions recorded.';}
        for(const row of rows) {
            const tr=body.insertRow();
            [row.item_name,row.date,row.branch_name,row.flock_name || 'Branch stock',formatQuantity(row.quantity,row.unit),row.cost_per_unit==null?'Needs review':'₱'+Number(row.cost_per_unit).toFixed(2),row.cost_snapshot==null?'Needs review':'₱'+Number(row.cost_snapshot).toFixed(2)].forEach(value=>tr.insertCell().textContent=value);
            const actions=tr.insertCell();
            if(row.reversed_at){tr.className='text-muted';actions.textContent='Reversed — '+row.reversal_reason;}
            else {const button=document.createElement('button');button.type='button';button.className='btn btn-sm btn-outline-danger';button.textContent='Reverse';button.addEventListener('click',()=>requestReversal(row));actions.append(button);}
        }
    } catch(error){const cell=body.insertRow().insertCell();cell.colSpan=8;cell.textContent=error.message;}
}
document.addEventListener('DOMContentLoaded',async()=>{
    document.getElementById('distributionBranch').addEventListener('change',updateReceivingFlocks);
    document.getElementById('distributionModal').addEventListener('show.bs.modal',updateReceivingFlocks);
    try {flockOptions=await pagedInventoryRecords('/api/flocks/');updateReceivingFlocks();}catch(error){showAppDialog(error.message,'Flocks');}
});
