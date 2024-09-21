var currentPathAuto = '';
var currentPathManual = '';

function showSpinner() {
    document.getElementById('globalSpinner').style.display = 'block';
}

function hideSpinner() {
    document.getElementById('globalSpinner').style.display = 'none';
}

function attachDeleteFolderFormListeners() {
    document.querySelectorAll('.delete-folder-form').forEach(form => {
        if (!form.dataset.listenerAdded) {
            form.addEventListener('submit', function(event) {
                event.preventDefault();
                const folderPath = form.querySelector('[name="folder_path"]').value;
                
                // Add confirmation dialog
                if (!confirm(`Are you sure you want to delete the folder ${folderPath} FROM DISK?`)) {
                    console.log("Deletion cancelled by user");
                    return; // Exit the function if user cancels
                }

                showSpinner();
                const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

                console.log("Attempting to delete folder with path:", folderPath);

                fetch('/delete_folder', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify({folder_path: folderPath})
                })
                .then(response => response.json())
                .then(data => {
                    console.log("Server response:", data);

                    if(data.status === 'success') {
                        console.log("Deletion successful, removing row.");
                        form.closest('tr').remove();
                    } else {
                        console.log("Deletion not successful:", data.message);
                        if (data.message === "The specified path does not exist or is not a folder. Entry removed if it was in the database.") {
                            console.log("Folder does not exist, removing row.");
                            form.closest('tr').remove();
                        }
                    }
                    alert(data.message);
                })
                .catch(error => {
                    console.error('Fetch error:', error);
                })
                .finally(() => {
                    hideSpinner();
                });
            });
            form.dataset.listenerAdded = 'true';
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    console.log("Document loaded. Setting up form submission handlers and tab activation based on activeTab.");

    const activeTab = document.querySelector('meta[name="active-tab"]').getAttribute('content');
    console.log("Active tab determined from server-side:", activeTab);

    switch (activeTab) {
        case 'manual':
            console.log("Activating manualScan tab.");
            new bootstrap.Tab(document.querySelector('#manualScan-tab')).show();
            break;
        case 'unmatched':
            console.log("Activating unmatchedFolders tab.");
            new bootstrap.Tab(document.querySelector('#unmatchedFolders-tab')).show();
            break;
        case 'deleteLibrary':
            console.log("Activating deleteLibrary tab.");
            new bootstrap.Tab(document.querySelector('#deleteLibrary-tab')).show();
            break;
        default:
            console.log("Defaulting to activating autoScan tab.");
            new bootstrap.Tab(document.querySelector('#autoScan-tab')).show();
    }

    setupFolderBrowse('#browseFoldersBtn', '#folderContents', '#loadingSpinner', '#upFolderBtn', '#folder_path', 'currentPathAuto');
    setupFolderBrowse('#browseFoldersBtnManual', '#folderContentsManual', '#loadingSpinnerManual', '#upFolderBtnManual', '#manualFolderPath', 'currentPathManual');

    var csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    const updateScanJobs = () => {
        fetch('/api/scan_jobs_status', {cache: 'no-store'})
            .then(response => response.json())
            .then(data => {
                const jobsTableBody = document.querySelector('#jobsTableBody');
                jobsTableBody.innerHTML = '';
                // Sort the data array to ensure the latest scan is at the top
                data.sort((a, b) => new Date(b.last_run) - new Date(a.last_run));
                data.forEach(job => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${job.id.substring(0, 8)}</td>
                        <td>${job.library_name || 'N/A'}</td>
                        <td>${Object.keys(job.folders).join(', ')}</td>
                        <td>${job.status}</td>
                        <td>${job.error_message}</td>
                        <td>${job.last_run}</td>
                        <td>${job.total_folders}</td>
                        <td>${job.folders_success}</td>
                        <td>${job.folders_failed}</td>
                        <td>
                            ${job.status === 'Running' ? 
                                `<form action="/cancel_scan_job/${job.id}" method="post">
                                    <input type="hidden" name="csrf_token" value="${csrfToken}">
                                    <button type="submit" class="btn btn-warning btn-sm">Cancel Scan</button>
                                </form>` : ''}
                        </td>
                    `;
                    jobsTableBody.appendChild(row);
                });
            })
            .catch(error => console.error('Error fetching scan jobs status:', error));
    };

    const updateUnmatchedFolders = () => {
        fetch('/api/unmatched_folders', {cache: 'no-store'})
            .then(response => response.json())
            .then(data => {
                const unmatchedTableBody = document.querySelector('#unmatchedFoldersTableBody');
                unmatchedTableBody.innerHTML = '';
                data.forEach(folder => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${folder.folder_path}</td>
                        <td>${folder.status}</td>
                        <td>${folder.library_name}</td>
                        <td>${folder.platform_name}</td>
                        <td>${folder.platform_id || 'N/A'}</td>
                        <td>
                            <form method="post" action="/update_unmatched_folder_status" data-csrf="${csrfToken}" style="display: inline;">
                                <input type="hidden" name="csrf_token" value="${csrfToken}">
                                <input type="hidden" name="folder_id" value="${folder.id}">
                                <input type="hidden" name="new_status" value="Ignore">
                                <input type="submit" class="btn btn-secondary btn-sm" value="Ignore">
                            </form>
                            <form class="delete-folder-form" style="display: inline;">
                                <input type="hidden" name="csrf_token" value="${csrfToken}">
                                <input type="hidden" name="folder_path" value="${folder.folder_path}">
                                <button type="submit" class="btn btn-danger btn-sm">Delete Folder</button>
                            </form>
                            <form action="/add_game_manual" method="GET" style="display: inline;">
                                <input type="hidden" name="full_disk_path" value="${folder.folder_path}">
                                <input type="hidden" name="library_uuid" value="${folder.library_uuid}">
                                <input type="hidden" name="platform_name" value="${folder.platform_name}">
                                <input type="hidden" name="platform_id" value="${folder.platform_id}">
                                <input type="hidden" name="from_unmatched" value="true">
                                <input type="submit" class="btn btn-primary btn-sm" value="Identify">
                            </form>
                        </td>
                    `;
                    unmatchedTableBody.appendChild(row);
                });
                // Attach event listeners to the new forms
                attachDeleteFolderFormListeners();
            })
            .catch(error => console.error('Error fetching unmatched folders:', error));
    };

    // Run immediately on load
    updateScanJobs();
    updateUnmatchedFolders();

    // Then update every 5 seconds
    setInterval(updateScanJobs, 5000);
    setInterval(updateUnmatchedFolders, 5000);
});

function setupFolderBrowse(browseButtonId, folderContentsId, spinnerId, upButtonId, inputFieldId, currentPathVar) {
    $(browseButtonId).click(function() {
        window[currentPathVar] = ''; // Reset the current path
        $(upButtonId).hide(); // Initially hide the "Up" button
        fetchFolders('', folderContentsId, spinnerId, upButtonId, inputFieldId, currentPathVar);
    });

    $(upButtonId).click(function() {
        var segments = window[currentPathVar].split('/').filter(Boolean);
        if (segments.length > 0) {
            segments.pop();
            window[currentPathVar] = segments.join('/') + '/';
        } else {
            window[currentPathVar] = ''; // Reset to root if no segments left
        }

        fetchFolders(window[currentPathVar], folderContentsId, spinnerId, upButtonId, inputFieldId, currentPathVar);

        // Update the input field with the new current path
        $(inputFieldId).val(window[currentPathVar]);

        if (segments.length < 1) {
            $(upButtonId).hide();
        } else {
            $(upButtonId).show();
        }
    });
}

function fetchFolders(path, folderContentsId, spinnerId, upButtonId, inputFieldId, currentPathVar) {
    console.log("Fetching folders for path:", path);
    $(spinnerId).show();
    $.ajax({
        url: '/browse_folders_ss',
        data: { path: path },
        success: function(data) {
            $(spinnerId).hide();
            $(folderContentsId).empty();
            data.forEach(function(item) {
                var itemElement = $('<div>').text(item.name);
                if (item.isDir) {
                    var fullPath = path + item.name + "/";
                    $(itemElement).addClass('folder-item').attr('data-path', fullPath);
                    $(folderContentsId).append(itemElement);
                }
            });
            $('.folder-item').click(function() {
                var newPath = $(this).data('path');
                window[currentPathVar] = newPath; 
                fetchFolders(newPath, folderContentsId, spinnerId, upButtonId, inputFieldId, currentPathVar);
                $(inputFieldId).val(newPath); 
            });
            if (path) {
                $(upButtonId).show();
            } else {
                $(upButtonId).hide();
            }
        },
        error: function(error) {
            $(spinnerId).hide();
            console.error("Error fetching folders:", error);
        }
    });
}
