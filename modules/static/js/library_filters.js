
$(document).ready(function() {
    function populateGenres() {
        $.ajax({
            url: '/api/genres', // Adjust if necessary to match your Flask route
            method: 'GET',
            success: function(genres) {
                var genreSelect = $('#genreSelect');
                genreSelect.empty().append($('<option>', { value: '', text: 'All Genres' }));
                genres.forEach(function(genre) {
                    genreSelect.append($('<option>', {
                        value: genre.name,
                        text: genre.name
                    }));
                });
            },
            error: function(xhr, status, error) {
                console.error("Error fetching genres:", error);
            }
        });
    }


    function populateGameModes() {
        $.ajax({
            url: '/api/game_modes', // Adjust if necessary to match your Flask route
            method: 'GET',
            success: function(gameModes) {
                var gameModeSelect = $('#gameModeSelect');
                gameModeSelect.empty().append($('<option>', { value: '', text: 'All Game Modes' }));
                gameModes.forEach(function(gameMode) {
                    gameModeSelect.append($('<option>', {
                        value: gameMode.name,
                        text: gameMode.name
                    }));
                });
            },
            error: function(xhr, status, error) {
                console.error("Error fetching game modes:", error);
            }
        });
    }

    // Adjusted function to populate themes from the API
    function populateThemes() {
        $.ajax({
            url: '/api/themes', // Make sure this URL matches your Flask route for themes
            method: 'GET',
            success: function(themes) {
                var themeSelect = $('#themeSelect');
                themeSelect.empty().append($('<option>', { value: '', text: 'All Themes' }));
                themes.forEach(function(theme) {
                    themeSelect.append($('<option>', {
                        value: theme.name,
                        text: theme.name
                    }));
                });
            },
            error: function(xhr, status, error) {
                console.error("Error fetching themes:", error);
            }
        });
    }  

    function fetchFilteredGames() {
        var filters = {
            category: $('#categorySelect').val(),
            genre: $('#genreSelect').val(),
            gameMode: $('#gameModeSelect').val(),
            playerPerspective: $('#playerPerspectiveSelect').val(),
            theme: $('#themeSelect').val(),
            rating: $('#ratingSlider').val(),
        };
        console.log("Sending filters:", filters); 
        $.ajax({
            url: '/browse_games',
            data: filters,
            method: 'GET',
            success: function(response) {
                console.log("AJAX response:", response);
    
                $('#gamesContainer').empty();
    
                if(response.hasOwnProperty('games') && Array.isArray(response.games)) {
                    response.games.forEach(function(game) {
                        var genres = game.genres ? game.genres.join(', ') : 'No Genres';
    
                        // Create popup menu HTML string, replacing template variables with JS variables
                        var popupMenuHtml = `
                        <div id="popupMenu-${game.uuid}" class="popup-menu" style="display: none;">
                            <form action="/main/download_game/${game.uuid}" method="get" class="menu-item">
                                <button type="submit" class="menu-button">Download</button>
                            </form>
    
                            <form action="/main/game_edit/${game.uuid}" method="get" class="menu-item">
                                <button type="submit" class="menu-button">Edit Details</button>
                            </form>
                            
                            <form action="/main/edit_game_images/${game.uuid}" method="get" class="menu-item">
                                <button type="submit" class="menu-button">Edit Images</button>
                            </form>
    
                            <form action="/main/refresh_game_images/${game.uuid}" method="post" class="menu-item">
                                <button type="submit" class="menu-button">Refresh Images</button>
                            </form>
                            <div class="menu-item">
                                <button type="button" class="menu-button delete-game" data-game-uuid="${game.uuid}">Remove Game</button>
                            </div>
                            <div class="menu-item">
                                <a href="${game.url}" target="_blank" class="menu-button" style="text-decoration: none; color: inherit;">Open IGDB Page</a>
                            </div>
                        </div>`;
    
                        var gameCardHtml = `
                        <div class="game-card" onmouseover="showDetails(this, '${game.uuid}')" onmouseout="hideDetails()" data-name="${game.name}" data-size="${game.size}" data-genres="${genres}">
                            <button id="menuButton-${game.uuid}" class="button-glass-hamburger"><i class="fas fa-bars"></i></button>
                            ${popupMenuHtml}
                            <a href="/game_details/${game.uuid}">
                                <img src="${game.cover_url.startsWith('http') ? game.cover_url : '/static/images/' + game.cover_url}" alt="${game.name}" class="game-cover">
                            </a>
                            <div id="details-${game.uuid}" class="popup-game-details hidden">
                                <!-- Details and screenshots will be injected here by JavaScript -->
                            </div>
                        </div>
                        `;
                        $('#gamesContainer').append(gameCardHtml);
                    });
                } else {
                    console.error("No 'games' property found in response.");
                }
            },
            error: function(xhr, status, error) {
                console.error("AJAX error:", error);
            }
        });
    }
    

    populateGenres();
    populateThemes();
    populateGameModes();

    $('#filterForm').on('submit', function(e) {
        e.preventDefault();
        fetchFilteredGames();
    });
    

    $('#ratingSlider').on('input', function() {
        $('#ratingValue').text($(this).val());
    });
});
