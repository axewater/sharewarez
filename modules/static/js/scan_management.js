
var currentPath = '';

document.addEventListener('DOMContentLoaded', function() {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
    // Select all delete-folder forms
    document.querySelectorAll('.delete-folder-form').forEach(form => {
        form.addEventListener('submit', function(event) {
            event.preventDefault(); // Prevent default form submission
            
            const formData = new FormData(form);
            const folderPath = formData.get('folder_path');
            const csrfToken = formData.get('csrf_token'); // Adjust based on your CSRF token field name
            console.log("folderPath:", folderPath);
            // Perform the AJAX request
            fetch('{{ url_for("main.delete_folder") }}', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken // Ensure CSRF token is correctly included in request headers
                },
                body: JSON.stringify({folder_path: folderPath})
            }).then(response => response.json())
              .then(data => {
                  // Flash message to user
                  alert(data.message); // Simple alert, replace with your method of displaying messages
                  
                  // Optionally, remove the row or update the UI as needed
                  if(data.status === 'success') {
                      form.parentElement.parentElement.remove(); // Example: remove the table row
                  }
              }).catch(error => console.error('Error:', error));
        });
    });
});


$(document).ready(function() {
    $('#browseFoldersBtn').click(function() {
        currentPath = ''; // Assuming this represents the root directory
        $('#upFolderBtn').hide(); // Initially hide the "Up" button since we're at the start
        fetchFolders(currentPath);
    });
});

function fetchFolders(path) {
    console.log("Fetching folders for path:", path);
    currentPath = path;
    $('#loadingSpinner').show();
    $.ajax({
        url: '/browse_folders_ss',
        data: { path: path },
        success: function(data) {
            $('#loadingSpinner').hide();
            $('#folderContents').empty();
            data.forEach(function(item) {
                var itemElement = $('<div>').text(item.name);
                if (item.isDir) {
                    // Ensure the full path is set correctly
                    var fullPath = path + item.name + "/";
                    $(itemElement).addClass('folder-item').attr('data-path', fullPath);
                }
                $('#folderContents').append(itemElement);
            });
            $('.folder-item').click(function() {
                var newPath = $(this).data('path');
                fetchFolders(newPath);
                // Update the folder path input field with the selected path
                $('#folder_path').val(newPath); // Ensure this ID matches your input field's ID
            });
            if (path) { // If there's any path, we're not at the root
                $('#upFolderBtn').show();
            } else {
                $('#upFolderBtn').hide();
            }
            currentPath = path;
            $('.folder-item').click(function() {
                var newPath = $(this).data('path');
                fetchFolders(newPath);
                // Always show the "Up" button after selecting a folder, since we're no longer at root
                $('#upFolderBtn').show();
            });
        },
    
        error: function(error) {
            $('#loadingSpinner').hide();
            console.error("Error fetching folders:", error);
        }
    });
}
$('#upFolderBtn').click(function() {
    // Navigate up by removing the last segment in the current path
    var segments = currentPath.split('/').filter(Boolean); // Split and remove empty segments
    if (segments.length > 0) { // Check if we're not already at the root
        segments.pop(); // Remove the last segment
        currentPath = segments.join('/') + '/';
        fetchFolders(currentPath);
    } else {
        currentPath = ''; // Reset to root if no segments left
    }

    // Update the input field with the new current path
    $('#folder_path').val(currentPath); // Update the path in the input field

    // Adjust the visibility of the "Up" button based on whether we're at the root directory
    if (segments.length < 1) { // Hide if at root or just above it
        $('#upFolderBtn').hide();
    }
});
