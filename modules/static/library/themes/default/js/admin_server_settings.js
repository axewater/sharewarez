document.addEventListener('DOMContentLoaded', function() {
    console.log("Settings form DOMContentLoaded event triggered.");

    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    const currentSettings = JSON.parse(document.getElementById('currentSettings').textContent);
    console.log("Current settings loaded:", currentSettings);

    // Apply current settings to form
    Object.keys(currentSettings).forEach(function(key) {
        const input = document.getElementById(key);
        if (input && input.type === 'checkbox') {
            input.checked = currentSettings[key];
        } else if (input) {
            input.value = currentSettings[key];
        }
        console.log("Applied setting for:", key, "; Value:", currentSettings[key]);
    });

    // Form submission handler
    document.getElementById('settingsForm').addEventListener('submit', function(e) {
        e.preventDefault();
        console.log("Form submit event triggered.");

        const settings = {
            showSystemLogo: document.getElementById('showSystemLogo').checked,
            showHelpButton: document.getElementById('showHelpButton').checked,
            allowUsersToInviteOthers: document.getElementById('allowUsersToInviteOthers').checked,
            enableWebLinksOnDetailsPage: document.getElementById('enableWebLinksOnDetailsPage').checked,
            enableServerStatusFeature: document.getElementById('enableServerStatusFeature').checked,
            enableNewsletterFeature: document.getElementById('enableNewsletterFeature').checked,
            enableDeleteGameOnDisk: document.getElementById('enableDeleteGameOnDisk').checked,
            showVersion: document.getElementById('showVersion').checked,
			enableGameUpdates: document.getElementById('enableGameUpdates').checked,
            updateFolderName: document.getElementById('updateFolderName').value,
			enableGameExtras: document.getElementById('enableGameExtras').checked,
			extrasFolderName: document.getElementById('extrasFolderName').value,
            discordNotifyNewGames: document.getElementById('discordNotifyNewGames').checked,
            discordNotifyGameUpdates: document.getElementById('discordNotifyGameUpdates').checked,
            discordNotifyDownloads: document.getElementById('discordNotifyDownloads').checked,
        };
        console.log("Settings to be saved:", settings);

        fetch('/admin/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.getElementById('csrf_token').textContent
            },
            body: JSON.stringify(settings)
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
            document.getElementById('settingsSavedNotification').style.display = 'block';
            setTimeout(() => {
                document.getElementById('settingsSavedNotification').style.display = 'none';
            }, 3000);
        })
        .catch(error => {
            console.error('Fetch operation error:', error);
            alert('Error updating settings');
        });
    });
});
