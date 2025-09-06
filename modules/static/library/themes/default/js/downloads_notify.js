// Browser notification support
let notificationPermission = 'default';

// Check and request notification permission
async function requestNotificationPermission() {
    if ('Notification' in window) {
        notificationPermission = await Notification.requestPermission();
        return notificationPermission === 'granted';
    }
    return false;
}

// Show browser notification
function showBrowserNotification(title, body) {
    if ('Notification' in window && notificationPermission === 'granted') {
        const notification = new Notification(title, {
            body: body,
            icon: '/static/favicon.ico', // Use site favicon as notification icon
            badge: '/static/favicon.ico',
            requireInteraction: false,
            tag: 'sharewarez-download' // This replaces previous notifications
        });

        // Focus window when notification is clicked
        notification.onclick = function() {
            window.focus();
            notification.close();
        };

        // Auto-close notification after 10 seconds
        setTimeout(() => {
            notification.close();
        }, 10000);
    }
}

// Track processing downloads in session storage
function initializeProcessingDownloads() {
    if (!sessionStorage.getItem('processingDownloads')) {
        sessionStorage.setItem('processingDownloads', JSON.stringify({}));
    }
}

// Add a download to track
function addProcessingDownload(gameUuid, gameName, fileName) {
    const downloads = JSON.parse(sessionStorage.getItem('processingDownloads'));
    downloads[gameUuid] = {
        name: gameName,
		file: fileName,
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
    
    for (const [download_id, info] of Object.entries(downloads)) {
        fetch(`/check_download_status/${download_id}`)
            .then(response => response.json())
            .then(data => {
                if (!data.found) {
                    // Remove from tracking if the download no longer exists
                    removeProcessingDownload(download_id);
                    return;
                }
                
                if (data.status === 'available') {
                    const successMessage = `Download file "${info.file}" for ${info.name} has completed processing`;
                    showFlashMessage(successMessage, 'success');
                    
                    // Show browser notification for successful download
                    showBrowserNotification(
                        'Download Complete! 🎮',
                        `${info.name} is ready to download`
                    );
                    
                    removeProcessingDownload(download_id);
                } else if (data.status === 'failed') {
                    const errorMessage = `Download failed for "${info.file}"`;
                    showFlashMessage(errorMessage, 'error');
                    
                    // Show browser notification for failed download
                    showBrowserNotification(
                        'Download Failed ❌',
                        `Failed to prepare ${info.name} for download`
                    );
                    
                    removeProcessingDownload(download_id);
                }
            })
            .catch(error => {
                console.warn('Error checking download status:', error);
                // Don't remove the download from tracking on network errors
            });
    }
}

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', async () => {
    initializeProcessingDownloads();
    
    // Initialize notification permission
    if ('Notification' in window) {
        notificationPermission = Notification.permission;
        
        // If permission is default (not yet asked), request permission
        // Only request on pages where downloads are relevant
        if (notificationPermission === 'default' && 
            (window.location.pathname === '/downloads' || 
             window.location.pathname.includes('/download_game/') ||
             window.location.pathname.includes('/download_other/'))) {
            
            // Show a subtle info message before requesting permission
            showFlashMessage('Enable browser notifications to get alerts when your downloads are ready!', 'info');
            
            // Request permission after a short delay to let user read the message
            setTimeout(async () => {
                await requestNotificationPermission();
            }, 2000);
        }
    }
    
    // Start periodic checking of processing downloads
    setInterval(checkProcessingDownloads, 5000);
});
