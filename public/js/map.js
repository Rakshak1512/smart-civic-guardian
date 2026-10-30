// Renders complaint markers on the authority Map dashboard using Leaflet.js
// Expects window.COMPLAINTS_DATA to be populated by the template.

document.addEventListener('DOMContentLoaded', function () {
    const mapEl = document.getElementById('complaintsMap');
    if (!mapEl) return;

    const complaints = window.COMPLAINTS_DATA || [];
    const defaultCenter = complaints.length ? [complaints[0].latitude, complaints[0].longitude] : [12.9716, 77.5946];

    const map = L.map('complaintsMap').setView(defaultCenter, 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    const priorityColors = { High: '#e05252', Medium: '#e2a233', Low: '#2fa876' };

    complaints.forEach(function (c) {
        const color = priorityColors[c.priority] || '#1e6f5c';
        const marker = L.circleMarker([c.latitude, c.longitude], {
            radius: 9,
            fillColor: color,
            color: '#fff',
            weight: 2,
            fillOpacity: 0.9
        }).addTo(map);

        marker.bindPopup(
            '<strong>' + c.category + '</strong><br>' +
            'Priority: ' + c.priority + '<br>' +
            'Status: ' + c.status + '<br>' +
            (c.location_name || '') +
            '<br><a href="/admin/complaints/' + c.id + '">View details</a>'
        );
    });

    if (complaints.length === 0) {
        mapEl.insertAdjacentHTML('beforebegin', '<p class="hint-text">No complaints with location data yet.</p>');
    }
});
