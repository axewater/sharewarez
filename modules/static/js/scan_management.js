var currentPathAuto = '';
var currentPathManual = '';
function showSpinner() {
    document.getElementById('globalSpinner').style.display = 'block';
}

function hideSpinner() {
    document.getElementById('globalSpinner').style.display = 'none';
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




    document.querySelectorAll('.delete-folder-form').forEach(form => {
        form.addEventListener('submit', function(event) {
            event.preventDefault();
            showSpinner();
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

            const folderPath = form.querySelector('[name="folder_path"]').value; // Ensure this matches your form structure
            console.log("Attempting to delete folder with path:", folderPath); // Debugging log
            
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
                console.log("Server response:", data); // Log the server response
                
                if(data.status === 'success') {
                    console.log("Deletion successful, removing row.");
                    form.closest('tr').remove();
                } else {
                    console.log("Deletion not successful:", data.message); // Log failure message
                    // If you want to remove the row even when the folder doesn't exist, adjust logic here
                    if (data.message === "The specified path does not exist or is not a folder. Entry removed if it was in the database.") {
                        console.log("Folder does not exist, removing row.");
                        form.closest('tr').remove(); // This line assumes your condition for removing the row matches this message
                    }
                }
                alert(data.message); // Show message to user
            })
            .catch(error => {
                console.error('Fetch error:', error); // Log any fetch error
            })
            .finally(() => {
                hideSpinner(); // Ensure spinner is always hidden after operation
            });
        });
    });
});





document.addEventListener('DOMContentLoaded', function() {
    setupFolderBrowse('#browseFoldersBtn', '#folderContents', '#loadingSpinner', '#upFolderBtn', '#folder_path', 'currentPathAuto');
    setupFolderBrowse('#browseFoldersBtnManual', '#folderContentsManual', '#loadingSpinnerManual', '#upFolderBtnManual', '#manualFolderPath', 'currentPathManual');
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
