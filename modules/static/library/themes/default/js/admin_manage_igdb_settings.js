document.addEventListener('DOMContentLoaded', function() {
    // Initialize collapse functionality for instructions panel
    const instructionsPanel = document.getElementById('instructionsPanel');
    const toggleIcon = document.getElementById('toggleIcon');
    
    if (instructionsPanel) {
        instructionsPanel.addEventListener('show.bs.collapse', function () {
            toggleIcon.classList.remove('fa-chevron-down');
            toggleIcon.classList.add('fa-chevron-up');
        });
        
        instructionsPanel.addEventListener('hide.bs.collapse', function () {
            toggleIcon.classList.remove('fa-chevron-up');
            toggleIcon.classList.add('fa-chevron-down');
        });
    }

    // Define save settings function
    window.saveSettings = function() {
        const clientId = document.getElementById('igdb_client_id').value;
        const clientSecret = document.getElementById('igdb_client_secret').value;

        // Basic validation
        if (clientId.length < 20 || clientSecret.length < 20) {
            $.notify("Client ID and Secret must be at least 20 characters long", "error");
            return;
        }

        const data = {
            igdb_client_id: clientId,
            igdb_client_secret: clientSecret
        };

        fetch('/admin/igdb_settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                $.notify("IGDB settings saved successfully", "success");
            } else {
                $.notify("Error saving IGDB settings: " + data.message, "error");
            }
        })
        .catch(error => {
            $.notify("Error saving IGDB settings: " + error, "error");
        });
    };

    // Define test settings function
    window.testSettings = function() {
        const testButton = document.querySelector('button.btn-secondary');
        const spinner = document.getElementById('loadingSpinner');
        spinner.style.display = 'flex';  // Changed from 'block' to 'flex'
        const originalText = testButton.textContent;
        testButton.disabled = true;
        
        fetch('/admin/test_igdb', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                $.notify("IGDB API test successful", "success");
                setTimeout(() => location.reload(), 2000);
            } else {
                $.notify("IGDB API test failed: " + data.message, "error");
            }
        })
        .catch(error => {
            $.notify("Error testing IGDB API: " + error, "error");
        })
        .finally(() => {
            testButton.disabled = false;
            spinner.style.display = 'none';
            testButton.textContent = originalText;
        });
    };

    // Add password visibility toggle functionality
    const togglePassword = document.querySelector('.toggle-password');
    const passwordInput = document.querySelector('#igdb_client_secret');

    togglePassword.addEventListener('click', function() {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        // Toggle the eye icon
        this.querySelector('i').classList.toggle('fa-eye');
        this.querySelector('i').classList.toggle('fa-eye-slash');
    });
});
