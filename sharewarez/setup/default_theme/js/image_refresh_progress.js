/**
 * Image Refresh Progress Handler
 * Monitors and displays progress for image refresh operations
 */

(function() {
    'use strict';

    // Check if there's an image refresh in progress on page load
    document.addEventListener('DOMContentLoaded', function() {
        // Check if there's an image-refresh flash message
        const imageRefreshAlert = document.querySelector('.alert-image-refresh');

        if (imageRefreshAlert) {
            // Get the game UUID from the session (we'll need to pass it via data attribute)
            const gameUuid = imageRefreshAlert.dataset.gameUuid;

            if (gameUuid) {
                startProgressTracking(imageRefreshAlert, gameUuid);
            }
        }
    });

    function startProgressTracking(alertElement, gameUuid) {
        // Create and append the spinner SVG
        const spinner = createSpinner();
        alertElement.appendChild(spinner);

        let pollCount = 0;
        const maxPolls = 120; // 2 minutes max (120 * 1000ms)

        const pollInterval = setInterval(function() {
            pollCount++;

            fetch(`/check_image_refresh_progress/${gameUuid}`, {
                method: 'GET',
                headers: CSRFUtils.getHeaders({
                    'X-Requested-With': 'XMLHttpRequest'
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'complete') {
                    // Update progress to 100%
                    updateSpinnerProgress(spinner, 100);

                    // Wait a moment to show completion, then update message
                    setTimeout(function() {
                        alertElement.classList.remove('alert-image-refresh');
                        alertElement.classList.add('alert-success');
                        alertElement.textContent = 'Game updated, images downloaded successfully';

                        // Remove the alert after 3 seconds
                        setTimeout(function() {
                            alertElement.style.opacity = '0';
                            setTimeout(function() {
                                alertElement.remove();
                            }, 300);
                        }, 3000);
                    }, 500);

                    clearInterval(pollInterval);
                } else if (data.status === 'error') {
                    alertElement.classList.remove('alert-image-refresh');
                    alertElement.classList.add('alert-danger');
                    alertElement.textContent = 'Failed to refresh game images';
                    spinner.remove();
                    clearInterval(pollInterval);
                } else if (data.status === 'in_progress') {
                    // Update the progress circle
                    updateSpinnerProgress(spinner, data.progress || 0);
                } else if (data.status === 'not_found' && pollCount > 5) {
                    // If not found after 5 polls, assume it completed
                    alertElement.classList.remove('alert-image-refresh');
                    alertElement.classList.add('alert-success');
                    alertElement.textContent = 'Game updated successfully';
                    spinner.remove();
                    clearInterval(pollInterval);
                }

                // Stop polling after max attempts
                if (pollCount >= maxPolls) {
                    alertElement.classList.remove('alert-image-refresh');
                    alertElement.classList.add('alert-warning');
                    alertElement.textContent = 'Image refresh is taking longer than expected';
                    spinner.remove();
                    clearInterval(pollInterval);
                }
            })
            .catch(error => {
                console.error('Error checking progress:', error);
                // Don't stop polling on network errors, might be temporary
            });
        }, 1000); // Poll every second
    }

    function createSpinner() {
        const spinner = document.createElement('span');
        spinner.className = 'image-refresh-spinner';
        spinner.innerHTML = `
            <svg viewBox="0 0 22 22">
                <circle class="spinner-circle-bg" cx="11" cy="11" r="10"></circle>
                <circle class="spinner-circle-progress" cx="11" cy="11" r="10"></circle>
            </svg>
        `;
        return spinner;
    }

    function updateSpinnerProgress(spinner, progress) {
        const circle = spinner.querySelector('.spinner-circle-progress');
        if (circle) {
            // Calculate stroke-dashoffset based on progress
            // Circle circumference = 2 * PI * r = 2 * 3.14159 * 10 = 62.83
            const circumference = 62.83;
            const offset = circumference - (progress / 100) * circumference;
            circle.style.strokeDashoffset = offset;
        }
    }
})();
