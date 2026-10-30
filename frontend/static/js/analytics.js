// Fetches /api/analytics/summary and renders Chart.js charts on the
// authority Analytics page.

document.addEventListener('DOMContentLoaded', function () {
    const fetchSummary = (window.api && window.api.getAnalyticsSummary)
        ? window.api.getAnalyticsSummary()
        : fetch(`${window.API_BASE_URL || ''}/api/analytics/summary`, { credentials: 'include' }).then(r => r.json());

    fetchSummary
        .then(renderAnalytics)
        .catch(function (err) {
            console.error(err);
            const el = document.getElementById('analyticsSummary');
            if (el) el.insertAdjacentHTML('afterend', '<p class="hint-text">Could not load analytics data. Please refresh the page.</p>');
        });
});

function renderAnalytics(data) {
    document.getElementById('statTotal').textContent = data.stats.total;
    document.getElementById('statResolved').textContent = data.stats.resolved;
    document.getElementById('statHigh').textContent = data.stats.high_priority;
    document.getElementById('statRating').textContent = data.rating.average ? (data.rating.average + ' / 5') : 'N/A';

    const palette = ['#1e6f5c', '#f2994a', '#e05252', '#2fa876', '#e2a233', '#4a90d9'];

    new Chart(document.getElementById('categoryChart'), {
        type: 'bar',
        data: {
            labels: Object.keys(data.by_category),
            datasets: [{ label: 'Complaints', data: Object.values(data.by_category), backgroundColor: palette }]
        },
        options: { responsive: true, plugins: { legend: { display: false } } }
    });

    new Chart(document.getElementById('statusChart'), {
        type: 'doughnut',
        data: {
            labels: Object.keys(data.by_status),
            datasets: [{ data: Object.values(data.by_status), backgroundColor: ['#e05252', '#e2a233', '#2fa876'] }]
        },
        options: { responsive: true }
    });

    new Chart(document.getElementById('priorityChart'), {
        type: 'pie',
        data: {
            labels: Object.keys(data.by_priority),
            datasets: [{ data: Object.values(data.by_priority), backgroundColor: ['#2fa876', '#e2a233', '#e05252'] }]
        },
        options: { responsive: true }
    });

    new Chart(document.getElementById('trendChart'), {
        type: 'line',
        data: {
            labels: data.trend.map(function (t) { return t.day; }),
            datasets: [{
                label: 'Complaints per day',
                data: data.trend.map(function (t) { return t.count; }),
                borderColor: '#1e6f5c',
                backgroundColor: 'rgba(30,111,92,0.15)',
                fill: true,
                tension: 0.3
            }]
        },
        options: { responsive: true, plugins: { legend: { display: false } } }
    });

    const hotspotList = document.getElementById('hotspotList');
    hotspotList.innerHTML = '';
    if (data.hotspots.length === 0) {
        hotspotList.innerHTML = '<li>No location data available yet.</li>';
    } else {
        data.hotspots.forEach(function (h) {
            const li = document.createElement('li');
            li.innerHTML = '<span>' + h.location + '</span><strong>' + h.count + ' reports</strong>';
            hotspotList.appendChild(li);
        });
    }
}
