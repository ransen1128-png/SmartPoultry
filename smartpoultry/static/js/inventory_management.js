/* Branch/flock inventory tracking. Server checks all ownership and stock rules. */
async function pagedInventoryRecords(url) {
    const rows=[];
    while(url) {const response=await fetch(url);if(!response.ok)throw new Error('Unable to load records.');const data=await response.json();rows.push(...(data.results || []));url=data.next;}
    return rows;
}
const inventoryMassUnits=[['kg','Kilograms (kg)'],['g','Grams (g)'],['lb','Pounds (lb)'],['oz','Ounces (oz)']];
const inventoryLiquidUnits=[['ml','Milliliters (mL)'],['L','Liters (L)']];
const inventoryPackageChoices=[['sacks','Sacks'],['bags','Bags'],['bottles','Bottles (liquid)'],['jugs','Jugs (liquid)'],['cans','Cans (liquid)'],['boxes','Boxes'],['containers','Containers'],['pcs','Pieces'],['kg','Kilograms (bulk)'],['g','Grams (bulk)'],['lb','Pounds (bulk)'],['ml','Milliliters (bulk)'],['L','Liters (bulk)']];
function setInventorySelect(select,choices,value,placeholder) {
    select.replaceChildren(new Option(placeholder,''));
    choices.forEach(([value,label])=>select.add(new Option(label,value)));
    // Preserve existing labels when editing older inventory; no quantity conversion.
    if(value && !choices.some(([option])=>option===value))select.add(new Option(value+' (existing)',value));
    select.value=value || '';
}
function updateInventoryContentUnits(stock,size,content,existingValue) {
    const unit=stock.value.toLowerCase();
    const liquid=['bottles','bottle','jugs','jug','cans','can'].includes(unit);
    const dry=['sacks','sack','bags','bag'].includes(unit);
    const choices=liquid?inventoryLiquidUnits:dry?inventoryMassUnits:[...inventoryMassUnits,...inventoryLiquidUnits];
    const selected=existingValue!==undefined?existingValue:
        size.value?(choices.some(([value])=>value===content.value)?content.value:choices[0][0]):'';
    setInventorySelect(content,choices,selected,'Choose content unit (optional)');
}
document.addEventListener('DOMContentLoaded',()=>{
    for(const [stockId,sizeId,contentId] of [['newStockUnit','newPackageSize','newContentUnit'],['packagingStockUnit','packagingSize','packagingContentUnit']]){
        const stock=document.getElementById(stockId),size=document.getElementById(sizeId),content=document.getElementById(contentId);
        setInventorySelect(stock,inventoryPackageChoices,'','Choose package type...');
        updateInventoryContentUnits(stock,size,content);
        stock.addEventListener('change',()=>updateInventoryContentUnits(stock,size,content));
        size.addEventListener('input',()=>updateInventoryContentUnits(stock,size,content));
    }
    document.getElementById('addInventoryForm').addEventListener('reset',()=>{
        setTimeout(()=>updateInventoryContentUnits(document.getElementById('newStockUnit'),document.getElementById('newPackageSize'),document.getElementById('newContentUnit'),''),0);
    });
});
let packagingReturnToHistory=false;
function showLowStockDialog(message,dialog,title='Low stock - restock needed') {
    if(!message)return;
    SmartPoultry.notify({type:'warning',title,message,
        target:dialog?.classList.contains('show') ? dialog.querySelector('.modal-body') : null});
}
function inventoryRestockMessage(item) {
    return item.name+': '+formatQuantity(item.quantity,item.unit,item.package_size,item.content_unit)+
        ' remaining; minimum '+item.minimum_stock+' '+item.unit+'. Stock is low. Please restock this item.';
}
function editPackaging(id) {
    const item=inventoryItems.get(Number(id));
    document.getElementById('packagingItemId').value=id;
    document.getElementById('packagingItemName').textContent=item.name+' — '+Number(item.quantity)+' stock units recorded';
    setInventorySelect(document.getElementById('packagingStockUnit'),inventoryPackageChoices,item.unit,'Choose package type...');
    document.getElementById('packagingSize').value=item.package_size ?? '';
    updateInventoryContentUnits(document.getElementById('packagingStockUnit'),document.getElementById('packagingSize'),document.getElementById('packagingContentUnit'),item.content_unit || '');
    document.getElementById('packagingError').textContent='';
    const history=document.getElementById('distributionModal');
    packagingReturnToHistory=history.classList.contains('show');
    const show=()=>bootstrap.Modal.getOrCreateInstance(document.getElementById('packagingModal')).show();
    if(packagingReturnToHistory){history.addEventListener('hidden.bs.modal',show,{once:true});bootstrap.Modal.getInstance(history).hide();}else show();
}
async function savePackaging() {
    if(!document.getElementById('packagingForm').reportValidity())return;
    const button=document.getElementById('savePackagingBtn');button.disabled=true;
    try {
        const response=await fetch('/api/inventory/items/'+document.getElementById('packagingItemId').value+'/',{method:'PATCH',headers:{'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')},body:JSON.stringify({unit:document.getElementById('packagingStockUnit').value,package_size:document.getElementById('packagingSize').value || null,content_unit:document.getElementById('packagingContentUnit').value.trim()})});
        const data=await response.json();
        if(!response.ok)throw new Error(Object.entries(data).map(([key,value])=>key+': '+value).join('; '));
        await loadInventory();bootstrap.Modal.getInstance(document.getElementById('packagingModal')).hide();
    }catch(error){document.getElementById('packagingError').textContent=error.message;}finally{button.disabled=false;}
}
document.addEventListener('DOMContentLoaded',()=>document.getElementById('packagingModal').addEventListener('hidden.bs.modal',()=>{
    if(packagingReturnToHistory){packagingReturnToHistory=false;showDistributionModal(null,false);}
}));
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
        const item=await response.json();
        const dialog=document.getElementById('minimumStockModal');
        if(item.is_low_stock)showLowStockDialog(inventoryRestockMessage(item),dialog);
        else bootstrap.Modal.getInstance(dialog).hide();
        await loadInventory();
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
    const history=document.getElementById('depletedInventoryBody');history.replaceChildren();
    for(const item of records) {
        inventoryItems.set(Number(item.id),item);
        if(Number(item.quantity)<=0) {
            const row=history.insertRow();
            [item.name,item.item_type,item.date_added,item.last_updated,formatQuantity(item.quantity,item.unit,item.package_size,item.content_unit),'₱'+Number(item.cost_per_unit).toFixed(2)].forEach(value=>row.insertCell().textContent=value);
            const actions=row.insertCell(),button=document.createElement('button');button.type='button';button.className='btn btn-sm btn-outline-primary';button.textContent='Distributions';button.addEventListener('click',()=>showDistributionModal(item.id,false));actions.append(button);
            const packaging=document.createElement('button');packaging.type='button';packaging.className='btn btn-sm btn-outline-secondary ms-1';packaging.textContent='Packaging';packaging.addEventListener('click',()=>editPackaging(item.id));actions.append(packaging);
            continue;
        }
        const row=body.insertRow();
        [item.item_type,item.name,item.date_added,formatQuantity(item.quantity,item.unit,item.package_size,item.content_unit),'₱'+Number(item.cost_per_unit).toFixed(2),'₱'+Number(item.total_value).toFixed(2),item.minimum_stock==null?'Disabled':item.minimum_stock+' '+item.unit+(item.is_low_stock?' — LOW STOCK':'')].forEach(value=>{row.insertCell().textContent=value;});
        if(item.is_low_stock)row.className='table-warning';
        const actions=row.insertCell();actions.className='text-end';
        [['Distribute',()=>openDistribution(item.id)],['Packaging',()=>editPackaging(item.id)],['Minimum stock',()=>setMinimum(item.id)],['Delete',()=>deleteItem(item.id)]].forEach(([label,action])=>{const button=document.createElement('button');button.type='button';button.className='btn btn-sm btn-outline-primary me-1 mb-1';button.textContent=label;button.addEventListener('click',action);actions.append(button);});
    }
    if(!body.rows.length){const cell=body.insertRow().insertCell();cell.colSpan=8;cell.textContent='No items in stock. Depleted items are available in History.';}
    if(!history.rows.length){const cell=history.insertRow().insertCell();cell.colSpan=7;cell.textContent='No depleted inventory items.';}
    if(typeof loadBranchStock==='function')await loadBranchStock();
}
async function loadDistributionHistory(inventoryId=null) {
    const body=document.getElementById('distributionHistoryBody');body.replaceChildren();
    try {
        const rows=await pagedInventoryRecords('/api/inventory/distributions/'+(inventoryId?'?inventory='+inventoryId:''));
        if(!rows.length){const cell=body.insertRow().insertCell();cell.colSpan=8;cell.textContent='No distributions recorded.';}
        for(const row of rows) {
            const tr=body.insertRow();
            [row.item_name,row.date,row.branch_name,row.flock_name || 'Branch stock',formatQuantity(row.quantity,row.unit,row.package_size_snapshot,row.content_unit_snapshot),row.cost_per_unit==null?'Needs review':'₱'+Number(row.cost_per_unit).toFixed(2),row.cost_snapshot==null?'Needs review':'₱'+Number(row.cost_snapshot).toFixed(2)].forEach(value=>tr.insertCell().textContent=value);
            const actions=tr.insertCell();
            if(row.reversed_at){tr.className='text-muted';actions.textContent='Reversed — '+row.reversal_reason;}
            else {const button=document.createElement('button');button.type='button';button.className='btn btn-sm btn-outline-danger';button.textContent='Reverse';button.addEventListener('click',()=>requestReversal(row));actions.append(button);}
        }
    } catch(error){const cell=body.insertRow().insertCell();cell.colSpan=8;cell.textContent=error.message;}
}
