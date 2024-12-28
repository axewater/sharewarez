document.addEventListener('DOMContentLoaded', function() {
    const testButton = document.createElement('button');
    testButton.className = 'btn btn-info ms-2';
    testButton.innerHTML = '<i class="fas fa-vial"></i> Test Webhook';
    testButton.id = 'test-webhook-btn';

    // Find the form's button container and add the test button
    const formButtons = document.querySelector('.d-flex.justify-content-between');
    if (formButtons) {
        formButtons.appendChild(testButton);
    }

    testButton.addEventListener('click', async function(e) {
        e.preventDefault();
        const webhookUrl = document.getElementById('discord_webhook_url').value;
        const botName = document.getElementById('discord_bot_name').value;
        const botAvatarUrl = document.getElementById('discord_bot_avatar_url').value;

        if (!webhookUrl) {
            $.notify("Please enter a webhook URL first", {
                className: 'error',
                position: 'top center'
            });
            return;
        }

        // Get Cross-Site Request Forgery token
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;

        // Disable button and show loading state
        testButton.disabled = true;
        testButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';

        try {
            const response = await fetch('/admin/test_discord_webhook', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    webhook_url: webhookUrl,
                    bot_name: botName,
                    bot_avatar_url: botAvatarUrl
                })
            });

            const data = await response.json();
            // Use notify.js for notifications
            if (response.ok) {
                $.notify("Webhook test successful! Check your Discord channel.", {
                    className: 'success',
                    position: 'top center'
                });
            } else {
                $.notify("Webhook test failed: " + (data.message || "Unknown error"), {
                    className: 'error',
                    position: 'top center'
                });
            }
        } catch (error) {
            $.notify("Error testing webhook: " + error.message, {
                className: 'error',
                position: 'top center'
            });
        } finally {
            // Reset button state
            testButton.disabled = false;
            testButton.innerHTML = '<i class="fas fa-vial"></i> Test Webhook';
        }
    });
});
