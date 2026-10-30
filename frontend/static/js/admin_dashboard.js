// Small UX helpers shared across authority pages (manage complaints /
// complaint detail): confirm before destructive-ish actions and disable
// buttons on submit to avoid double-clicks.

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.management-forms form').forEach(function (form) {
        form.addEventListener('submit', function () {
            const btn = form.querySelector('button[type="submit"]');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Saving...';
            }
        });
    });

    // Auto-submit the filter form when a dropdown changes, for a snappier feel
    const filterBar = document.querySelector('.filter-bar');
    if (filterBar) {
        filterBar.querySelectorAll('select').forEach(function (select) {
            select.addEventListener('change', function () {
                filterBar.submit();
            });
        });
    }
});
