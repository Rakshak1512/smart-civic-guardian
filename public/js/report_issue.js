document.addEventListener('DOMContentLoaded', function () {
    const gpsStatus = document.getElementById('gpsStatus');
    const manualBox = document.getElementById('manualLocationBox');
    const latInput = document.getElementById('latitude');
    const lonInput = document.getElementById('longitude');
    const locNameInput = document.getElementById('location_name');
    const manualInput = document.getElementById('manual_location');
    const retryBtn = document.getElementById('retryGpsBtn');

    if (gpsStatus) {
        function showManualFallback(message) {
            gpsStatus.textContent = message;
            manualBox.style.display = 'block';
        }

        function detectLocation() {
            manualBox.style.display = 'none';
            gpsStatus.textContent = '📍 Attempting to detect your location...';

            if (!navigator.geolocation) {
                showManualFallback('⚠ Geolocation is not supported by this browser. Please enter your location manually.');
                return;
            }

            navigator.geolocation.getCurrentPosition(
                function (position) {
                    latInput.value = position.coords.latitude;
                    lonInput.value = position.coords.longitude;
                    locNameInput.value = 'Detected via GPS';
                    gpsStatus.textContent = '✅ Location detected successfully via GPS.';
                    manualBox.style.display = 'none';
                },
                function () {
                    latInput.value = '';
                    lonInput.value = '';
                    showManualFallback('⚠ GPS location unavailable or permission denied. Please enter your location manually below.');
                },
                { timeout: 8000, enableHighAccuracy: true }
            );
        }

        detectLocation();
        if (retryBtn) retryBtn.addEventListener('click', detectLocation);

        const form = document.getElementById('reportForm');
        const submitBtn = document.getElementById('submitBtn');
        if (form) {
            form.addEventListener('submit', function (e) {
                const hasGps = latInput.value && lonInput.value;
                const hasManual = manualInput.value.trim().length > 0;
                if (!hasGps && !hasManual) {
                    e.preventDefault();
                    showManualFallback('⚠ Please enter a location manually since GPS could not be detected.');
                    manualInput.focus();
                    return;
                }
                submitBtn.disabled = true;
                submitBtn.textContent = 'Analyzing...';
            });
        }
    }

    const photoInput = document.getElementById('photo');
    const preview = document.getElementById('photoPreview');
    if (photoInput) {
        photoInput.addEventListener('change', function () {
            const file = this.files[0];
            if (!file) { preview.style.display = 'none'; return; }
            const reader = new FileReader();
            reader.onload = function (e) {
                preview.src = e.target.result;
                preview.style.display = 'block';
            };
            reader.readAsDataURL(file);
        });
    }

    const panels = document.querySelectorAll('.wizard-panel');
    const steps = document.querySelectorAll('.wizard-step');
    function goToStep(n) {
        panels.forEach(function (p) { p.style.display = (p.dataset.panel === String(n)) ? 'block' : 'none'; });
        steps.forEach(function (s) { s.classList.toggle('active', parseInt(s.dataset.step) <= n); });
    }
    document.querySelectorAll('.wizard-next').forEach(function (btn) {
        btn.addEventListener('click', function () { goToStep(this.dataset.next); });
    });
    document.querySelectorAll('.wizard-back').forEach(function (btn) {
        btn.addEventListener('click', function () { goToStep(this.dataset.back); });
    });
});