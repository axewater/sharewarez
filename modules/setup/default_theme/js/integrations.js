/**
 * Integrations Page JavaScript
 * Handles tabbed interface functionality
 */

$(document).ready(function() {

    // Initialize tooltips
    $('[data-toggle="tooltip"]').tooltip();

    // Handle tab switching with smooth animations
    $('#integrationTabs button[data-bs-toggle="tab"]').on('shown.bs.tab', function (e) {
        const target = $(e.target).data('bs-target');
        console.log('Switching to tab:', target);

        // Add fade-in animation to the active tab
        $(target).addClass('animate-tab');
        setTimeout(function() {
            $(target).removeClass('animate-tab');
        }, 300);
    });

    // Add smooth scrolling to tabs when clicked
    $('.integrations-nav-link').on('click', function() {
        $('html, body').animate({
            scrollTop: $('#integrationTabs').offset().top - 100
        }, 300);
    });

    // Add hover effects to buttons
    $('.integration-content .btn-lg').on('mouseenter', function() {
        $(this).addClass('btn-hover');
    }).on('mouseleave', function() {
        $(this).removeClass('btn-hover');
    });

    // Initialize active tab state
    const activeTab = $('#integrationTabs .nav-link.active');
    if (activeTab.length > 0) {
        console.log('Active tab:', activeTab.data('bs-target'));
    }

    console.log('Integrations page JavaScript loaded');

    // SMTP Settings functionality
    initializeSmtpSettings();

    // IGDB Settings functionality
    initializeIgdbSettings();

    // Discord Settings functionality
    initializeDiscordSettings();
});

function initializeSmtpSettings() {
    const smtpEnabledCheckbox = document.getElementById('smtp_enabled');
    const formFields = document.querySelectorAll('.form-control');
    const saveButton = document.querySelector('.btn-primary');
    const testButton = document.querySelector('.btn-secondary');
    const testResultsDiv = document.getElementById('testResults');

    // Define test settings function
    window.testSettings = function() {
        if (!testButton) return;
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
                $.notify("SMTP connection successful", "success");
                // Clear any previous test results
                if (testResultsDiv) testResultsDiv.innerHTML = '';
            } else {
                $.notify("SMTP connection failed: " + (data.message || 'Unknown error'), "error");
                // Clear any previous test results
                if (testResultsDiv) testResultsDiv.innerHTML = '';
            }
        })
        .catch(error => {
            testButton.disabled = false;
            $.notify("Error testing SMTP connection: " + (error.message || 'Unknown error'), "error");
            // Clear any previous test results
            if (testResultsDiv) testResultsDiv.innerHTML = '';
        });
    }

    // Define save settings function
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
}

function initializeIgdbSettings() {
    // Initialize collapse functionality for IGDB instructions panel
    const igdbInstructionsPanel = document.getElementById('igdbInstructionsPanel');
    const igdbToggleIcon = document.getElementById('igdbToggleIcon');

    if (igdbInstructionsPanel) {
        igdbInstructionsPanel.addEventListener('show.bs.collapse', function () {
            igdbToggleIcon.classList.remove('fa-chevron-down');
            igdbToggleIcon.classList.add('fa-chevron-up');
        });

        igdbInstructionsPanel.addEventListener('hide.bs.collapse', function () {
            igdbToggleIcon.classList.remove('fa-chevron-up');
            igdbToggleIcon.classList.add('fa-chevron-down');
        });
    }

    // Initialize password visibility toggle for IGDB
    initializePasswordToggle();

    // Define IGDB save settings function
    window.saveIgdbSettings = function() {
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

        fetch('/admin/integrations/igdb/save', {
            method: 'POST',
            headers: CSRFUtils.getHeaders({
                'Content-Type': 'application/json'
            }),
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

    // Define IGDB test settings function
    window.testIgdbSettings = function() {
        const testButton = document.querySelector('#igdb .btn-secondary');
        const spinner = document.getElementById('igdbLoadingSpinner');

        if (spinner) {
            spinner.style.display = 'flex';
        }

        const originalText = testButton.textContent;
        testButton.disabled = true;

        fetch('/admin/integrations/igdb/test', {
            method: 'POST',
            headers: CSRFUtils.getHeaders({
                'Content-Type': 'application/json'
            })
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
            if (spinner) {
                spinner.style.display = 'none';
            }
            testButton.textContent = originalText;
        });
    };
}

function initializePasswordToggle() {
    // Set up password visibility toggles for IGDB
    const toggleButtons = document.querySelectorAll('.toggle-password');

    toggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const inputId = this.getAttribute('data-input');
            const input = document.getElementById(inputId);
            const icon = this.querySelector('i');

            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        });
    });
}

function initializeDiscordSettings() {
    // Initialize collapse functionality for Discord instructions panel
    const discordInstructionsPanel = document.getElementById('discordInstructionsPanel');
    const discordToggleIcon = document.getElementById('discordToggleIcon');

    if (discordInstructionsPanel) {
        discordInstructionsPanel.addEventListener('show.bs.collapse', function () {
            discordToggleIcon.classList.remove('fa-chevron-down');
            discordToggleIcon.classList.add('fa-chevron-up');
        });

        discordInstructionsPanel.addEventListener('hide.bs.collapse', function () {
            discordToggleIcon.classList.remove('fa-chevron-up');
            discordToggleIcon.classList.add('fa-chevron-down');
        });
    }

    // Define Discord save settings function
    window.saveDiscordSettings = function() {
        const webhookUrl = document.getElementById('discord_webhook_url').value.trim();
        const botName = document.getElementById('discord_bot_name').value.trim();
        const botAvatarUrl = document.getElementById('discord_bot_avatar_url').value.trim();

        // Basic validation
        if (!webhookUrl || webhookUrl === 'insert_webhook_url_here') {
            $.notify("Please enter a valid Discord webhook URL", "error");
            return;
        }

        if (!webhookUrl.startsWith('https://discord.com/api/webhooks/') && !webhookUrl.startsWith('https://discordapp.com/api/webhooks/')) {
            $.notify("Please enter a valid Discord webhook URL", "error");
            return;
        }

        // Create form data to submit to existing Discord settings endpoint
        const formData = new FormData();
        formData.append('csrf_token', CSRFUtils.getToken());
        formData.append('discord_webhook_url', webhookUrl);
        formData.append('discord_bot_name', botName || 'SharewareZ Bot');
        formData.append('discord_bot_avatar_url', botAvatarUrl || 'insert_bot_avatar_url_here');

        fetch('/admin/discord_settings', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (response.ok) {
                $.notify("Discord settings saved successfully", "success");
                // Reload page to show updated "last tested" info if available
                setTimeout(() => location.reload(), 1500);
            } else {
                return response.text().then(text => {
                    // Try to extract error message from response
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(text, 'text/html');
                    const alerts = doc.querySelectorAll('.alert-danger, .alert-error');
                    if (alerts.length > 0) {
                        const errorText = alerts[0].textContent.trim();
                        $.notify("Error saving Discord settings: " + errorText, "error");
                    } else {
                        $.notify("Error saving Discord settings", "error");
                    }
                });
            }
        })
        .catch(error => {
            $.notify("Error saving Discord settings: " + error.message, "error");
        });
    };

    // Define Discord test webhook function
    window.testDiscordWebhook = function() {
        const webhookUrl = document.getElementById('discord_webhook_url').value.trim();
        const botName = document.getElementById('discord_bot_name').value.trim();
        const botAvatarUrl = document.getElementById('discord_bot_avatar_url').value.trim();

        // Validation
        if (!webhookUrl || webhookUrl === 'insert_webhook_url_here') {
            $.notify("Please enter a webhook URL first", "error");
            return;
        }

        const testButton = document.querySelector('#discord .btn-secondary');
        const spinner = document.getElementById('discordLoadingSpinner');

        if (spinner) {
            spinner.style.display = 'flex';
        }

        const originalText = testButton.textContent;
        testButton.disabled = true;
        testButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';

        fetch('/admin/test_discord_webhook', {
            method: 'POST',
            headers: CSRFUtils.getHeaders({
                'Content-Type': 'application/json'
            }),
            body: JSON.stringify({
                webhook_url: webhookUrl,
                bot_name: botName || 'SharewareZ Bot',
                bot_avatar_url: botAvatarUrl || 'insert_bot_avatar_url_here'
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                $.notify("Discord webhook test successful! Check your Discord channel.", "success");
                setTimeout(() => location.reload(), 2000);
            } else {
                $.notify("Discord webhook test failed: " + data.message, "error");
            }
        })
        .catch(error => {
            $.notify("Error testing Discord webhook: " + error.message, "error");
        })
        .finally(() => {
            testButton.disabled = false;
            testButton.textContent = originalText;
            if (spinner) {
                spinner.style.display = 'none';
            }
        });
    };
}