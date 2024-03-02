
document.addEventListener('DOMContentLoaded', function() {
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


