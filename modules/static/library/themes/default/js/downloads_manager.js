document.addEventListener("DOMContentLoaded", function() {
    // Easter egg click handler for the download banner
    const downloadBanner = document.querySelector('.logo-download img');
    if (downloadBanner) {
        downloadBanner.addEventListener('click', function(e) {
            // Get click coordinates relative to the image
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            console.log(x, y);
            // Calculate center point
            const centerX = this.width / 2;
            const centerY = this.height / 2;
            console.log(centerX, centerY);
            // Check if click is within 25x25px area of center
            if (Math.abs(x - centerX) <= 12.5 && Math.abs(y - centerY) <= 12.5) {
                console.log('Easter egg activated!');
                // Remove existing animation class if present
                this.classList.remove('bounce-wiggle');
                // Force reflow
                void this.offsetWidth;
                // Add animation class
                this.classList.add('bounce-wiggle');
            }
        });
    }

    // Auto-dismiss flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(flash => {
        setTimeout(() => {
            if (flash && flash.parentNode) {
                flash.remove();
            }
        }, 5000);
    });

    const downloads = document.querySelectorAll("tr[data-download-id]");
    
    downloads.forEach((download) => {
        const download_id = download.getAttribute("data-download-id");
        const gameName = download.querySelector("td").textContent;
        const fileName = download.querySelector(".file-name-cell").textContent;	
        
        // Status handling removed - no longer tracking processing downloads
        
        checkDownloadStatus(download_id);
        setInterval(() => checkDownloadStatus(download_id), 5000);
    });
});

function checkDownloadStatus(download_id) {
    fetch(`/check_download_status/${download_id}`)
    .then(response => response.json())
    .then(data => {
        if (data.status === 'available') {
            const downloadRow = document.querySelector(`tr[data-download-id="${download_id}"]`);
            if (downloadRow) {
                updateDownloadRow(downloadRow, data.downloadId);
            }
        }
    })
    .catch(error => console.error('Error fetching download status:', error));
}

function updateDownloadRow(downloadRow, downloadId) {
    // Update the status cell
    const statusCell = downloadRow.querySelector(".status-cell");
    statusCell.innerHTML = '<span class="status-value" style="color: #005f00; background-color: #e8ffe8; border: 2px solid #004c00; padding: 2px 6px; border-radius: 4px; font-weight: bold;">Available</span>';

    
    const csrfToken = CSRFUtils.getToken();
    // Update the actions cell with the CSRF token included in the form
    const actionsCell = downloadRow.querySelector(".actions-cell");
    actionsCell.innerHTML = `<a href="/download_zip/${downloadId}" class="btn btn-primary">Download</a>
                             <form action="/delete_download/${downloadId}" method="post" style="display: inline;">
                                 <input type="hidden" name="csrf_token" value="${csrfToken}">
                                 <button type="submit" class="btn btn-danger">Delete</button>
                             </form>`;
}

