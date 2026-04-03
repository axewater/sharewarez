document.addEventListener('DOMContentLoaded', function() {
    console.log("Discord notifications DOMContentLoaded event triggered.");

    const notificationForm = document.getElementById('discordNotificationForm');
    if (!notificationForm) {
        console.log("Discord notification form not found");
        return;
    }

    // Initialize tooltips for the notification form
    const tooltipTriggerList = [].slice.call(notificationForm.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Load current notification settings from the server
    loadNotificationSettings();

    // Handle form submission
    notificationForm.addEventListener('submit', function(e) {
        e.preventDefault();
        console.log("Discord notification form submit event triggered.");

        const notificationSettings = {
            discordNotifyNewGames: document.getElementById('discordNotifyNewGames').checked,
            discordNotifyGameUpdates: document.getElementById('discordNotifyGameUpdates').checked,
            discordNotifyGameExtras: document.getElementById('discordNotifyGameExtras').checked,
            discordNotifyDownloads: document.getElementById('discordNotifyDownloads').checked,
            discordNotifyManualTrigger: document.getElementById('discordNotifyManualTrigger').checked
        };

        console.log("Notification settings to be saved:", notificationSettings);

        // Show saving state
        const submitButton = notificationForm.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.innerHTML;
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

        fetch('/admin/discord_notifications', {
            method: 'POST',
            headers: CSRFUtils.getHeaders({
                'Content-Type': 'application/json'
            }),
            body: JSON.stringify(notificationSettings)
        })
        .then(response => {
            console.log("Fetch response received.");
            if (response.ok) {
                return response.json();
            }
            throw new Error('Network response was not ok.');
        })
        .then(data => {
            console.log("Response data:", data);
            if (data.success) {
                $.notify("Discord notification settings saved successfully!", {
                    className: 'success',
                    position: 'top center'
                });
            } else {
                throw new Error(data.message || 'Unknown error');
            }
        })
        .catch(error => {
            console.error('Fetch operation error:', error);
            $.notify("Error saving Discord notification settings: " + error.message, {
                className: 'error',
                position: 'top center'
            });
        })
        .finally(() => {
            // Reset button state
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonText;
        });
    });

    function loadNotificationSettings() {
        // Get current settings from the embedded JSON data
        const currentSettingsElement = document.getElementById('currentSettings');
        if (!currentSettingsElement) {
            console.warn("Current settings data not found in page");
            return;
        }

        try {
            const settings = JSON.parse(currentSettingsElement.textContent);
            console.log("Loaded notification settings from embedded data:", settings);

            // Apply settings to checkboxes
            if (settings.discordNotifyNewGames !== undefined) {
                document.getElementById('discordNotifyNewGames').checked = settings.discordNotifyNewGames;
            }
            if (settings.discordNotifyGameUpdates !== undefined) {
                document.getElementById('discordNotifyGameUpdates').checked = settings.discordNotifyGameUpdates;
            }
            if (settings.discordNotifyGameExtras !== undefined) {
                document.getElementById('discordNotifyGameExtras').checked = settings.discordNotifyGameExtras;
            }
            if (settings.discordNotifyDownloads !== undefined) {
                document.getElementById('discordNotifyDownloads').checked = settings.discordNotifyDownloads;
            }
            if (settings.discordNotifyManualTrigger !== undefined) {
                document.getElementById('discordNotifyManualTrigger').checked = settings.discordNotifyManualTrigger;
            }
        } catch (error) {
            console.error("Error parsing embedded settings data:", error);
        }
    }
});