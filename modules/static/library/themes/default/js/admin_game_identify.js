document.addEventListener('DOMContentLoaded', function() {
    
    var platformDisplay = document.querySelector('#platform_display');
    const platformId = document.querySelector('#platform_id').textContent; 
    const igdbIdInput = document.querySelector('#igdb_id');
    const fullPathInput = document.querySelector('#full_disk_path');
    const nameInput = document.querySelector('#name');
    const urlInput = document.querySelector('#url');
    const submitButton = document.querySelector('button[type="submit"]');
    const igdbIdFeedback = document.querySelector('#igdb_id_feedback');
    const fullPathFeedback = document.createElement('small');
    const developerInput = document.querySelector('#developer');
    const publisherInput = document.querySelector('#publisher');
    const libraryUuidInput = document.querySelector('#library_uuid');
    fullPathFeedback.id = 'full_disk_path_feedback';
    fullPathInput.parentNode.insertBefore(fullPathFeedback, fullPathInput.nextSibling);

    $(submitButton).tooltip({
        title: "Incomplete entry",
        placement: "top",
        trigger: "hover"
    });

    function updateButtonState(isDisabled) {
        console.log(`Update submit button state: ${isDisabled ? 'Disabled' : 'Enabled'}`);
        submitButton.disabled = isDisabled;
        if (isDisabled) {
            $(submitButton).tooltip('enable');
        } else {
            $(submitButton).tooltip('disable');
        }
    }

    function validateField(inputElement, isValid) {
        if (isValid) {
            console.log(`${inputElement.id} is valid`);
            inputElement.classList.remove('invalid-input');
        } else {
            console.log(`${inputElement.id} is invalid`);
            inputElement.classList.add('invalid-input');
        }
    }

    function checkFieldsAndToggleSubmit() {
        const igdbIdIsValid = igdbIdInput.value.trim().length > 0 && /^\d+$/.test(igdbIdInput.value);
        const fullPathIsValid = fullPathInput.value.trim().length > 0;
        const nameIsValid = nameInput.value.trim().length > 0;
        const libraryUuidIsValid = libraryUuidInput.value.trim().length > 0;

        validateField(igdbIdInput, igdbIdIsValid);
        validateField(fullPathInput, fullPathIsValid);
        validateField(nameInput, nameIsValid);
        validateField(libraryUuidInput, libraryUuidIsValid);

        updateButtonState(!(igdbIdIsValid && fullPathIsValid && nameIsValid && libraryUuidIsValid));
    }

    function updateFormWithGameData(gameData) {
        console.log("Received game data:", gameData); // Print out the gameData object
        // Update genres
        const genreCheckboxes = document.querySelectorAll('#genres-container .form-check-input');
        console.log("Genres:", genreCheckboxes);
        genreCheckboxes.forEach(checkbox => {
            const checkboxLabel = checkbox.nextElementSibling ? checkbox.nextElementSibling.textContent.trim().toLowerCase() : "";
            // Check if genres exist in gameData and then if current genre matches any of those genres
            const isGenreMatched = gameData.genres ? gameData.genres.some(genre => genre.name.toLowerCase() === checkboxLabel) : false;
            checkbox.checked = isGenreMatched;
        });
    
        // Update game modes
        const gameModeCheckboxes = document.querySelectorAll('#gamemodes-container input[type="checkbox"]');
        gameModeCheckboxes.forEach((checkbox) => {
            const checkboxLabel = checkbox.nextElementSibling ? checkbox.nextElementSibling.textContent.trim().toLowerCase() : "";
            // Check if game_modes exist in gameData and then if current game mode matches any of those game modes
            const isGameModeMatched = gameData.game_modes ? gameData.game_modes.some(mode => mode.name.toLowerCase() === checkboxLabel) : false;
            checkbox.checked = isGameModeMatched;
        });
    
        // Update themes
        const themeCheckboxes = document.querySelectorAll('#themes-container .form-check-input');
        themeCheckboxes.forEach(checkbox => {
            const label = document.querySelector(`label[for="${checkbox.id}"]`);
            const labelText = label ? label.textContent.trim() : "";
            // Check if themes exist in gameData and then if current theme matches any of those themes
            const isThemeMatched = gameData.themes ? gameData.themes.some(theme => theme.name === labelText) : false;
            checkbox.checked = isThemeMatched;
        });
    
        // Update platforms
        const platformCheckboxes = document.querySelectorAll('#platforms-container .form-check-input');
        platformCheckboxes.forEach(checkbox => {
            const label = document.querySelector(`label[for="${checkbox.id}"]`);
            const labelText = label ? label.textContent.trim() : "";
            // Check if platforms exist in gameData and then if current platform matches any of those platforms
            const isPlatformMatched = gameData.platforms ? gameData.platforms.some(platform => platform.name === labelText) : false;
            checkbox.checked = isPlatformMatched;
        });


        // Update player perspectives
        const perspectiveCheckboxes = document.querySelectorAll('#perspectives-container input[type="checkbox"]');
        console.log("Found perspective checkboxes: ", perspectiveCheckboxes.length);
        perspectiveCheckboxes.forEach(checkbox => {
            // Since the label text is directly after the checkbox, we use the checkbox ID to match the label text.
            const labelText = checkbox.nextSibling.textContent.trim();
            // Check if player_perspectives exist in gameData and then if current perspective matches any of those perspectives
            const isPerspectiveMatched = gameData.player_perspectives ? gameData.player_perspectives.some(perspective => perspective.name === labelText) : false;
            checkbox.checked = isPerspectiveMatched;
        });




        // Assuming gameData.involved_companies is an array of company IDs
        if (gameData.involved_companies && gameData.involved_companies.length > 0) {
            // Map each companyId to a fetch promise
            const companyFetchPromises = gameData.involved_companies.map(companyId =>
                fetch(`/api/get_company_role?game_igdb_id=${gameData.id}&company_id=${companyId}`)
                    .then(response => response.json())
            );

            // Wait for all fetch promises to resolve
            Promise.all(companyFetchPromises)
                .then(results => {
                    // Flags to check if we found any developer or publisher
                    let foundDeveloper = false;
                    let foundPublisher = false;

                    results.forEach(data => {
                        if (data.error) {
                            console.error('Error:', data.error);
                        } else {
                            // Check the role and update the corresponding field
                            if (data.role === 'Developer') {
                                const developerInput = document.querySelector('#developer');
                                developerInput.value = data.company_name;
                                foundDeveloper = true;
                            } else if (data.role === 'Publisher') {
                                const publisherInput = document.querySelector('#publisher');
                                publisherInput.value = data.company_name;
                                foundPublisher = true;
                            }
                        }
                    });

                    // Set to 'Not Found' if no developer or publisher was found
                    if (!foundDeveloper) {
                        document.querySelector('#developer').value = 'Not Found';
                    }
                    if (!foundPublisher) {
                        document.querySelector('#publisher').value = 'Not Found';
                    }
                })
                .catch(error => console.error('Error processing company roles:', error));
        } else {
            // If no involved companies, set developer and publisher to 'Not Found'
            document.querySelector('#developer').value = 'Not Found';
            document.querySelector('#publisher').value = 'Not Found';
        }


        // Update for video URLs
        const videoURLsInput = document.querySelector('#video_urls');
        if (gameData.videos && gameData.videos.length > 0) {
            // Form the YouTube URLs and join them with commas, ensuring they start with https://
            const videoURLs = gameData.videos.map(video => {
                // Check if video.url is defined to avoid TypeError
                if (video.url) {
                    let url = video.url;
                    if (!url.startsWith('http://') && !url.startsWith('https://')) {
                        url = 'https://' + url; // Prepend https:// if no scheme is present
                    }
                    return url;
                }
                return ''; // Return an empty string or a placeholder URL if video.url is undefined
            }).filter(url => url !== '').join(','); // Filter out any empty strings to avoid invalid URLs in the list
            videoURLsInput.value = videoURLs; // Populate the input field with corrected YouTube URLs
        } else {
            videoURLsInput.value = ''; // Clear the field if there are no videos
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
            fetch(`/api/search_igdb_by_id?igdb_id=${igdbId}`)
                .then(response => response.json())
                .then(data => {
                    console.log("API Response (IGDB id Search):", data);
                    
                    if (data.error) {
                        console.error('Error:', data.error);
                        // Show flash message using notify.js
                        $.notify("Game not found", {
                            className: 'error',
                            position: 'top center'
                        });
                    } else {
                        // Show success notification when game is found
                        $.notify("Game found successfully!", {
                            className: 'success',
                            position: 'top center'
                        });
                        updateFormWithGameData(data);
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
        const platformId = document.querySelector('#platform_id').textContent; // Retrieve the platform ID from the HTML

        console.log(`Initiating IGDB search for name: ${gameName}`);
        if (gameName) {
            fetch(`/api/search_igdb_by_name?name=${encodeURIComponent(gameName)}&platform_id=${encodeURIComponent(platformId)}`)
                .then(response => response.json())
                .then(data => {
                    console.log("API Response (IGDB name Search):", data);
                    const resultsContainer = document.querySelector('#search-results');
                    resultsContainer.innerHTML = '';
                    if (data.results && data.results.length > 0) {
                        data.results.forEach(game => {
                            const resultItem = document.createElement('div');
                            resultItem.className = 'search-result-item';
                            
                            // Initialize the img element early to ensure order
                            const img = document.createElement('img');
                            img.alt = 'Cover Image';
                            img.style.width = '50px'; // Adjust size as needed
                            img.style.height = 'auto';
                            img.style.marginRight = '10px'; // Spacing between image and text
    
                            // Fetch the cover thumbnail URL
                            fetch(`/api/get_cover_thumbnail?igdb_id=${game.id}`)
                            .then(response => response.json())
                            .then(coverData => {
                                if (!coverData.error && coverData.cover_url) {
                                    img.src = coverData.cover_url;
                                } else {
                                    // Use a fallback image if cover URL not found
                                    img.src = '/static/newstyle/nocoverfound.png';
                                }
                                // Prepend the img element regardless of fetch outcome
                                resultItem.prepend(img);
                            })
                            .catch(error => {
                                console.error('Error fetching cover thumbnail:', error);
                                img.src = '/static/newstyle/nocoverfound.png'; // Fallback if fetch fails
                                resultItem.prepend(img);
                            });
                            
                            // Append game name text
                            const textNode = document.createTextNode(game.name);
                            resultItem.appendChild(textNode);
    
                            resultItem.addEventListener('click', function() {
                                // Update form with game data upon selection
                                updateFormWithGameData(game);
    
                                igdbIdInput.value = game.id;
                                nameInput.value = game.name;
                                document.querySelector('#summary').value = game.summary || '';
                                document.querySelector('#storyline').value = game.storyline || '';
                                document.querySelector('#url').value = game.url || '';
                                checkFieldsAndToggleSubmit();
                                resultsContainer.innerHTML = ''; // Clear results after selection
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
