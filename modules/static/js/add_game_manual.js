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

    function updateFormWithGameData(gameData) {
        // Update genres
        const genreCheckboxes = document.querySelectorAll('#genres-container .form-check-input');
        
        genreCheckboxes.forEach(checkbox => {
            
            const checkboxLabel = checkbox.nextElementSibling ? checkbox.nextElementSibling.textContent.trim().toLowerCase() : "";
            const isGenreMatched = gameData.genres.some(genre => genre.name.toLowerCase() === checkboxLabel);
            
            
            if (isGenreMatched) {
                checkbox.checked = true;
            } else {
                checkbox.checked = false;
            }
        });

        // Update game modes
        const gameModeCheckboxes = document.querySelectorAll('#gamemodes-container input[type="checkbox"]');
        console.log("Found game mode checkboxes: ", gameModeCheckboxes.length);
        
        gameModeCheckboxes.forEach((checkbox) => {
            // Assuming the next sibling of the checkbox is its label
            const checkboxLabel = checkbox.nextElementSibling ? checkbox.nextElementSibling.textContent.trim().toLowerCase() : "";
            console.log(`Checkbox label: "${checkboxLabel}"`);
        
            // Adjust the comparison logic as needed to account for any data discrepancies
            const isGameModeMatched = gameData.game_modes.some(mode => mode.name.toLowerCase() === checkboxLabel);
        
            console.log(`Is game mode matched? ${isGameModeMatched}`);
            checkbox.checked = isGameModeMatched;
        });
        



        // Update themes
        const themeCheckboxes = document.querySelectorAll('#themes-container .form-check-input');
        themeCheckboxes.forEach(checkbox => {
            const label = document.querySelector(`label[for="${checkbox.id}"]`);
            const labelText = label ? label.textContent.trim() : "";
            if (gameData.themes.some(theme => theme.name === labelText)) {
                checkbox.checked = true;
            } else {
                checkbox.checked = false;
            }
        });


        // Update platforms
        const platformCheckboxes = document.querySelectorAll('#platforms-container .form-check-input');
        platformCheckboxes.forEach(checkbox => {
            const label = document.querySelector(`label[for="${checkbox.id}"]`);
            const labelText = label ? label.textContent.trim() : "";
            if (gameData.platforms.some(platform => platform.name === labelText)) {
                checkbox.checked = true;
            } else {
                checkbox.checked = false;
            }
        });


        // Update player perspectives
        const perspectiveCheckboxes = document.querySelectorAll('#player_perspectives .form-check-input');
        perspectiveCheckboxes.forEach(checkbox => {
            if (gameData.player_perspectives.some(perspective => perspective.name === checkbox.nextSibling.textContent)) {
                checkbox.checked = true;
            }
        });

        // Assuming Developer and Publisher are single selects and you're managing IDs or names
        // Update Developer - Adjust this part based on your actual field setup
        const developerSelect = document.querySelector('#developer');
        if (developerSelect && gameData.developer) {
            const optionToSelect = Array.from(developerSelect.options).find(option => option.textContent === gameData.developer.name);
            if (optionToSelect) {
                developerSelect.value = optionToSelect.value;
            }
        }

        // Update Publisher - Adjust this part based on your actual field setup
        const publisherSelect = document.querySelector('#publisher');
        if (publisherSelect && gameData.publisher) {
            const optionToSelect = Array.from(publisherSelect.options).find(option => option.textContent === gameData.publisher.name);
            if (optionToSelect) {
                publisherSelect.value = optionToSelect.value;
            }
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
                    console.log("API Response (IGDB id Search):", data);
                    
                    if (data.error) {
                        console.error('Error:', data.error);
                    } else {
                        updateFormWithGameData(data); // Call the new function with the game data
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
                    console.log("API Response (IGDB name Search):", data);
                    const resultsContainer = document.querySelector('#search-results');
                    resultsContainer.innerHTML = ''; 
                    updateFormWithGameData(data); // Call the new function with the game data

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
