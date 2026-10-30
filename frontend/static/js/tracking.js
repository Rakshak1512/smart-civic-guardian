// Small UX helper for the track-status / feedback form: prevents a
// double submission of feedback while the request is in flight.

document.addEventListener('DOMContentLoaded', function () {
    const feedbackForm = document.querySelector('.feedback-section form');
    if (!feedbackForm) return;

    feedbackForm.addEventListener('submit', function () {
        const btn = feedbackForm.querySelector('button[type="submit"]');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Submitting...';
        }
    });
});
