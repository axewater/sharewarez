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