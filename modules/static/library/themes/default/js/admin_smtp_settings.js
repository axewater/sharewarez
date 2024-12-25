document.addEventListener('DOMContentLoaded', function() {
    // Initialize any required UI elements
    const smtpEnabledCheckbox = document.getElementById('smtp_enabled');
    const csrfToken = document.querySelector('meta[name="csrf-token"]');
    const formFields = document.querySelectorAll('.form-control');
    const saveButton = document.querySelector('.btn-primary');
    const testButton = document.querySelector('.btn-secondary');

    if (saveButton) saveButton.addEventListener('click', saveSettings);
    if (testButton) testButton.addEventListener('click', testSettings);
    
    // Check if CSRF token is present
    if (!csrfToken) {
        console.error('CSRF token meta tag not found');
        return;
    }

    // Function to save SMTP settings
    function saveSettings() {
        const data = {
            smtp_enabled: document.getElementById('smtp_enabled').checked,
            smtp_server: document.getElementById('smtp_server').value,
            smtp_port: document.getElementById('smtp_port').value,
            smtp_username: document.getElementById('smtp_username').value,
            smtp_password: document.getElementById('smtp_password').value,
            smtp_use_tls: document.getElementById('smtp_use_tls').checked,
            smtp_default_sender: document.getElementById('smtp_default_sender').value
        };

        fetch('/admin/smtp_settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken.content
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                $.notify("SMTP settings saved successfully", "success");
            } else {
                $.notify("Error saving SMTP settings: " + data.message, "error");
            }
        })
        .catch(error => {
            $.notify("Error saving SMTP settings: " + error, "error");
        });
    }

    // Function to test SMTP settings
    function testSettings() {
        // Show loading indicator
        const testButton = document.querySelector('button.btn-secondary');
        const originalText = testButton.textContent;
        testButton.disabled = true;
        testButton.textContent = 'Testing...';
        
        fetch('/admin/test_smtp', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken.content
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.message || 'Network response was not ok');
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                $.notify({
                    message: "SMTP test successful",
                    type: 'success',
                    delay: 2000,
                    placement: {
                        from: 'top',
                        align: 'center'
                    }
                });
                setTimeout(() => location.reload(), 2000);
            } else {
                $.notify({
                    message: "SMTP test failed: " + data.message,
                    type: 'error',
                    delay: 5000,
                    placement: {
                        from: 'top',
                        align: 'center'
                    }
                });
            }
        })
        .catch(error => {
            $.notify({
                message: "Error testing SMTP: " + error.message,
                type: 'error',
                delay: 5000,
                placement: {
                    from: 'top',
                    align: 'center'
                }
            });
        })
        .finally(() => {
            // Reset button state
            testButton.disabled = false;
            testButton.textContent = originalText;
        });
    }

    // Add event listeners
    const saveSettingsButton = document.querySelector('button[onclick="saveSettings()"]');
    const testSettingsButton = document.querySelector('button[onclick="testSettings()"]');

    if (saveSettingsButton) {
        saveSettingsButton.addEventListener('click', saveSettings);
    } else {
        console.error('Save settings button not found');
    }

    if (testSettingsButton) {
        testSettingsButton.addEventListener('click', testSettings);
    } else {
        console.error('Test settings button not found');
    }
});
