import { fileIcons } from './config/file_type_icons.js';

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
                const csrfToken = CSRFUtils.getToken();

                console.log("Attempting to delete folder with path:", folderPath);

                fetch('/delete_folder', {
                    method: 'POST',
                    headers: CSRFUtils.getHeaders({ 'Content-Type': 'application/json' }),
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

    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    })

    // Simple table references - no DataTables initialization needed
    const scanJobsTableBody = document.getElementById('jobsTableBody');
    const unmatchedTableBody = document.getElementById('unmatchedFoldersTableBody');

    const urlParams = new URLSearchParams(window.location.search);
    const activeTab = urlParams.get('active_tab') || document.querySelector('meta[name="active-tab"]').getAttribute('content');
    console.log("Active tab determined:", activeTab);

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

    // Prevent form submission on pressing Enter and trigger Browse Folders click (Auto Scan Tab)
    const autoScanForm = document.querySelector('#autoScan form');
    if (autoScanForm) {
        autoScanForm.addEventListener('keydown', function(event) {
            // Only prevent default and trigger browse folders on Enter key press
            if (event.key === 'Enter') {
                event.preventDefault();
                const browseFoldersBtn = document.querySelector('#browseFoldersBtn');
                if (browseFoldersBtn) {
                    browseFoldersBtn.click();
                }
            }
        });
    }

    // Same for manual scan form
    const manualScanForm = document.querySelector('#manualScan form');
    if (manualScanForm) {
        manualScanForm.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                const browseFoldersBtnManual = document.querySelector('#browseFoldersBtnManual');
                if (browseFoldersBtnManual) {
                    browseFoldersBtnManual.click();
                }
            }
        });
    }

    setupFolderBrowse('#browseFoldersBtn', '#folderContents', '#loadingSpinner', '#upFolderBtn', '#folder_path', 'currentPathAuto');
    setupFolderBrowse('#browseFoldersBtnManual', '#folderContentsManual', '#loadingSpinnerManual', '#upFolderBtnManual', '#manualFolderPath', 'currentPathManual');

    // No complex toggle functionality needed for simplified table

    var csrfToken = CSRFUtils.getToken();

    // Helper function to get user-friendly status display
    function getDisplayStatus(job) {
        if (job.status === 'Failed' && job.error_message) {
            if (job.error_message === 'Scan cancelled by user') {
                return 'Cancelled';
            } else if (job.error_message === 'Scan job interrupted by server restart') {
                return 'Interrupted by server restart';
            }
        }
        return job.status;
    }

    const updateScanJobs = () => {
        fetch('/api/scan_jobs_status', {cache: 'no-store'})
            .then(response => response.json())
            .then(data => {
                // Sort the data array to ensure the latest scan is at the top
                data.sort((a, b) => new Date(b.last_run) - new Date(a.last_run));
                
                // Clear the table body
                scanJobsTableBody.innerHTML = '';
                
                const isAnyJobRunning = data.some(j => j.status === 'Running');
                
                data.forEach(job => {
                    // Create progress column content
                    let progressColumn = '';
                    if (job.status === 'Running' && job.total_folders > 0) {
                        const percentage = job.progress_percentage || 0;
                        const processed = job.folders_success + job.folders_failed;
                        progressColumn = `
                            <div class="scan-progress">
                                <div class="progress mb-1" style="height: 20px;">
                                    <div class="progress-bar" style="width: ${percentage}%"></div>
                                </div>
                                <div class="progress-info">
                                    <span class="progress-numbers">${processed}/${job.total_folders} (${percentage}%)</span>
                                </div>
                                <div class="progress-status">
                                    <small class="text-bright-green">${job.current_processing || 'Processing...'}</small>
                                </div>
                            </div>
                        `;
                    } else if (job.status === 'Completed') {
                        progressColumn = `<span class="text-success"><i class="fas fa-check"></i> ${job.folders_success + job.folders_failed}/${job.total_folders}</span>`;
                    } else if (job.status === 'Failed') {
                        progressColumn = `<span class="text-danger"><i class="fas fa-times"></i> ${job.folders_success + job.folders_failed}/${job.total_folders}</span>`;
                    } else {
                        progressColumn = '-';
                    }

                    // Create actions column content
                    const actionsColumn = `
                        ${job.status === 'Running' ? 
                            `<form action="/cancel_scan_job/${job.id}" method="post" style="display: inline-block;">
                                <input type="hidden" name="csrf_token" value="${csrfToken}">
                                <button type="submit" class="btn btn-warning btn-sm" title="Cancel Scan"><i class="fas fa-stop"></i></button>
                            </form>` : 
                            `${isAnyJobRunning ? 
                                `<button class="btn btn-info btn-sm" disabled title="Cannot restart while another scan is running"><i class="fas fa-sync"></i></button>` :
                                `<form action="/restart_scan_job/${job.id}" method="post" style="display: inline-block;">
                                    <input type="hidden" name="csrf_token" value="${csrfToken}">
                                    <button type="submit" class="btn btn-info btn-sm" title="Restart Scan"><i class="fas fa-sync"></i></button>
                                </form>`
                            }`
                        }
                    `;
                    
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${job.id.substring(0, 8)}</td>
                        <td>${job.library_name || 'N/A'}</td>
                        <td>${job.scan_folder || 'N/A'}</td>
                        <td>${getDisplayStatus(job)}</td>
                        <td>${progressColumn}</td>
                        <td>${actionsColumn}</td>
                    `;
                    scanJobsTableBody.appendChild(row);
                });
            })
            .catch(error => console.error('Error fetching scan jobs status:', error));
    };

    const updateUnmatchedFolders = () => {
        showSpinner();
        return fetch('/api/unmatched_folders', {cache: 'no-store'})
            .then(response => response.json())
            .then(data => {
                // Clear the table body
                unmatchedTableBody.innerHTML = '';
                
                data.forEach(folder => {
                    const actionsColumn = `
                        <button 
                            onclick="window.toggleIgnoreStatus('${folder.id}', this)" 
                            class="btn ${folder.status === 'Ignore' ? 'btn-warning' : 'btn-secondary'} btn-sm"
                            title="Ignored folders are not scanned">
                            <i class="fas ${folder.status === 'Ignore' ? 'fa-eye-slash' : 'fa-eye'}"></i>
                        </button>
                        <button onclick="clearEntry('${folder.id}')" class="btn btn-info btn-sm" title="Remove from unmatched list"><i class="fas fa-eraser"></i></button>
                        <form class="delete-folder-form" style="display: inline;">
                            <input type="hidden" name="csrf_token" value="${csrfToken}">
                            <input type="hidden" name="folder_path" value="${folder.folder_path}">
                            <button type="submit" class="btn btn-danger btn-sm" title="Delete the folder from disk"><i class="fas fa-trash-alt"></i></button>
                        </form>
                        <form action="/add_game_manual" method="GET" style="display: inline;">
                            <input type="hidden" name="full_disk_path" value="${folder.folder_path}">
                            <input type="hidden" name="library_uuid" value="${folder.library_uuid}">
                            <input type="hidden" name="platform_name" value="${folder.platform_name}">
                            <input type="hidden" name="platform_id" value="${folder.platform_id}">
                            <input type="hidden" name="from_unmatched" value="true">
                            <button type="submit" class="btn btn-primary btn-sm" title="Attempt manual IGDB search"><i class="fas fa-search"></i></button>
                        </form>
                    `;
                    
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td><i class="fas fa-folder"></i> ${folder.folder_path}</td>
                        <td>${folder.status}</td>
                        <td>${folder.library_name}</td>
                        <td>${folder.platform_name}</td>
                        <td>${actionsColumn}</td>
                    `;
                    unmatchedTableBody.appendChild(row);
                });
                // Attach event listeners to the new forms
                attachDeleteFolderFormListeners();
            })
            .catch(error => {
                console.error('Error fetching unmatched folders:', error);
            })
            .finally(() => {
                hideSpinner();
            });
    };

    // Run immediately on load
    updateScanJobs();
    updateUnmatchedFolders();

    // Set up periodic updates
    setInterval(updateScanJobs, 3000);  // Update every 3 seconds
    setInterval(updateUnmatchedFolders, 30000);  // Update every 30 seconds

    // Global functions for table interactions
    window.toggleIgnoreStatus = function(folderId, button) {
        fetch(`/toggle_ignore_status/${folderId}`, {
            method: 'POST',
            headers: CSRFUtils.getHeaders({ 'Content-Type': 'application/json' })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                updateUnmatchedFolders();
            }
        })
        .catch(error => console.error('Error toggling ignore status:', error));
    };

    window.clearEntry = function(folderId) {
        if (confirm('Remove this entry from the unmatched list?')) {
            fetch(`/clear_unmatched_entry/${folderId}`, {
                method: 'POST',
                headers: CSRFUtils.getHeaders({ 'Content-Type': 'application/json' })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    updateUnmatchedFolders();
                }
            })
            .catch(error => console.error('Error clearing entry:', error));
        }
    };
});

// Folder browse setup function
function setupFolderBrowse(browseButtonId, folderContentsId, spinnerId, upButtonId, inputFieldId, currentPathVar) {
    // Store the initial library selection
    var initialLibrarySelection = $(inputFieldId).closest('form').find('select[name="library_uuid"]').val();
    
    $(browseButtonId).click(function() {
        window[currentPathVar] = ''; // Reset the current path
        $(upButtonId).hide(); // Initially hide the "Up" button
        // Preserve the library selection
        var librarySelect = $(inputFieldId).closest('form').find('select[name="library_uuid"]');
        if (!librarySelect.val() && initialLibrarySelection) {
            librarySelect.val(initialLibrarySelection);
        }
        fetchFolders('', folderContentsId, spinnerId, upButtonId, inputFieldId, currentPathVar);
    });

    $(upButtonId).click(function() {
        var segments = window[currentPathVar].split('/').filter(Boolean);
        if (segments.length > 0) {
            // Remove the last segment to go up one level
            segments.pop();
            if (segments.length > 0) {
                window[currentPathVar] = segments.join('/') + '/';
            } else {
                window[currentPathVar] = ''; // Reset to base directory if no segments left
            }
        } else {
            window[currentPathVar] = ''; // Already at base directory
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
        url: '/api/browse_folders_ss',
        data: { path: path },
        success: function(data) {
            $(spinnerId).hide();
            $(folderContentsId).empty();
            
            // Check if we're using the new response format or the old one
            const items = data.items || data;
            
            // Display warning if there were errors
            if (data.hasErrors) {
                $(folderContentsId).append(
                    $('<div class="alert alert-warning">').html(
                        `<i class="fas fa-exclamation-triangle"></i> Some items (${data.skippedItems}) could not be accessed and were skipped.`
                    )
                );
            }
            
            items.forEach(function(item) {
                var itemElement;
                if (item.isDir) {
                    itemElement = $('<div>').html('<i class="fas fa-folder text-warning"></i> ' + item.name);
                    var fullPath = path + item.name + "/";
                    $(itemElement).addClass('folder-item').attr('data-path', fullPath);
                } else {
                    // Get file extension and appropriate icon
                    var ext = item.ext ? item.ext.toLowerCase() : '';
                    var iconClass = fileIcons[ext] || fileIcons['default'];
                    
                    // Format file size
                    var sizeText = formatFileSize(item.size);
                    
                    // Create file element with icon, name, and size
                    itemElement = $('<div>').html(
                        '<i class="fas ' + iconClass + '"></i> ' + 
                        item.name + 
                        '<span class="file-size">(' + sizeText + ')</span>'
                    );
                    $(itemElement)
                        .addClass('file-item')
                        .attr('title', item.name + ' - ' + sizeText)
                        .css('cursor', 'default');
                }
                $(folderContentsId).append(itemElement);
            });

            // Only attach click handlers to folders
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

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const kilobyte = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(kilobyte));
    return parseFloat((bytes / Math.pow(kilobyte, i)).toFixed(2)) + ' ' + sizes[i];
}