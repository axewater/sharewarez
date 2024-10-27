// Track processing downloads in session storage
function initializeProcessingDownloads() {
    if (!sessionStorage.getItem('processingDownloads')) {
        sessionStorage.setItem('processingDownloads', JSON.stringify({}));
    }
}

// Add a download to track
function addProcessingDownload(gameUuid, gameName) {
    const downloads = JSON.parse(sessionStorage.getItem('processingDownloads'));
    downloads[gameUuid] = {
        name: gameName,
        timestamp: Date.now()
    };
    sessionStorage.setItem('processingDownloads', JSON.stringify(downloads));
}

// Remove a download from tracking
function removeProcessingDownload(gameUuid) {
    const downloads = JSON.parse(sessionStorage.getItem('processingDownloads'));
    delete downloads[gameUuid];
    sessionStorage.setItem('processingDownloads', JSON.stringify(downloads));
}

// Create and show a flash message
function showFlashMessage(message, type = 'info') {
    const flashesContainer = document.querySelector('.flashes');
    if (!flashesContainer) {
        const contentFlash = document.querySelector('.content-flash');
        if (contentFlash) {
            const newFlashesContainer = document.createElement('div');
            newFlashesContainer.className = 'flashes';
            contentFlash.appendChild(newFlashesContainer);
        }
    }

    const flash = document.createElement('div');
    flash.className = `flash flash-${type}`;
    flash.textContent = message;

    // Add close button
    const closeButton = document.createElement('button');
    closeButton.className = 'flash-close';
    closeButton.innerHTML = '&times;';
    closeButton.onclick = () => flash.remove();
    flash.appendChild(closeButton);

    document.querySelector('.flashes').appendChild(flash);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (flash && flash.parentNode) {
            flash.remove();
        }
    }, 5000);
}

// Check status of all processing downloads
function checkProcessingDownloads() {
    const downloads = JSON.parse(sessionStorage.getItem('processingDownloads'));
    
    for (const [gameUuid, info] of Object.entries(downloads)) {
        fetch(`/check_download_status/${gameUuid}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'available') {
                    showFlashMessage(`Download "${info.name}" has completed processing`, 'success');
                    removeProcessingDownload(gameUuid);
                }
            })
            .catch(error => console.error('Error checking download status:', error));
    }
}

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', () => {
    initializeProcessingDownloads();
    
    // Start periodic checking of processing downloads
    setInterval(checkProcessingDownloads, 3000);
});
