(() => {
    const getCookie = name => document.cookie.split(';').map(value => value.trim()).find(value => value.startsWith(name + '='))?.slice(name.length + 1) || '';
    const error = document.getElementById('generatedReportError');
    const periods = [...document.querySelectorAll('[data-report-period]')];
    const localDate = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    const displayDate = value => new Date(value.length === 10 ? value + 'T00:00:00' : value).toLocaleDateString();
    async function loadReports() {
        const reports = [];
        let url = '/api/reports/';
        while (url) {
            const response = await fetch(url, {spHandleErrors: false});
            if (!response.ok) throw new Error('Unable to load generated reports. Please try again.');
            const data = await response.json();
            reports.push(...(data.results || []));
            url = data.next;
        }
        const body = document.getElementById('reportsBody');
        body.replaceChildren();
        for (const report of reports) {
            const row = body.insertRow();
            [report.report_type.charAt(0).toUpperCase() + report.report_type.slice(1), report.title,
                `${displayDate(report.start_date)} – ${displayDate(report.end_date)}`, displayDate(report.generated_at)]
                .forEach(value => row.insertCell().textContent = value);
            const link = document.createElement('a');
            link.className = 'btn btn-outline-primary btn-sm';
            link.href = `/api/reports/${encodeURIComponent(report.id)}/download/`;
            link.textContent = 'Download';
            row.insertCell().append(link);
        }
        if (!reports.length) {
            const cell = body.insertRow().insertCell();
            cell.colSpan = 5; cell.textContent = 'No generated reports yet. Choose a period above to create one.';
        }
    }
    async function generateReport(type) {
        if (periods.some(button => button.disabled)) return;
        error.textContent = '';
        periods.forEach(button => button.disabled = true);
        const today = new Date();
        let start = new Date(today);
        if (type === 'weekly') start.setDate(start.getDate() - 6);
        if (type === 'monthly') start = new Date(today.getFullYear(), today.getMonth(), 1);
        if (type === 'annual') start = new Date(today.getFullYear(), 0, 1);
        try {
            const response = await fetch('/api/reports/', {
                method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')},
                body: JSON.stringify({report_type: type, title: `${type.charAt(0).toUpperCase() + type.slice(1)} Report - ${today.toLocaleDateString()}`,
                    start_date: localDate(start), end_date: localDate(today), summary: 'Auto-generated report'}),
            });
            if (!response.ok) throw new Error('Unable to generate report. Please try again.');
            await response.json();
            try { await loadReports(); }
            catch (_) { error.textContent = 'Your report was created, but the list could not refresh. Reload this page to view it.'; }
        } catch (_) {
            error.textContent = 'Unable to confirm report creation. Refresh the report list before trying again.';
        } finally {
            periods.forEach(button => button.disabled = false);
        }
    }
    periods.forEach(button => button.addEventListener('click', () => generateReport(button.dataset.reportPeriod)));
    document.addEventListener('DOMContentLoaded', () => loadReports().catch(() => {
        error.textContent = 'Unable to load generated reports. Please refresh and try again.';
    }));
})();
