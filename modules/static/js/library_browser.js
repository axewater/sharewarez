document.addEventListener('DOMContentLoaded', function() {
    console.log('Game downloads loaded');
    document.querySelectorAll('.download-form').forEach(form => {
        form.onsubmit = function(e) {
            e.preventDefault(); // Prevent form submission
            console.log('Download form submitted');
            const gameUuid = this.querySelector('input[type="submit"]').getAttribute('data-game-uuid');
            const statusDiv = document.getElementById(`download-status-${gameUuid}`);
            statusDiv.innerHTML = 'Initiating download...';

            // First, initiate the download process
            fetch(`/download_game/${gameUuid}`)
                .then(response => {
                    if(response.ok) {
                        console.log(`Download initiated for ${gameUuid}`);
                        statusDiv.innerHTML = 'Processing download...';
                        startPolling(gameUuid); // Then start polling
                    } else {
                        console.error('Failed to initiate download.');
                        statusDiv.innerHTML = 'Failed to initiate download. Please try again.';
                    }
                }).catch(error => {
                    console.error('Error:', error);
                    statusDiv.innerHTML = 'Error initiating download.';
                });
        };
    });
});


function startPolling(gameUuid) {
    const statusDiv = document.getElementById(`download-status-${gameUuid}`);
    const intervalId = setInterval(() => {
        // Correct placement of fetch and chaining of .then()
        fetch(`/check_download_status/${gameUuid}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'available') {
                    console.log('Download ready for ' + gameUuid);
                    clearInterval(intervalId); // Stop polling
                    statusDiv.innerHTML = `<a href="/download_zip/${data.downloadId}" class="button-glass">Download Ready</a>`;
                } else if (data.status === 'processing') {
                    // Update status, keep polling
                    console.log('Download processing for ' + gameUuid);
                    statusDiv.innerHTML = 'Your download is being processed...';
                }
            }).catch(error => {
                console.error('Error:', error);
                statusDiv.innerHTML = 'Error checking download status.';
                clearInterval(intervalId);
            });
        console.log('Checking download status for ' + gameUuid);
    }, 5000); // Poll every 5 seconds
}

function confirmDeletion(gameName) {
    return confirm(`Are you sure you want to remove "${gameName}"?`);
}
