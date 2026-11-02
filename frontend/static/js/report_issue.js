/**
 * Smart Civic Guardian - Report Issue Geolocation & Interactive Map
 *
 * Implements high-accuracy multi-sample device location detection using
 * navigator.geolocation.watchPosition(), accurate uncertainty reporting in metres,
 * separate error diagnostics (denied, unavailable, timeout), interactive Leaflet
 * map-pin correction, reverse-geocoded address resolution, and bottom-displayed
 * location confirmation.
 */

document.addEventListener('DOMContentLoaded', function () {
    const gpsStatus = document.getElementById('gpsStatus');
    const manualBox = document.getElementById('manualLocationBox');
    const latInput = document.getElementById('latitude');
    const lonInput = document.getElementById('longitude');
    const locNameInput = document.getElementById('location_name');
    const manualInput = document.getElementById('manual_location');
    const retryBtn = document.getElementById('retryGpsBtn');
    const gpsHint = document.getElementById('gpsHint');
    const mapEl = document.getElementById('issueLocationMap');

    const devLatInput = document.getElementById('device_latitude');
    const devLonInput = document.getElementById('device_longitude');
    const accInput = document.getElementById('location_accuracy');
    const srcInput = document.getElementById('location_source');

    // Bottom detected location display elements
    const detectedLocationCard = document.getElementById('detectedLocationCard');
    const detectedAccuracyBadge = document.getElementById('detectedAccuracyBadge');
    const detectedSourceBadge = document.getElementById('detectedSourceBadge');
    const detectedAddressText = document.getElementById('detectedAddressText');
    const detectedLatText = document.getElementById('detectedLatText');
    const detectedLonText = document.getElementById('detectedLonText');

    let leafletMap = null;
    let mapMarker = null;
    let accuracyCircle = null;

    let activeWatchId = null;
    let masterTimer = null;
    let bestPosition = null;
    let readingCount = 0;
    let isSampling = false;

    let currentResolvedAddress = '';

    // High accuracy thresholds (in metres)
    const PRECISE_ACCURACY_THRESHOLD = 25; // <= 25 m triggers early stop (dedicated GPS)
    const MASTER_TIMEOUT_MS = 12000;       // Up to 12s to sample and refine position

    // Default center for manual map pin placement if device GPS is completely disabled
    const DEFAULT_MAP_CENTER = [12.9716, 77.5946];

    // ---------------------------------------------------------------------------
    // Reverse Geocoding & Bottom Location Display
    // ---------------------------------------------------------------------------
    function updateBottomDetectedDisplay(lat, lon, accuracyMeters, sourceLabel, isAdjusted) {
        if (!detectedLocationCard) return;

        detectedLocationCard.style.display = 'block';

        if (detectedLatText) detectedLatText.textContent = lat.toFixed(6);
        if (detectedLonText) detectedLonText.textContent = lon.toFixed(6);

        if (detectedSourceBadge) {
            detectedSourceBadge.textContent = sourceLabel || 'Device Fix';
        }

        if (detectedAccuracyBadge) {
            if (accuracyMeters && accuracyMeters > 0) {
                const roundedAcc = Math.round(accuracyMeters);
                if (roundedAcc <= 30) {
                    detectedAccuracyBadge.textContent = '±' + roundedAcc + ' m (High Precision GPS)';
                    detectedAccuracyBadge.style.background = '#dcfce7';
                    detectedAccuracyBadge.style.color = '#166534';
                } else if (roundedAcc <= 80) {
                    detectedAccuracyBadge.textContent = '±' + roundedAcc + ' m (Moderate)';
                    detectedAccuracyBadge.style.background = '#fef3c7';
                    detectedAccuracyBadge.style.color = '#92400e';
                } else {
                    detectedAccuracyBadge.textContent = '±' + roundedAcc + ' m (Approximate)';
                    detectedAccuracyBadge.style.background = '#ffedd5';
                    detectedAccuracyBadge.style.color = '#9a3412';
                }
            } else {
                detectedAccuracyBadge.textContent = 'Map Pin';
                detectedAccuracyBadge.style.background = '#E6F4F1';
                detectedAccuracyBadge.style.color = '#0d6868';
            }
        }

        // Initial fallback address while reverse geocode resolves
        currentResolvedAddress = 'Coordinates: ' + lat.toFixed(5) + ', ' + lon.toFixed(5);
        renderFullAddressLine();

        // Query Nominatim reverse geocode for actual place / road name
        fetch('https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=' + lat + '&lon=' + lon, {
            headers: { 'Accept': 'application/json' }
        })
        .then(function (res) {
            if (!res.ok) throw new Error('Geocoding response not ok');
            return res.json();
        })
        .then(function (data) {
            if (data && data.display_name) {
                const addr = data.address || {};
                const parts = [];
                const primary = addr.road || addr.pedestrian || addr.suburb || addr.quarter;
                if (primary) parts.push(primary);
                const secondary = addr.neighbourhood || addr.city_district || addr.suburb;
                if (secondary && !parts.includes(secondary)) parts.push(secondary);
                const city = addr.city || addr.town || addr.municipality;
                if (city && !parts.includes(city)) parts.push(city);

                currentResolvedAddress = parts.length > 0 ? parts.join(', ') : data.display_name.split(',').slice(0, 3).join(',');
                renderFullAddressLine();
            }
        })
        .catch(function () {
            // Keep coordinates as fallback on network error
            renderFullAddressLine();
        });
    }

    function renderFullAddressLine() {
        if (!detectedAddressText) return;

        const manualText = manualInput && manualInput.value.trim();
        const baseAddr = currentResolvedAddress || 'Detected Location';

        if (manualText) {
            detectedAddressText.innerHTML = '<strong>' + escapeHtml(baseAddr) + '</strong>' +
                '<span style="font-weight:normal;color:var(--text-muted);"> — Landmark: ' + escapeHtml(manualText) + '</span>';
        } else {
            detectedAddressText.textContent = baseAddr;
        }

        // Sync with location_name hidden input
        if (locNameInput && latInput && latInput.value) {
            const acc = accInput && accInput.value ? ' (±' + Math.round(Number(accInput.value)) + ' m)' : '';
            const landmarkPart = manualText ? ' — Landmark: ' + manualText : '';
            locNameInput.value = (baseAddr + acc + landmarkPart).substring(0, 250);
        }
    }

    function escapeHtml(str) {
        return String(str).replace(/[&<>"']/g, function (m) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
        });
    }

    if (manualInput) {
        manualInput.addEventListener('input', function () {
            renderFullAddressLine();
        });
    }

    // ---------------------------------------------------------------------------
    // Leaflet Mini Map Initialization & Updates
    // ---------------------------------------------------------------------------
    function initOrUpdateMap(lat, lon, accuracyMeters, isFallbackMode) {
        if (!mapEl || typeof window.L === 'undefined') return;

        mapEl.style.display = 'block';

        const centerLat = (typeof lat === 'number' && isFinite(lat)) ? lat : DEFAULT_MAP_CENTER[0];
        const centerLon = (typeof lon === 'number' && isFinite(lon)) ? lon : DEFAULT_MAP_CENTER[1];
        const zoomLevel = isFallbackMode ? 12 : 16;

        if (!leafletMap) {
            leafletMap = L.map('issueLocationMap', {
                scrollWheelZoom: false,
                touchZoom: true
            }).setView([centerLat, centerLon], zoomLevel);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors',
                maxZoom: 19
            }).addTo(leafletMap);

            // Clicking anywhere on the map moves or places the pin
            leafletMap.on('click', function (e) {
                applyManualMapPin(e.latlng.lat, e.latlng.lng);
            });
        } else {
            leafletMap.setView([centerLat, centerLon], zoomLevel);
        }

        // Clean up previous marker/circle
        if (accuracyCircle) {
            leafletMap.removeLayer(accuracyCircle);
            accuracyCircle = null;
        }

        if (typeof lat === 'number' && typeof lon === 'number' && isFinite(lat) && isFinite(lon)) {
            if (!mapMarker) {
                mapMarker = L.marker([lat, lon], { draggable: true }).addTo(leafletMap);
                mapMarker.on('dragend', function () {
                    const pos = mapMarker.getLatLng();
                    applyManualMapPin(pos.lat, pos.lng);
                });
            } else {
                mapMarker.setLatLng([lat, lon]);
            }

            // Draw accuracy radius circle if valid positive accuracy
            if (accuracyMeters && accuracyMeters > 0 && !isFallbackMode) {
                accuracyCircle = L.circle([lat, lon], {
                    radius: accuracyMeters,
                    color: '#2563eb',
                    fillColor: '#3b82f6',
                    fillOpacity: 0.14,
                    weight: 1.5,
                    dashArray: accuracyMeters > 50 ? '4, 4' : null
                }).addTo(leafletMap);
            }
        }

        setTimeout(function () {
            if (leafletMap) leafletMap.invalidateSize();
        }, 150);
    }

    function applyManualMapPin(newLat, newLon) {
        if (!leafletMap) return;

        const roundedLat = Number(newLat.toFixed(6));
        const roundedLon = Number(newLon.toFixed(6));

        if (latInput) latInput.value = roundedLat;
        if (lonInput) lonInput.value = roundedLon;

        const origAcc = accInput && accInput.value ? Math.round(Number(accInput.value)) : null;

        if (srcInput) srcInput.value = 'map_pin_manual';

        if (mapMarker) {
            mapMarker.setLatLng([roundedLat, roundedLon]);
        } else {
            mapMarker = L.marker([roundedLat, roundedLon], { draggable: true }).addTo(leafletMap);
            mapMarker.on('dragend', function () {
                const pos = mapMarker.getLatLng();
                applyManualMapPin(pos.lat, pos.lng);
            });
        }

        if (accuracyCircle) {
            accuracyCircle.setStyle({ color: '#6b7280', fillColor: '#9ca3af', fillOpacity: 0.1 });
        }

        if (gpsStatus) {
            gpsStatus.innerHTML = '📌 <strong>Pin placed on map:</strong> ' + roundedLat + ', ' + roundedLon +
                (origAcc ? ' <span style="color:var(--text-muted);">(Adjusted from original ±' + origAcc + ' m fix)</span>' : '');
        }

        if (manualBox) manualBox.style.display = 'block';

        // Update the bottom detected location card
        updateBottomDetectedDisplay(roundedLat, roundedLon, origAcc, 'Map Pin Adjusted', true);
    }

    // ---------------------------------------------------------------------------
    // Geolocation Detection with Multi-Reading Watcher
    // ---------------------------------------------------------------------------
    if (gpsStatus) {
        function showManualFallback(message, isError) {
            stopLocationSampling();
            gpsStatus.innerHTML = message;
            if (gpsHint) gpsHint.textContent = '';
            if (manualBox) manualBox.style.display = 'block';
            if (retryBtn) {
                retryBtn.disabled = false;
                retryBtn.textContent = 'Retry Location';
            }
            if (detectedLocationCard) detectedLocationCard.style.display = 'none';
            initOrUpdateMap(null, null, null, true);
        }

        function stopLocationSampling() {
            if (activeWatchId !== null && navigator.geolocation) {
                try { navigator.geolocation.clearWatch(activeWatchId); } catch (e) {}
                activeWatchId = null;
            }
            if (masterTimer !== null) {
                clearTimeout(masterTimer);
                masterTimer = null;
            }
            isSampling = false;
        }

        function finalizeBestReading() {
            stopLocationSampling();

            if (retryBtn) {
                retryBtn.disabled = false;
                retryBtn.textContent = 'Retry Location';
            }

            if (!bestPosition || !bestPosition.coords) {
                handleLocationError({
                    code: 3,
                    message: 'Location request timed out before receiving a valid fix.'
                });
                return;
            }

            const coords = bestPosition.coords;
            const lat = Number(coords.latitude.toFixed(6));
            const lon = Number(coords.longitude.toFixed(6));
            const accuracy = Math.round(Number(coords.accuracy));

            if (latInput) latInput.value = lat;
            if (lonInput) lonInput.value = lon;
            if (devLatInput) devLatInput.value = lat;
            if (devLonInput) devLonInput.value = lon;
            if (accInput) accInput.value = accuracy;

            let sourceTag = 'device_approximate';
            let locDescriptor = '';
            let statusHtml = '';

            if (accuracy <= 30) {
                sourceTag = 'device_gps_precise';
                locDescriptor = 'Device GPS (±' + accuracy + ' m) [Precise]';
                statusHtml = '✅ <strong>Precise device GPS fix captured:</strong> Accuracy ±' + accuracy + ' m.';
                if (gpsHint) gpsHint.textContent = 'High-accuracy satellite fix acquired.';
            } else if (accuracy <= 80) {
                sourceTag = 'device_moderate';
                locDescriptor = 'Device Location (±' + accuracy + ' m) [Good]';
                statusHtml = '📍 <strong>Device location captured:</strong> Accuracy ±' + accuracy + ' m. Drag the pin if needed.';
                if (gpsHint) gpsHint.textContent = 'You can drag the blue pin on the map to fine-tune.';
            } else {
                sourceTag = 'device_approximate';
                locDescriptor = 'Device Location (±' + accuracy + ' m) [Approximate]';
                statusHtml = '⚠ <strong>Location captured, but accuracy is about ' + accuracy + ' m.</strong><br>' +
                    '<span style="font-size:0.85rem;color:var(--text-muted);">' +
                    'Laptops on Wi-Fi without GPS hardware typically report ~100–150 m accuracy. ' +
                    'You can drag the pin on the map or enter a landmark below to pinpoint the exact spot.</span>';
                if (gpsHint) gpsHint.textContent = 'Drag the pin on the map or add a landmark.';
            }

            if (srcInput) srcInput.value = sourceTag;
            if (locNameInput) locNameInput.value = locDescriptor;
            gpsStatus.innerHTML = statusHtml;

            // Render interactive Leaflet map with accuracy circle
            initOrUpdateMap(lat, lon, accuracy, false);

            // Display detected location clearly on the bottom
            updateBottomDetectedDisplay(lat, lon, accuracy, accuracy <= 30 ? 'High Precision GPS' : 'Device Fix (Wi-Fi/Network)', false);

            if (manualBox) {
                manualBox.style.display = 'block';
                const manualLabel = manualBox.querySelector('label');
                if (manualLabel) {
                    manualLabel.textContent = accuracy <= 30
                        ? 'Optional: add a nearby landmark or street address'
                        : 'Recommended: add a nearby landmark or street name to refine location';
                }
            }
        }

        function handleLocationError(error) {
            stopLocationSampling();

            if (bestPosition) {
                // If we got at least one reading prior to the error, keep it!
                finalizeBestReading();
                return;
            }

            let title = '';
            let details = '';

            switch (error && error.code) {
                case 1: // PERMISSION_DENIED
                    title = '❌ Location permission was denied';
                    details = 'In Chrome or Edge, click the lock/tune icon next to the URL in your address bar, change <strong>Location</strong> to <strong>Allow</strong>, and click <strong>Retry Location</strong>. Alternatively, you can drop a pin directly on the map below.';
                    break;
                case 2: // POSITION_UNAVAILABLE
                    title = '❌ Device location services are unavailable';
                    details = 'Your device cannot determine position. If using Windows 11, verify that <em>Windows Settings → Privacy & Security → Location</em> is turned <strong>ON</strong>. You can also select the location directly on the map below.';
                    break;
                case 3: // TIMEOUT
                    title = '⏱ Device location timed out';
                    details = 'Could not obtain a satellite or Wi-Fi fix in time. Click <strong>Retry Location</strong> or drop a pin directly on the map below.';
                    break;
                default:
                    title = '⚠ Could not detect device location';
                    details = 'Please click <strong>Retry Location</strong> or select your location on the map below.';
                    break;
            }

            showManualFallback('<strong>' + title + '</strong><br><span style="font-size:0.85rem;color:var(--text-muted);">' + details + '</span>', true);
        }

        function startLocationDetection() {
            stopLocationSampling();

            bestPosition = null;
            readingCount = 0;
            isSampling = true;

            if (latInput) latInput.value = '';
            if (lonInput) lonInput.value = '';
            if (locNameInput) locNameInput.value = '';
            if (devLatInput) devLatInput.value = '';
            if (devLonInput) devLonInput.value = '';
            if (accInput) accInput.value = '';
            if (srcInput) srcInput.value = '';

            if (detectedLocationCard) detectedLocationCard.style.display = 'none';

            gpsStatus.innerHTML = '📍 <strong>Detecting device location…</strong> (sampling GPS & Wi-Fi fix)';
            if (gpsHint) gpsHint.textContent = 'Collecting high-accuracy readings…';
            if (retryBtn) {
                retryBtn.disabled = true;
                retryBtn.textContent = 'Sampling GPS…';
            }

            if (!window.isSecureContext) {
                showManualFallback('⚠ <strong>Secure Context Required:</strong> Geolocation requires HTTPS (or localhost). Please enter your location manually or select on the map.', true);
                return;
            }

            if (!navigator.geolocation) {
                showManualFallback('⚠ <strong>Unsupported Browser:</strong> This browser does not support geolocation. Please enter your location manually or select on the map.', true);
                return;
            }

            // Master timeout: locks in best reading after up to MASTER_TIMEOUT_MS
            masterTimer = setTimeout(function () {
                if (isSampling) {
                    finalizeBestReading();
                }
            }, MASTER_TIMEOUT_MS);

            try {
                activeWatchId = navigator.geolocation.watchPosition(
                    function onPosition(pos) {
                        if (!isSampling) return;

                        const coords = pos && pos.coords;
                        if (!coords || !isFinite(coords.latitude) || !isFinite(coords.longitude)) return;

                        readingCount++;
                        const currentAcc = Number(coords.accuracy);

                        // Keep the best reading (lowest uncertainty in metres)
                        if (!bestPosition || currentAcc < Number(bestPosition.coords.accuracy)) {
                            bestPosition = pos;
                        }

                        const bestAcc = Math.round(Number(bestPosition.coords.accuracy));
                        gpsStatus.innerHTML = '📍 <strong>Refining location…</strong> (reading #' + readingCount +
                            ', best accuracy: ±' + bestAcc + ' m)';

                        // If high-accuracy satellite fix is achieved (<= 25m), finish immediately
                        if (bestPosition.coords.accuracy <= PRECISE_ACCURACY_THRESHOLD) {
                            finalizeBestReading();
                        }
                    },
                    function onError(err) {
                        if (!isSampling) return;
                        handleLocationError(err);
                    },
                    {
                        enableHighAccuracy: true,
                        timeout: 8000,
                        maximumAge: 0
                    }
                );
            } catch (e) {
                handleLocationError({ code: 2, message: e.message });
            }
        }

        // Start location detection automatically on page load
        startLocationDetection();

        if (retryBtn) {
            retryBtn.addEventListener('click', function (e) {
                e.preventDefault();
                startLocationDetection();
            });
        }

        // Form submission validation: allow coordinates OR manual address
        const form = document.getElementById('reportForm');
        const submitBtn = document.getElementById('submitBtn');
        if (form) {
            form.addEventListener('submit', function (e) {
                const hasCoordinates = latInput && lonInput && latInput.value && lonInput.value;
                const hasManualText = manualInput && manualInput.value.trim().length > 0;

                if (!hasCoordinates && !hasManualText) {
                    e.preventDefault();
                    if (gpsStatus) {
                        gpsStatus.innerHTML = '⚠ <strong>Location required:</strong> Please click <em>Retry Location</em>, drop a pin on the map, or enter a nearby landmark/street address.';
                    }
                    if (manualBox) manualBox.style.display = 'block';
                    if (manualInput) manualInput.focus();
                    return;
                }

                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.textContent = 'Analyzing…';
                }
            });
        }
    }

    // ---------------------------------------------------------------------------
    // Photo Preview
    // ---------------------------------------------------------------------------
    const photoInput = document.getElementById('photo');
    const preview = document.getElementById('photoPreview');
    if (photoInput && preview) {
        photoInput.addEventListener('change', function () {
            const file = this.files && this.files[0];
            if (!file) {
                preview.style.display = 'none';
                return;
            }
            const reader = new FileReader();
            reader.onload = function (e) {
                preview.src = e.target.result;
                preview.style.display = 'block';
            };
            reader.readAsDataURL(file);
        });
    }

    // ---------------------------------------------------------------------------
    // Category Confirmation Sync
    // ---------------------------------------------------------------------------
    const confirmedCategory = document.getElementById('confirmedCategory');
    const confirmedCategoryHidden = document.getElementById('confirmedCategoryHidden');
    if (confirmedCategory && confirmedCategoryHidden) {
        confirmedCategoryHidden.value = confirmedCategory.value;
        confirmedCategory.addEventListener('change', function () {
            confirmedCategoryHidden.value = this.value;
            const reviewCategory = document.querySelector('.review-category-value');
            if (reviewCategory) reviewCategory.textContent = this.value;
        });
    }

    // ---------------------------------------------------------------------------
    // Wizard Navigation
    // ---------------------------------------------------------------------------
    const panels = document.querySelectorAll('.wizard-panel');
    const steps = document.querySelectorAll('.wizard-step');

    function goToStep(n) {
        panels.forEach(function (p) {
            p.style.display = (p.dataset.panel === String(n)) ? 'block' : 'none';
        });
        steps.forEach(function (s) {
            s.classList.toggle('active', parseInt(s.dataset.step, 10) <= Number(n));
        });

        // When switching to Location panel, trigger map redraw
        if (String(n) === '2' && leafletMap) {
            setTimeout(function () {
                leafletMap.invalidateSize();
            }, 100);
        }
    }

    document.querySelectorAll('.wizard-next').forEach(function (btn) {
        btn.addEventListener('click', function () {
            if (this.dataset.next === '2') {
                const category = document.getElementById('category');
                const description = document.getElementById('description');
                const photo = document.getElementById('photo');

                if (photo && !photo.files.length) {
                    photo.reportValidity();
                    return;
                }
                if (category && !category.value) {
                    category.reportValidity();
                    return;
                }
                if (description && !description.checkValidity()) {
                    description.reportValidity();
                    return;
                }
            }
            goToStep(this.dataset.next);
        });
    });

    document.querySelectorAll('.wizard-back').forEach(function (btn) {
        btn.addEventListener('click', function () {
            goToStep(this.dataset.back);
        });
    });
});
