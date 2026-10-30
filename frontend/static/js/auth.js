// Auth page behaviours: role toggle on register page, basic client-side checks.

function toggleAuthorityFields() {
    const roleAuthority = document.querySelector('input[name="role"][value="authority"]');
    const fields = document.getElementById('authorityFields');
    if (!roleAuthority || !fields) return;
    fields.style.display = roleAuthority.checked ? 'block' : 'none';
    const deptInput = document.getElementById('department');
    if (deptInput) deptInput.required = roleAuthority.checked;
}

document.addEventListener('DOMContentLoaded', function () {
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', function (e) {
            const password = document.getElementById('password').value;
            const confirm = document.getElementById('confirm_password').value;
            if (password !== confirm) {
                e.preventDefault();
                alert('Passwords do not match.');
            }
        });
    }
});
