var currentPathAuto = '';
var currentPathManual = '';

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
                window[currentPathVar] = newPath; // Update the correct path variable
                fetchFolders(newPath, folderContentsId, spinnerId, upButtonId, inputFieldId, currentPathVar);
                $(inputFieldId).val(newPath); // Update the input field with the new path
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
