let branchReportRequest = 0;
let branchReportController;
async function loadBranchAnalysis() {
    const form = document.getElementById('branchReportFilters');
    const error = document.getElementById('branchReportError');
    error.textContent = '';
    if (!form.reportValidity()) return;
    branchReportController?.abort();
    branchReportController = new AbortController();
    const request = ++branchReportRequest;
    form.removeAttribute('aria-busy');
    const params = new URLSearchParams(new FormData(form));
    const csv = document.getElementById('branchExpensesCsv');
    csv.removeAttribute('href'); csv.setAttribute('aria-disabled', 'true');
    const clearTables = () => ['branchExpensesBody', 'feedUsageBody'].forEach(id => document.getElementById(id).replaceChildren());
    const fail = message => {
        error.textContent = message;
        document.getElementById('branchExpenseTotal').textContent = '\u2014';
        document.getElementById('reportFeedTotal').textContent = '\u2014';
        clearTables();
    };
    if (params.get('end') < params.get('start')) {
        fail('End date must be on or after start date.');
        return;
    }
    form.setAttribute('aria-busy', 'true');
    try {
        const responses = await Promise.all(['/api/reports/branch-expenses/', '/api/reports/feed-usage/'].map(url => fetch(url + '?' + params, {signal: branchReportController.signal, spHandleErrors: false})));
        if (responses.some(response => !response.ok)) throw new Error('Unable to load report. Check the dates and selected branch.');
        const [expenses, feed] = await Promise.all(responses.map(response => response.json()));
        if (request !== branchReportRequest) return;
        error.textContent = '';
        document.getElementById('branchExpenseTotal').textContent = '\u20b1' + Number(expenses.total).toFixed(2);
        csv.href = '/api/reports/branch-expenses/?' + params + '&export=csv';
        csv.setAttribute('aria-disabled', 'false');
        clearTables();
        const expenseBody = document.getElementById('branchExpensesBody');
        for (const row of expenses.summary) {
            const tr = expenseBody.insertRow();
            [row.branch_name, row.expense_type.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' '), '\u20b1' + Number(row.amount).toFixed(2), row.records].forEach(value => tr.insertCell().textContent = value);
        }
        const totals = new Map();
        const feedBody = document.getElementById('feedUsageBody');
        for (const row of feed.results) {
            for (const [unit, quantity] of Object.entries(row.quantities)) totals.set(unit, (totals.get(unit) || 0) + Number(quantity));
            const tr = feedBody.insertRow();
            [row.branch, row.flock, Object.entries(row.quantities).map(([unit, quantity]) => quantity + ' ' + unit).join('; '), '\u20b1' + Number(row.cost).toFixed(2) + (row.missing_cost_records ? ' (some costs need review)' : ''), row.eggs_produced ?? 'Individual egg count unavailable', row.distributed_feed_cost_per_egg == null ? 'Not available' : '\u20b1' + Number(row.distributed_feed_cost_per_egg).toFixed(4)].forEach(value => tr.insertCell().textContent = value);
        }
        document.getElementById('reportFeedTotal').textContent = totals.size ? [...totals].map(([unit, quantity]) => quantity.toLocaleString(undefined, {maximumFractionDigits: 3}) + ' ' + unit).join(' \u00b7 ') : '0.00 kg';
        for (const [body, columns, message] of [[expenseBody, 4, 'No expenses in this range.'], [feedBody, 6, 'No feed distributions in this range.']]) {
            if (!body.rows.length) { const cell = body.insertRow().insertCell(); cell.colSpan = columns; cell.textContent = message; }
        }
    } catch (failure) {
        if (failure.name !== 'AbortError' && request === branchReportRequest) fail('Unable to load report. Check the dates, selected branch and your connection.');
    } finally {
        if (request === branchReportRequest) form.removeAttribute('aria-busy');
    }
}
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('branchReportFilters');
    form.addEventListener('submit', event => { event.preventDefault(); loadBranchAnalysis(); });
    form.addEventListener('input', () => { document.getElementById('branchReportError').textContent = ''; });
    document.querySelectorAll('.report-tabs [data-bs-toggle="tab"]').forEach(tab => tab.addEventListener('shown.bs.tab', () => {
        const expenses = tab.id === 'expenseReportTab';
        document.getElementById('expenseReportTable').hidden = !expenses;
        document.getElementById('feedReportTable').hidden = expenses;
        document.getElementById('branchExpensesCsv').hidden = !expenses;
    }));
    loadBranchAnalysis();
});
