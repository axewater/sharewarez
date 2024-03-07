document.addEventListener("DOMContentLoaded", function() {
    
    const downloads = document.querySelectorAll("tr[data-game-uuid]");
    console.log
    downloads.forEach((download) => {
        const gameUuid = download.getAttribute("data-game-uuid");
        checkDownloadStatus(gameUuid);
        setInterval(() => checkDownloadStatus(gameUuid), 3000); // every 3 seconds
    });
});

function checkDownloadStatus(gameUuid) {
    fetch(`/check_download_status/${gameUuid}`)
    .then(response => response.json())
    .then(data => {
        if (data.status === 'available') {
            const downloadRow = document.querySelector(`tr[data-game-uuid="${gameUuid}"]`);
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