document.addEventListener('DOMContentLoaded', function() {
    // Initialize UI elements
    const smtpEnabledCheckbox = document.getElementById('smtp_enabled');
    // CSRF token now handled by CSRFUtils
    // const csrfToken = document.querySelector('meta[name="csrf-token"]');
    const formFields = document.querySelectorAll('.form-control');
    const saveButton = document.querySelector('.btn-primary');
    const testButton = document.querySelector('.btn-secondary');
    const testResultsDiv = document.getElementById('testResults');

    // Define test settings function
    window.testSettings = function() {
        testResultsDiv.innerHTML = '<div class="alert alert-info">Testing SMTP connection...</div>';
        testButton.disabled = true;

        fetch('/admin/smtp_test', {
            method: 'POST',
            headers: CSRFUtils.getHeaders({
                'Content-Type': 'application/json'
            })
        })
        .then(response => response.json())
        .then(data => {
            testButton.disabled = false;
            if (data.success) {
                testResultsDiv.innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle"></i> ${data.message || 'SMTP connection successful'}
                    </div>`;
            } else {
                testResultsDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle"></i> ${data.message || 'SMTP connection failed'}
                    </div>`;
            }
        })
        .catch(error => {
            testButton.disabled = false;
            testResultsDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle"></i> Error testing SMTP connection: ${error.message || 'Unknown error'}
                </div>`;
        });
    }

    // Define functions in global scope
    window.saveSettings = function() {
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
            headers: CSRFUtils.getHeaders({
                'Content-Type': 'application/json'
            }),
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
});
