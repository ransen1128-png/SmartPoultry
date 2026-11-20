// SMARTPOULTRY Main JavaScript

// CSRF Token Helper
function getCsrfToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, 'csrftoken'.length + 1) === 'csrftoken=') {
                cookieValue = decodeURIComponent(cookie.substring('csrftoken'.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// API Request Helper
async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        }
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API Request Error:', error);
        showError('An error occurred. Please try again.');
        throw error;
    }
}

// All modules use the shared notification component.
function showError(message) { return window.SmartPoultry.notify({type:'error', message}); }
function showSuccess(message) { return window.SmartPoultry.notify({type:'success', message}); }

// Format Currency
function formatCurrency(value) {
    return new Intl.NumberFormat('en-PH', {
        style: 'currency',
        currency: 'PHP'
    }).format(value);
}

// Format Date
function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('en-PH', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function parseScenarioPercent(value) {
    const numericValue = parseFloat(String(value).replace('%', '').replace('+', '').trim());
    return Number.isFinite(numericValue) ? numericValue / 100 : 0;
}

function parseScenarioMoney(value) {
    const numericValue = parseFloat(String(value || '0').replace(/,/g, ''));
    return Number.isFinite(numericValue) ? numericValue : 0;
}

function updateScenarioPanel(panel) {
    const scenarioType = panel.querySelector('[data-scenario-type]');
    const scenarioChange = panel.querySelector('[data-scenario-change]');
    const percent = parseScenarioPercent(scenarioChange ? scenarioChange.value : 0);

    let revenue = parseScenarioMoney(panel.dataset.baseRevenue);
    let expenses = parseScenarioMoney(panel.dataset.baseExpenses);
    const feedCost = parseScenarioMoney(panel.dataset.baseFeedCost);
    const feedBaseline = feedCost > 0 ? feedCost : expenses;

    switch (scenarioType ? scenarioType.value : '') {
        case 'feed_price_increase':
            expenses += feedBaseline * percent;
            break;
        case 'lower_mortality':
            revenue += revenue * percent * 0.5;
            expenses -= expenses * percent * 0.1;
            break;
        case 'mortality_increase':
            revenue -= revenue * percent * 0.35;
            expenses += expenses * percent * 0.12;
            break;
        case 'egg_price_increase':
            revenue += revenue * percent;
            break;
        default:
            break;
    }

    const profit = revenue - expenses;
    const values = { profit, revenue, expenses };

    panel.querySelectorAll('[data-result]').forEach(result => {
        const key = result.dataset.result;
        result.textContent = formatCurrency(values[key] || 0);
        if (key === 'profit') {
            result.classList.toggle('text-success', profit >= 0);
            result.classList.toggle('text-danger', profit < 0);
        }
    });

    panel.querySelectorAll('[data-scenario-label]').forEach(label => {
        label.textContent = label.textContent.replace('Current', 'Expected');
    });
}

function initScenarioPanels() {
    document.querySelectorAll('.scenario-panel').forEach(panel => {
        const applyButton = panel.querySelector('[data-apply-scenario]');
        if (!applyButton) {
            return;
        }

        applyButton.addEventListener('click', () => updateScenarioPanel(panel));
    });
}

// Initialize tooltips (Bootstrap)
document.addEventListener('DOMContentLoaded', function() {
    // Initialize all tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

document.addEventListener('DOMContentLoaded', initScenarioPanels);

// Only temporary notices may be removed. Forms reuse their alert containers.
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert[data-auto-dismiss]');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.classList.remove('show');
            alert.remove();
        }, 5000);
    });
});

// Export to CSV
function exportTableToCSV(filename) {
    const csv = [];
    const tables = document.querySelectorAll('table');
    
    tables.forEach(table => {
        const rows = table.querySelectorAll('tr');
        rows.forEach(row => {
            const cols = row.querySelectorAll('td, th');
            const csvRow = [];
            cols.forEach(col => {
                csvRow.push(col.innerText);
            });
            csv.push(csvRow.join(','));
        });
    });

    downloadCSV(csv.join('\n'), filename);
}

function downloadCSV(csv, filename) {
    const csvFile = new Blob([csv], { type: 'text/csv' });
    const downloadLink = document.createElement('a');
    downloadLink.href = URL.createObjectURL(csvFile);
    downloadLink.download = filename;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    downloadLink.remove();
}

// Debounce function for search
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize Chart.js defaults
Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto'";
Chart.defaults.color = '#666';
