document.addEventListener('DOMContentLoaded', function() {
    // Function to toggle password visibility
    function togglePasswordVisibility(inputId, iconId) {
        const passwordInput = document.getElementById(inputId);
        const eyeIcon = document.getElementById(iconId);
        
        if (passwordInput.type === 'password') {
            passwordInput.type = 'text';
            eyeIcon.classList.remove('fa-eye');
            eyeIcon.classList.add('fa-eye-slash');
        } else {
            passwordInput.type = 'password';
            eyeIcon.classList.remove('fa-eye-slash');
            eyeIcon.classList.add('fa-eye');
        }
    }

    // Add event listeners for both password fields
    document.querySelectorAll('.toggle-password').forEach(button => {
        button.addEventListener('click', function(event) {
            event.preventDefault();
            const inputId = this.getAttribute('data-input');
            const iconId = this.querySelector('i').id;
            togglePasswordVisibility(inputId, iconId);
        });
    });

    // Validate passwords match
    const passwordForm = document.getElementById('password-form');
    const password = document.getElementById('password');
    const confirmPassword = document.getElementById('confirm_password');
    const submitButton = document.querySelector('input[type="submit"]');

    function validatePasswords() {
        if (password.value !== confirmPassword.value) {
            confirmPassword.setCustomValidity("Passwords do not match");
            return false;
        } else {
            confirmPassword.setCustomValidity('');
            return true;
        }
    }

    if (passwordForm) {
        passwordForm.addEventListener('submit', function(event) {
            if (!validatePasswords()) {
                event.preventDefault();
            }
        });

        confirmPassword.addEventListener('input', validatePasswords);
        password.addEventListener('input', validatePasswords);
    }
});
