document.addEventListener('DOMContentLoaded', function() {
    
    const igdbIdInput = document.querySelector('#igdb_id');
    const fullPathInput = document.querySelector('#full_disk_path');
    const nameInput = document.querySelector('#name');
    const urlInput = document.querySelector('#url');
    const submitButton = document.querySelector('button[type="submit"]');
    const igdbIdFeedback = document.querySelector('#igdb_id_feedback');
    const fullPathFeedback = document.createElement('small');
    fullPathFeedback.id = 'full_disk_path_feedback';
    fullPathInput.parentNode.insertBefore(fullPathFeedback, fullPathInput.nextSibling);

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

        updateButtonState(!(igdbIdIsValid && fullPathIsValid && nameIsValid));
    }

    function showFeedback(element, message, isSuccess) {
        element.textContent = message;
        element.className = isSuccess ? 'form-text text-success' : 'form-text text-danger';
    }
    function triggerClickOnEnter(event, button) {
        if (event.keyCode === 13) {
            event.preventDefault();
            button.click();
        }
    }
    
    igdbIdInput.addEventListener('keypress', function(event) {
        triggerClickOnEnter(event, document.querySelector('#search-igdb-btn'));
    });

    
    nameInput.addEventListener('keypress', function(event) {
        triggerClickOnEnter(event, document.querySelector('#search-igdb'));
    });

    document.querySelector('#search-igdb-btn').addEventListener('click', function() {
        const igdbId = igdbIdInput.value;
        if (igdbId) {
            fetch(`/search_igdb_by_id?igdb_id=${igdbId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error:', data.error);
                    } else {
                        
                        nameInput.value = data.name;
                        document.querySelector('#summary').value = data.summary;
                        document.querySelector('#storyline').value = data.storyline || '';
                        urlInput.value = data.url || '';
    
                        const statusSelect = document.querySelector('#status');
                        if (statusSelect) {
                            statusSelect.value = data.status || '';
                        }
    
                        const categorySelect = document.querySelector('#category');
                        if (categorySelect) {
                            categorySelect.value = data.category || '';
                        }
    
                        const genresOptions = document.querySelectorAll('#genres option');
                        genresOptions.forEach(option => {
                            if (data.genres && data.genres.includes(option.text)) {
                                option.selected = true;
                            }
                        });
    
                        
                        checkFieldsAndToggleSubmit();
                    }
                })
                .catch(error => console.error('Error:', error));
        }
    });
    

        document.querySelector('#search-igdb').addEventListener('click', function() {
        const gameName = nameInput.value;
        console.log(`Initiating IGDB search for name: ${gameName}`);
        if (gameName) {
            fetch(`/search_igdb_by_name?name=${encodeURIComponent(gameName)}`)
                .then(response => response.json())
                .then(data => {
                    console.log("API Response (IGDB Search):", data);
                    const resultsContainer = document.querySelector('#search-results');
                    resultsContainer.innerHTML = ''; 

                    if (data.results && data.results.length > 0) {
                        data.results.forEach(game => {
                            const resultItem = document.createElement('div');
                            resultItem.className = 'search-result-item';
                            resultItem.textContent = game.name;
                            resultItem.addEventListener('click', function() {
                                igdbIdInput.value = game.id;
                                nameInput.value = game.name;
                                document.querySelector('#summary').value = game.summary || '';
                                document.querySelector('#storyline').value = game.storyline || '';
                                document.querySelector('#url').value = game.url || '';
                                urlInput.value = game.url || '';
                                checkFieldsAndToggleSubmit();
                                resultsContainer.innerHTML = '';
                            });
                            resultsContainer.appendChild(resultItem);
                        });
                    } else {
                        resultsContainer.textContent = 'No results found';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                });
        }
    });

    igdbIdInput.addEventListener('input', function() {
        this.value = this.value.replace(/\D/g, '');
        checkFieldsAndToggleSubmit();
    });

    fullPathInput.addEventListener('input', checkFieldsAndToggleSubmit);
    nameInput.addEventListener('input', checkFieldsAndToggleSubmit);

    igdbIdInput.addEventListener('blur', function() {
        igdbIdInput.addEventListener('blur', function() {
            const igdbId = this.value.trim();
            if (igdbId.length > 0) {
                fetch(`/check_igdb_id?igdb_id=${igdbId}`)
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
        
    });

    fullPathInput.addEventListener('blur', function() {
        fullPathInput.addEventListener('blur', function() {
            const fullPath = this.value;
            if (fullPath.trim().length > 0) {
                fetch(`/check_path_availability?full_disk_path=${encodeURIComponent(fullPath)}`)
                    .then(response => response.json())
                    .then(data => {
                        const isValid = data.available;
                        showFeedback(fullPathFeedback, isValid ? 'Path is accessible' : 'Path is not accessible', isValid);
                        validateField(this, isValid);
                        checkFieldsAndToggleSubmit();
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        showFeedback(fullPathFeedback, 'Error checking path accessibility', false);
                    });
            }
        });
        
    });

    checkFieldsAndToggleSubmit();
    console.log("Ready to add a game!.");
});
