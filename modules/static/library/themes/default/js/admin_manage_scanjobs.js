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

    // Initialize DataTables with column visibility control
    const scanJobsTable = $('#scanJobsTable').DataTable({
        pageLength: 10,
        lengthMenu: [[5, 10, 25, 50], [5, 10, 25, 50]],
        order: [[10, 'desc']], // Sort by Last Run column (moved to index 10)
        scrollY: false, // Disabled since we're using CSS max-height
        scrollX: true,
        autoWidth: false,
        columnDefs: [
            { targets: [8], orderable: false }, // Disable sorting on Actions column
            { targets: [4], orderable: false }, // Disable sorting on Progress column
            { targets: [9,10,11,12,13], visible: false }, // Hide detail columns by default
            { targets: '_all', searchable: true },
            // Column width specifications
            { targets: 0, width: '80px' }, // Job ID
            { targets: 1, width: '120px' }, // Library
            { targets: 3, width: '100px' }, // Status
            { targets: [5,6,7], width: '80px' }, // Numeric columns
            { targets: 8, width: '120px' } // Actions
        ],
        dom: '<"top"lf>rt<"bottom"ip><"clear">',
        language: {
            search: "Search:",
            lengthMenu: "Show _MENU_ entries",
            info: "Showing _START_ to _END_ of _TOTAL_ scan jobs",
            infoEmpty: "No scan jobs found",
            emptyTable: "No scan jobs available"
        },
        responsive: {
            breakpoints: {
                tablet: 768,
                phone: 576
            }
        }
    });

    const unmatchedTable = $('#unmatchedTable').DataTable({
        pageLength: 25,
        order: [[1, 'desc']], // Sort by Status column by default
        columnDefs: [
            { targets: [4], orderable: false }, // Disable sorting on Actions column
            { targets: '_all', searchable: true }
        ],
        dom: '<"top"lf>rt<"bottom"ip><"clear">',
        language: {
            search: "Search:",
            lengthMenu: "Show _MENU_ entries"
        }
    });

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

    // Setup toggle functionality for detailed columns
    let detailColumnsVisible = localStorage.getItem('scanJobsDetailsVisible') === 'true';
    let compactMode = localStorage.getItem('scanJobsCompactMode') === 'true';
    const detailColumnIndices = [9, 10, 11, 12, 13]; // Updated indices after Job ID moved to first position
    
    function updateToggleButton() {
        const btn = document.getElementById('toggleDetailsBtn');
        const icon = btn.querySelector('i');
        
        if (detailColumnsVisible) {
            icon.className = 'fas fa-eye-slash';
            btn.innerHTML = '<i class="fas fa-eye-slash"></i> Hide Details';
        } else {
            icon.className = 'fas fa-eye';
            btn.innerHTML = '<i class="fas fa-eye"></i> Show Details';
        }
    }
    
    function updateCompactButton() {
        const btn = document.getElementById('toggleCompactBtn');
        const icon = btn.querySelector('i');
        
        if (compactMode) {
            icon.className = 'fas fa-expand';
            btn.innerHTML = '<i class="fas fa-expand"></i> Normal';
            btn.classList.remove('btn-outline-info');
            btn.classList.add('btn-info');
        } else {
            icon.className = 'fas fa-compress';
            btn.innerHTML = '<i class="fas fa-compress"></i> Compact';
            btn.classList.remove('btn-info');
            btn.classList.add('btn-outline-info');
        }
    }
    
    function toggleDetailColumns() {
        detailColumnsVisible = !detailColumnsVisible;
        localStorage.setItem('scanJobsDetailsVisible', detailColumnsVisible);
        
        // Toggle column visibility
        detailColumnIndices.forEach(columnIndex => {
            scanJobsTable.column(columnIndex).visible(detailColumnsVisible);
        });
        
        updateToggleButton();
    }
    
    function toggleCompactMode() {
        compactMode = !compactMode;
        localStorage.setItem('scanJobsCompactMode', compactMode);
        
        const table = document.getElementById('scanJobsTable');
        const container = document.querySelector('.scan-jobs-table-container');
        
        if (compactMode) {
            table.classList.add('scan-jobs-compact');
            container.style.maxHeight = '300px';
            // Change to 5 entries in compact mode
            scanJobsTable.page.len(5).draw();
        } else {
            table.classList.remove('scan-jobs-compact');
            container.style.maxHeight = '500px';
            // Back to 10 entries in normal mode
            scanJobsTable.page.len(10).draw();
        }
        
        updateCompactButton();
    }
    
    // Initialize button states
    updateToggleButton();
    updateCompactButton();
    
    // Set initial column visibility based on stored preference
    detailColumnIndices.forEach(columnIndex => {
        scanJobsTable.column(columnIndex).visible(detailColumnsVisible);
    });
    
    // Set initial compact mode
    if (compactMode) {
        const table = document.getElementById('scanJobsTable');
        const container = document.querySelector('.scan-jobs-table-container');
        table.classList.add('scan-jobs-compact');
        container.style.maxHeight = '300px';
        scanJobsTable.page.len(5).draw();
    }
    
    // Attach click handlers to toggle buttons
    document.getElementById('toggleDetailsBtn').addEventListener('click', toggleDetailColumns);
    document.getElementById('toggleCompactBtn').addEventListener('click', toggleCompactMode);

    var csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    const updateScanJobs = () => {
        fetch('/api/scan_jobs_status', {cache: 'no-store'})
            .then(response => response.json())
            .then(data => {
                // Sort the data array to ensure the latest scan is at the top
                data.sort((a, b) => new Date(b.last_run) - new Date(a.last_run));
                
                // Clear the table once before adding new data
                scanJobsTable.clear();
                
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
                                    <div class="progress-bar bg-primary" style="width: ${percentage}%">
                                        ${processed}/${job.total_folders}
                                    </div>
                                </div>
                                <small class="text-muted">${job.current_processing || 'Processing...'}</small>
                            </div>
                        `;
                    } else if (job.status === 'Completed') {
                        progressColumn = `<span class="text-success"><i class="fas fa-check"></i> ${job.folders_success + job.folders_failed}/${job.total_folders}</span>`;
                    } else if (job.status === 'Failed') {
                        progressColumn = `<span class="text-danger"><i class="fas fa-times"></i> ${job.folders_success + job.folders_failed}/${job.total_folders}</span>`;
                    } else {
                        progressColumn = '-';
                    }
                    
                    scanJobsTable.row.add([
                        job.id.substring(0, 8),  // Job ID - now first column
                        job.library_name || 'N/A',
                        job.scan_folder || 'N/A',
                        job.status,
                        progressColumn,
                        job.total_folders,
                        job.folders_success,
                        job.folders_failed,
                        `
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
                        `,
                        // Detail columns (hidden by default)
                        job.error_message,
                        formatTimestamp(job.last_run),
                        job.removed_count || 0,
                        job.setting_remove ? 'On' : 'Off',
                        job.setting_filefolder ? 'File' : 'Folder'
                    ]);
                });
                
                // Draw the table after all rows have been added
                scanJobsTable.draw();
            })
            .catch(error => console.error('Error fetching scan jobs status:', error));
    };

    const updateUnmatchedFolders = () => {
        return fetch('/api/unmatched_folders', {cache: 'no-store'})
            .then(response => response.json())
            .then(data => {
                const unmatchedTableBody = document.querySelector('#unmatchedFoldersTableBody');
                unmatchedTableBody.innerHTML = '';
                unmatchedTable.clear();
                data.forEach(folder => {
                    unmatchedTable.row.add([
                        `
                            <i class="fas fa-folder"></i> ${folder.folder_path}
                        `,
                        folder.status,
                        folder.library_name,
                        folder.platform_name,
                        `
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
                        `
                    ]).draw();
                });
                // Attach event listeners to the new forms
                attachDeleteFolderFormListeners();
            })
            .catch(error => console.error('Error fetching unmatched folders:', error));
    };

    // Run immediately on load
    updateScanJobs();
    
    // Only load unmatched folders when its tab is activated
    document.querySelector('#unmatchedFolders-tab').addEventListener('shown.bs.tab', function (e) {
        console.log("Unmatched folders tab activated");
        // Show loading spinner
        document.getElementById('globalSpinner').style.display = 'block';
        
        // Load the data
        updateUnmatchedFolders().then(() => {
            // Hide spinner when done
            document.getElementById('globalSpinner').style.display = 'none';
        });
    });

    // Then update every 5 seconds
    setInterval(updateScanJobs, 5000);
});

window.toggleIgnoreStatus = function(folderId, button) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
    fetch('/update_unmatched_folder_status', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': csrfToken
        },
        body: `folder_id=${folderId}&csrf_token=${csrfToken}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Update button icon and class based on new status
            const icon = button.querySelector('i') || document.createElement('i');
            icon.className = `fas ${data.new_status === 'Ignore' ? 'fa-eye-slash' : 'fa-eye'}`;
            if (!button.contains(icon)) {
                button.innerHTML = '';
                button.appendChild(icon);
            }
            button.classList.toggle('btn-warning', data.new_status === 'Ignore');
            button.classList.toggle('btn-secondary', data.new_status !== 'Ignore');
        } else {
            console.error('Error:', data.message);
            alert('Error updating status: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error updating status');
    });
}

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

function formatTimestamp(timestamp) {
    if (!timestamp) return 'N/A';
    
    try {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        // Format time as HH:MM
        const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        // If it's today, show "Today at HH:MM"
        if (diffDays === 0) {
            return `Today at ${timeStr}`;
        }
        // If it's yesterday, show "Yesterday at HH:MM"
        else if (diffDays === 1) {
            return `Yesterday at ${timeStr}`;
        }
        // If it's within the last week, show "X days ago at HH:MM"
        else if (diffDays < 7) {
            return `${diffDays} days ago at ${timeStr}`;
        }
        // For older dates, show the full date
        else {
            return date.toLocaleDateString() + ' at ' + timeStr;
        }
    } catch (error) {
        console.error('Error formatting timestamp:', timestamp, error);
        return timestamp; // Return original if formatting fails
    }
}

window.clearEntry = clearEntry;
function clearEntry(folderId) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    console.log("Clearing entry for folder ID:", folderId);
    if (!confirm('Are you sure you want to clear this entry? This will only remove the database entry.')) {
        return;
    }
    console.log("Confirmed, sending request.");
    fetch(`/clear_unmatched_entry/${folderId}`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': csrfToken
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Remove the row from the table
            console.log("Response success, removing row.");
            const row = document.querySelector(`tr[data-folder-id="${folderId}"]`);
            if (row) row.remove();
        } else {
            alert('Error clearing entry: ' + data.message);
        }
    })
    .catch(error => console.error('Error:', error));
}

// Auto-refresh scan jobs progress functionality
let progressUpdateInterval;

function startProgressTracking() {
    // Check for running scan jobs every 5 seconds
    progressUpdateInterval = setInterval(updateScanJobsProgress, 5000);
    console.log("Started scan jobs progress tracking");
}

function stopProgressTracking() {
    if (progressUpdateInterval) {
        clearInterval(progressUpdateInterval);
        progressUpdateInterval = null;
        console.log("Stopped scan jobs progress tracking");
    }
}

function updateScanJobsProgress() {
    fetch('/api/scan_jobs_status')
        .then(response => response.json())
        .then(data => {
            // Filter for running jobs only for progress tracking
            const runningJobs = data.filter(job => job.status === 'Running');
            updateProgressDisplay(runningJobs);
        })
        .catch(error => {
            console.error('Error fetching scan job progress:', error);
        });
}

function updateProgressDisplay(runningJobs) {
    const hasRunningJobs = runningJobs.length > 0;
    
    // Start/stop tracking based on whether there are running jobs
    if (hasRunningJobs && !progressUpdateInterval) {
        startProgressTracking();
    } else if (!hasRunningJobs && progressUpdateInterval) {
        stopProgressTracking();
    }
    
    // Update each running job's progress in the table
    runningJobs.forEach(job => {
        const jobRow = document.querySelector(`tr[data-job-id="${job.id}"]`);
        if (jobRow) {
            updateJobRowProgress(jobRow, job);
        }
    });
}

function updateJobRowProgress(jobRow, job) {
    // Find the progress column (5th column, index 4)
    const progressCell = jobRow.cells[4]; // Progress column
    
    if (progressCell) {
        const percentage = job.progress_percentage || 0;
        const processed = job.folders_success + job.folders_failed;
        const total = job.total_folders;
        
        progressCell.innerHTML = `
            <div class="scan-progress">
                <div class="progress mb-1" style="height: 20px;">
                    <div class="progress-bar ${percentage === 100 ? 'bg-success' : 'bg-primary'}" 
                         style="width: ${percentage}%">
                        ${processed}/${total}
                    </div>
                </div>
                <small class="text-muted">${job.current_processing || 'Processing...'}</small>
            </div>
        `;
    }
}

// Initialize progress tracking on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initial check for running jobs
    updateScanJobsProgress();
});

// Clean up interval when leaving the page
window.addEventListener('beforeunload', function() {
    stopProgressTracking();
});
