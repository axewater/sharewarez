document.addEventListener('DOMContentLoaded', function() {
    const igdbIdInput = document.querySelector('#igdb_id');
    const fullPathInput = document.querySelector('#full_disk_path');
    const nameInput = document.querySelector('#name');
    const submitButton = document.querySelector('button[type="submit"]');
    const igdbIdFeedback = document.querySelector('#igdb_id_feedback');
    const fullPathFeedback = document.createElement('small');
    fullPathFeedback.id = 'full_disk_path_feedback';
    fullPathInput.parentNode.insertBefore(fullPathFeedback, fullPathInput.nextSibling);

    // Tooltip initialization for the submit button
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

    function validateField(inputElement, isValid) {
        if (isValid) {
            inputElement.classList.remove('invalid-input');
        } else {
            inputElement.classList.add('invalid-input');
        }
    }

    function checkFieldsAndToggleSubmit() {
        const igdbIdIsValid = igdbIdInput.value.trim().length > 0 && /^\d+$/.test(igdbIdInput.value);
        const fullPathIsValid = fullPathInput.value.trim().length > 0;
        const nameIsValid = nameInput.value.trim().length > 0;

        validateField(igdbIdInput, igdbIdIsValid);
        validateField(fullPathInput, fullPathIsValid);
        validateField(nameInput, nameIsValid);

        // Enable the submit button only if all validations pass
        updateButtonState(!(igdbIdIsValid && fullPathIsValid && nameIsValid));
    }

    igdbIdInput.addEventListener('input', function() {
        this.value = this.value.replace(/\D/g, ''); // Remove non-digits
        checkFieldsAndToggleSubmit();
    });

    fullPathInput.addEventListener('input', checkFieldsAndToggleSubmit);
    nameInput.addEventListener('input', checkFieldsAndToggleSubmit);

    function showFeedback(element, message, isSuccess) {
        element.textContent = message;
        element.className = isSuccess ? 'form-text text-success' : 'form-text text-danger';
    }

    igdbIdInput.addEventListener('blur', function() {
        if (this.value.trim().length > 0) {
            fetch(`/check_igdb_id?igdb_id=${this.value}`)
                .then(response => response.json())
                .then(data => {
                    const isValid = data.available;
                    showFeedback(igdbIdFeedback, isValid ? 'IGDB ID is available' : 'IGDB ID is already in the database', isValid);
                    validateField(this, isValid);
                    checkFieldsAndToggleSubmit();
                })
                .catch(error => {
                    console.error('Error:', error);
                    showFeedback(igdbIdFeedback, 'Error checking IGDB ID', false);
                });
        }
    });

    fullPathInput.addEventListener('blur', function() {
        const fullPath = this.value;
        if (fullPath.trim().length > 0) {
            fetch(`/check_path_availability?full_disk_path=${encodeURIComponent(fullPath)}`)
                .then(response => response.json())
                .then(data => {
                    const isValid = data.available;
                    showFeedback(fullPathFeedback, isValid ? 'Path is available' : 'Path is not available', isValid);
                    validateField(this, isValid);
                    checkFieldsAndToggleSubmit();
                })
                .catch(error => {
                    console.error('Error:', error);
                    showFeedback(fullPathFeedback, 'Error checking path availability', false);
                });
        }
    });

    // Assuming there's a button with ID 'search-igdb-btn' for IGDB search functionality
    document.querySelector('#search-igdb-btn').addEventListener('click', function() {
        const igdbId = igdbIdInput.value;
        if (igdbId) {
            fetch(`/search_igdb_by_id?igdb_id=${igdbId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error:', data.error);
                    } else {
                        // Populate form fields with the response data
                        nameInput.value = data.name || '';
                        document.querySelector('#summary').value = data.summary || '';
                        // Continue populating other fields as needed
                        checkFieldsAndToggleSubmit(); // Re-validate the form
                    }
                })
                .catch(error => console.error('Error:', error));
        }
    });
    document.querySelector('#search-igdb').addEventListener('click', function() {
        const gameName = document.querySelector('#name').value;
        if (gameName) {
            fetch(`/search_igdb_by_name?name=${encodeURIComponent(gameName)}`)
                .then(response => response.json())
                .then(data => {
                    const resultsContainer = document.querySelector('#search-results');
                    resultsContainer.innerHTML = ''; // Clear previous results
                    if (data.results && data.results.length > 0) {
                        data.results.forEach(game => {
                            const resultItem = document.createElement('div');
                            resultItem.className = 'search-result-item';
                            resultItem.textContent = game.name; // Customize display as needed
                            resultItem.addEventListener('click', function() {
                                // Fill form fields with selected game's data
                                document.querySelector('#igdb_id').value = game.id;
                                document.querySelector('#name').value = game.name;
                                // Add other fields as necessary
                            });
                            resultsContainer.appendChild(resultItem);
                        });
                    } else {
                        resultsContainer.textContent = 'No results found';
                    }
                })
                .catch(error => console.error('Error:', error));
        }
    });
    
    // Initialize form validation and feedback for existing functionality
    checkFieldsAndToggleSubmit();
});
