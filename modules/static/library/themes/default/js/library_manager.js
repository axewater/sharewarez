document.addEventListener('DOMContentLoaded', function() {
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
