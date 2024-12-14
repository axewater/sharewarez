document.addEventListener('DOMContentLoaded', function() {
    // Initialize Sortable on the libraries table
    var tbody = document.querySelector('#librariesTable tbody');
    if (tbody) {
        new Sortable(tbody, {
            handle: '.drag-handle',
            animation: 150,
            onEnd: function(evt) {
                // Collect new order of libraries
                var rows = tbody.getElementsByTagName('tr');
                var newOrder = Array.from(rows).map(row => row.dataset.libraryUuid);
                
                // Send new order to server
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
                    if (data.status !== 'success') {
                        console.error('Error saving library order');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                });
            }
        });
    }

    // Existing delete confirmation code
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
