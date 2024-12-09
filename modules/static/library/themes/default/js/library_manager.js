document.addEventListener('DOMContentLoaded', function() {
    // Initialize Sortable
    var librariesTableBody = document.querySelector('#librariesTable tbody');
    if (librariesTableBody) {
        new Sortable(librariesTableBody, {
            handle: '.drag-handle',
            animation: 150,
            onEnd: function(evt) {
                var newOrder = Array.from(librariesTableBody.querySelectorAll('tr')).map(row => row.dataset.libraryUuid);
                
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
                        console.log('Library order updated successfully');
                    } else {
                        console.error('Failed to update library order');
                    }
                })
                .catch(error => {
                    console.error('Error updating library order:', error);
                });
            }
        });
    }

    var confirmDeleteButton = document.getElementById('confirmDeleteButton');
    var deleteForm = document.createElement('form');
    deleteForm.method = 'post';
    deleteForm.style.display = 'none';
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
                deleteForm.submit();
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
                deleteForm.submit();
            };
        });
    }
});
