document.addEventListener('DOMContentLoaded', function() {
    const igdbIdInput = document.querySelector('#igdb_id');
    const igdbIdFeedback = document.querySelector('#igdb_id_feedback');
    const fullPathInput = document.querySelector('#full_disk_path');
    const submitButton = document.querySelector('button[type="submit"]');
    const fullPathFeedback = document.createElement('small');
    fullPathFeedback.id = 'full_disk_path_feedback';
    fullPathInput.parentNode.appendChild(fullPathFeedback);

    $(submitButton).tooltip({
        title: "Incomplete entry",
        placement: "top",
        trigger: "hover"
    });

    function updateButtonState(isDisabled) {
        submitButton.disabled = isDisabled;
        if (isDisabled) {
            $(submitButton).tooltip('enable');
        } else {
            $(submitButton).tooltip('disable');
        }
    }

    updateButtonState(true);

    igdbIdInput.addEventListener('blur', function() {
        const igdbId = this.value;
        if (igdbId) {
            fetch(`/check_igdb_id?igdb_id=${igdbId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.available) {
                        igdbIdFeedback.textContent = 'Available';
                        igdbIdFeedback.className = 'form-text text-success';
                    } else {
                        igdbIdFeedback.textContent = 'Already in database';
                        igdbIdFeedback.className = 'form-text text-danger';
                    }
                })
                .catch(error => console.error('Error:', error));
        }
    });

    fullPathInput.addEventListener('blur', function() {
        const fullPath = this.value;
        if (fullPath) {
            fetch(`/check_path_availability?full_disk_path=${encodeURIComponent(fullPath)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.available) {
                        fullPathFeedback.textContent = 'Path is available';
                        fullPathFeedback.className = 'form-text text-success';
                        updateButtonState(false); 
                    } else {
                        fullPathFeedback.textContent = 'Path is not available';
                        fullPathFeedback.className = 'form-text text-danger';
                        updateButtonState(true); 
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    updateButtonState(true); 
                });
        } else {
            fullPathFeedback.textContent = 'Please enter a path.';
            fullPathFeedback.className = 'form-text text-warning';
            updateButtonState(true); 
        }
    });
    igdbIdInput.addEventListener('input', function() {
        this.value = this.value.replace(/\D/g, ''); // Remove non-digits
    });
    document.querySelector('form').addEventListener('submit', function(e) {
        // Check if any mandatory fields are invalid
        const invalidInputs = document.querySelectorAll('.invalid-input');
        if (invalidInputs.length > 0) {
            e.preventDefault(); // Prevent form submission
            invalidInputs[0].scrollIntoView({ behavior: 'smooth', block: 'center' }); // Scroll to the first invalid input
            // Optionally, show a message to the user indicating that some fields need attention
        }
    });
    
    // Move the search button event listener inside the DOMContentLoaded listener
    document.querySelector('#search-igdb-btn').addEventListener('click', function() {
        const igdbId = igdbIdInput.value;
        if (igdbId) {
            fetch(`/search_igdb_by_id?igdb_id=${igdbId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error:', data.error);
                    } else {
                        document.querySelector('#name').value = data.name;
                        document.querySelector('#summary').value = data.summary;
                        // Continue populating other fields accordingly
                    }
                })
                .catch(error => console.error('Error:', error));
        }
    });
});
