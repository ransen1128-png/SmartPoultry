async function loadBranchAnalysis() {
    const form=document.getElementById('branchReportFilters');if(!form.reportValidity())return;
    const params=new URLSearchParams(new FormData(form));
    document.getElementById('branchReportError').textContent='';
    try {
        const responses=await Promise.all(['/api/reports/branch-expenses/','/api/reports/feed-usage/'].map(url=>fetch(url+'?'+params)));
        if(responses.some(response=>!response.ok))throw new Error('Unable to load report. Check the dates and selected branch.');
        const [expenses,feed]=await Promise.all(responses.map(response=>response.json()));
        document.getElementById('branchExpenseTotal').textContent='₱'+Number(expenses.total).toFixed(2);
        document.getElementById('branchExpensesCsv').href='/api/reports/branch-expenses/?'+params+'&export=csv';
        const expenseBody=document.getElementById('branchExpensesBody');expenseBody.replaceChildren();
        for(const row of expenses.summary) {const tr=expenseBody.insertRow();[row.branch_name,row.expense_type,'₱'+Number(row.amount).toFixed(2),row.records].forEach(value=>tr.insertCell().textContent=value);}
        const feedBody=document.getElementById('feedUsageBody');feedBody.replaceChildren();
        for(const row of feed.results) {
            const tr=feedBody.insertRow();
            [row.branch,row.flock,Object.entries(row.quantities).map(([unit,quantity])=>quantity+' '+unit).join('; '),'₱'+Number(row.cost).toFixed(2)+(row.missing_cost_records?' (some costs need review)':''),row.eggs_produced ?? 'Individual egg count unavailable',row.distributed_feed_cost_per_egg==null?'Not available':'₱'+Number(row.distributed_feed_cost_per_egg).toFixed(4)].forEach(value=>tr.insertCell().textContent=value);
        }
        for(const [body,columns,message] of [[expenseBody,4,'No expenses in this range.'],[feedBody,6,'No feed distributions in this range.']])if(!body.rows.length){const cell=body.insertRow().insertCell();cell.colSpan=columns;cell.textContent=message;}
    }catch(error){document.getElementById('branchReportError').textContent=error.message;document.getElementById('branchExpenseTotal').textContent='—';document.getElementById('branchExpensesCsv').removeAttribute('href');}
}
document.addEventListener('DOMContentLoaded',()=>{
    document.getElementById('branchReportFilters').addEventListener('submit',event=>{event.preventDefault();loadBranchAnalysis();});
    loadBranchAnalysis();
});
