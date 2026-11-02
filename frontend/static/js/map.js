// Renders complaint markers on the authority Map dashboard using Leaflet.js
// Expects window.COMPLAINTS_DATA to be populated by the template.

document.addEventListener('DOMContentLoaded', function () {
    const mapEl = document.getElementById('complaintsMap');
    if (!mapEl || typeof L === 'undefined') return;

    // Only plot reports with real, valid GPS coordinates. Never invent a pin
    // for reports that contain only a manually entered place description.
    const complaints = (window.COMPLAINTS_DATA || []).filter(function (c) {
        const lat = Number(c.latitude);
        const lon = Number(c.longitude);
        return c.latitude !== null && c.latitude !== undefined &&
            c.longitude !== null && c.longitude !== undefined &&
            Number.isFinite(lat) && Number.isFinite(lon) &&
            lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
    });

    const defaultCenter = complaints.length
        ? [Number(complaints[0].latitude), Number(complaints[0].longitude)]
        : [12.9716, 77.5946];

    const map = L.map('complaintsMap').setView(defaultCenter, 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    const priorityColors = { High: '#e05252', Medium: '#e2a233', Low: '#2fa876' };

    complaints.forEach(function (c) {
        const lat = Number(c.latitude);
        const lon = Number(c.longitude);
        const color = priorityColors[c.priority] || '#1e6f5c';
        const marker = L.circleMarker([lat, lon], {
            radius: 9,
            fillColor: color,
            color: '#fff',
            weight: 2,
            fillOpacity: 0.9
        }).addTo(map);

        const mapsUrl = 'https://www.google.com/maps/search/?api=1&query=' +
            encodeURIComponent(lat + ',' + lon);
        const popup = document.createElement('div');
        const heading = document.createElement('strong');
        heading.textContent = c.category || 'Civic issue';
        const details = document.createElement('div');
        details.textContent = 'Priority: ' + (c.priority || 'N/A') +
            ' · Status: ' + (c.status || 'N/A');
        const place = document.createElement('div');
        place.textContent = c.location_name || 'GPS location';
        const mapsLink = document.createElement('a');
        mapsLink.href = mapsUrl;
        mapsLink.target = '_blank';
        mapsLink.rel = 'noopener noreferrer';
        mapsLink.textContent = 'Open in Google Maps ↗';
        const detailLink = document.createElement('a');
        detailLink.href = '/admin/complaints/' + encodeURIComponent(c.id);
        detailLink.textContent = 'View details';
        popup.append(heading, details, place, mapsLink, document.createElement('br'), detailLink);
        marker.bindPopup(popup);
    });

    if (complaints.length === 0) {
        mapEl.insertAdjacentHTML('beforebegin',
            '<p class="hint-text">No complaints with GPS coordinates yet. Reports with manually entered locations remain available in Manage Complaints.</p>');
    }
});
