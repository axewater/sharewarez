document.addEventListener('DOMContentLoaded', function() {
    // Initialize Sortable on the libraries table
    const tbody = document.querySelector('#librariesTable tbody');
    new Sortable(tbody, {
        handle: '.drag-handle',
        animation: 150,
        onEnd: function(evt) {
            const newOrder = Array.from(tbody.querySelectorAll('tr')).map(row => row.dataset.libraryUuid);
            
            // Send the new order to the server
            fetch('/api/reorder_libraries', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                },
                body: JSON.stringify({ order: newOrder })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    $.notify('Library order updated successfully', 'success');
                } else {
                    $.notify('Error updating library order', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                $.notify('Error updating library order', 'error');
            });
        }
    });

    // Existing delete functionality
    const spinner = document.getElementById('deleteSpinner');
    var confirmDeleteButton = document.getElementById('confirmDeleteButton');
    var deleteForm = document.createElement('form');
    deleteForm.method = 'post';
    deleteForm.style.display = 'none'; // Ensure the form isn't visible on the page.
    document.body.appendChild(deleteForm);
    var csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrf_token';
    csrfInput.value = document.querySelector('meta[name="csrf-token"]').getAttribute('content'); // Ensure CSRF token is pulled from a meta tag
    deleteForm.appendChild(csrfInput);

    var body = document.querySelector('body');
    var deleteAllUrl = body.getAttribute('data-delete-url');
    var baseDeleteUrl = document.body.getAttribute('data-base-delete-url');

    // Handle individual delete buttons
    document.querySelectorAll('.delete-btn').forEach(button => {
        button.addEventListener('click', function() {
            console.log('clicked delete button');
            var libraryUuid = this.getAttribute('data-library-uuid');
            document.querySelector('#deleteWarningModal .modal-body').textContent = 'Are you sure you want to delete this library? This action cannot be undone.';
            deleteForm.action = baseDeleteUrl + libraryUuid;
            confirmDeleteButton.textContent = 'Confirm Delete';

            // show modal
            var deleteWarningModal = new bootstrap.Modal(document.getElementById('deleteWarningModal'));
            deleteWarningModal.show();

            confirmDeleteButton.onclick = function() {
                // Hide the modal
                deleteWarningModal.hide();
                // Show the spinner
                spinner.style.display = 'flex';
                
                // Submit the form
                deleteForm.onsubmit = function() {
                    return true;
                };
                
                setTimeout(() => {
                    deleteForm.submit();
                }, 100);
            };
        });
    });

    // Handle delete all libraries button
    var deleteAllGamesBtn = document.getElementById('deleteAllGamesBtn');
    if (deleteAllGamesBtn) {
        deleteAllGamesBtn.addEventListener('click', function() {
            document.querySelector('#deleteWarningModal .modal-body').textContent = 'Are you sure you want to delete all libraries? This action cannot be undone.';
            deleteForm.action = deleteAllUrl;
            confirmDeleteButton.textContent = 'Confirm Delete All Libraries';

            var deleteWarningModal = new bootstrap.Modal(document.getElementById('deleteWarningModal'));
            deleteWarningModal.show();
            
            confirmDeleteButton.onclick = function() {
                // Hide the modal
                deleteWarningModal.hide();
                // Show the spinner
                spinner.style.display = 'flex';
                
                // Submit the form
                deleteForm.onsubmit = function() {
                    return true;
                };
                
                setTimeout(() => {
                    deleteForm.submit();
                }, 100);
            };
        });
    }
});
