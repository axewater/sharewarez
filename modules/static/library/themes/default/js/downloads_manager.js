document.addEventListener("DOMContentLoaded", function() {
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
        
        // Add to processing downloads if status is 'processing'
        const statusCell = download.querySelector(".status-cell .status-value");
        if (statusCell && statusCell.textContent.trim().toLowerCase() === 'processing') {
            addProcessingDownload(download_id, gameName, fileName);
        }
        
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

    
    const csrfToken = getCsrfToken();
    // Update the actions cell with the CSRF token included in the form
    const actionsCell = downloadRow.querySelector(".actions-cell");
    actionsCell.innerHTML = `<a href="/download_zip/${downloadId}" class="btn btn-primary">Download</a>
                             <form action="/delete_download/${downloadId}" method="post" style="display: inline;">
                                 <input type="hidden" name="csrf_token" value="${csrfToken}">
                                 <button type="submit" class="btn btn-danger">Delete</button>
                             </form>`;
}

function getCsrfToken() {
    // Attempt to find a CSRF token in the document
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    return csrfInput ? csrfInput.value : null;
}