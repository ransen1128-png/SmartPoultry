let branchStockLots=new Map(),branchUsageRecords=new Map(),branchUsageOperation=null;
function branchStockCell(row,text){row.insertCell().textContent=text;}
async function loadBranchStock(){
    try{
        const response=await fetch('/api/inventory/distributions/branch-stock/');
        if(!response.ok)throw new Error('Unable to load branch stock.');
        const lots=await response.json(),body=document.getElementById('branchStockBody');
        body.replaceChildren();branchStockLots.clear();
        for(const lot of lots){
            branchStockLots.set(lot.id,lot);const row=body.insertRow();
            [lot.branch_name,lot.item_name+' / #'+lot.id+' / '+lot.date,
                formatQuantity(lot.received,lot.unit,lot.package_size,lot.content_unit),
                formatQuantity(lot.used,lot.unit,lot.package_size,lot.content_unit),
                formatQuantity(lot.remaining,lot.unit,lot.package_size,lot.content_unit)].forEach(value=>branchStockCell(row,value));
            const cell=row.insertCell();
            if(lot.active && Number(lot.remaining)>0){const button=document.createElement('button');button.type='button';button.className='btn btn-sm btn-outline-primary';button.textContent='Record use';button.onclick=()=>openBranchUsage(lot.id);cell.append(button);}
        }
        if(!lots.length){const cell=body.insertRow().insertCell();cell.colSpan=6;cell.textContent='No stock has been distributed to branches.';}
        const usages=await pagedInventoryRecords('/api/inventory/usage/'),history=document.getElementById('branchUsageBody');history.replaceChildren();branchUsageRecords.clear();
        for(const usage of usages){
            branchUsageRecords.set(usage.id,usage);const row=history.insertRow();
            [usage.branch_name,usage.item_name,usage.date,formatQuantity(usage.quantity,usage.unit),usage.reason,usage.voided_at?'Reversed: '+usage.void_reason:'Used'].forEach(value=>branchStockCell(row,value));
            const cell=row.insertCell();if(!usage.voided_at){const button=document.createElement('button');button.type='button';button.className='btn btn-sm btn-outline-danger';button.textContent='Reverse usage';button.onclick=()=>openBranchUsage(usage.id,true);cell.append(button);}
        }
        if(!usages.length){const cell=history.insertRow().insertCell();cell.colSpan=7;cell.textContent='No branch usage recorded yet.';}
        document.getElementById('branchStockError').textContent='';
    }catch(error){document.getElementById('branchStockError').textContent=error.message;}
}
function openBranchUsage(id,reverse=false){
    const record=reverse?branchUsageRecords.get(id):branchStockLots.get(id);branchUsageOperation={id,reverse};
    document.getElementById('branchUsageTitle').textContent=reverse?'Reverse branch usage':'Record branch use';
    document.getElementById('branchUsageLabel').textContent=record.branch_name+' - '+record.item_name+(reverse?'':' - '+formatQuantity(record.remaining,record.unit)+' available');
    const form=document.getElementById('branchUsageForm');form.reset();
    document.getElementById('branchUsageQuantityFields').hidden=reverse;
    for(const field of ['branchUsageQuantity','branchUsageDate'])document.getElementById(field).required=!reverse;
    if(!reverse){document.getElementById('branchUsageQuantity').max=record.remaining;document.getElementById('branchUsageDate').min=record.date;document.getElementById('branchUsageDate').value=document.getElementById('branchUsageDate').max;}
    document.getElementById('branchUsageError').textContent='';bootstrap.Modal.getOrCreateInstance(document.getElementById('branchUsageModal')).show();
}
document.addEventListener('DOMContentLoaded',()=>{
    const modal=document.getElementById('branchUsageModal');let saving=false;
    modal.addEventListener('hide.bs.modal',event=>{if(saving)event.preventDefault();});
    document.getElementById('branchUsageForm').addEventListener('submit',event=>{event.preventDefault();document.getElementById('branchUsageSave').click();});
    document.getElementById('branchUsageSave').addEventListener('click',async function(){
        if(saving || !document.getElementById('branchUsageForm').reportValidity())return;
        saving=true;this.disabled=true;
        try{
            const {id,reverse}=branchUsageOperation;
            const data={reason:document.getElementById('branchUsageReason').value};
            if(!reverse)Object.assign(data,{distribution:id,quantity:document.getElementById('branchUsageQuantity').value,date:document.getElementById('branchUsageDate').value});
            const response=await safeTransactionFetch('/api/inventory/usage/'+(reverse?id+'/reverse/':''),{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')},body:JSON.stringify(data)});
            const result=await response.json();if(!response.ok)throw new Error(JSON.stringify(result));
            saving=false;bootstrap.Modal.getInstance(modal).hide();await loadBranchStock();
        }catch(error){document.getElementById('branchUsageError').textContent=error.message;}
        finally{saving=false;this.disabled=false;}
    });
});
