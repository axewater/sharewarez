document.addEventListener("DOMContentLoaded", function() {
    
    const downloads = document.querySelectorAll("tr[data-game-uuid]");
    console.log
    downloads.forEach((download) => {
        const gameUuid = download.getAttribute("data-game-uuid");
        setInterval(() => checkDownloadStatus(gameUuid), 10000); // every 10 seconds
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
    statusCell.innerHTML = '<span class="status-value">Available</span>';

    // Update the actions cell with the CSRF token included in the form
    const actionsCell = downloadRow.querySelector(".actions-cell");
    actionsCell.innerHTML = `<a href="/download_zip/${downloadId}" class="btn btn-primary">Download</a>
                             <form action="/delete_download/${downloadId}" method="post" style="display: inline;">
                                 <input type="hidden" name="csrf_token" value="${csrfToken}">
                                 <button type="submit" class="btn btn-danger">Delete</button>
                             </form>`;
}

