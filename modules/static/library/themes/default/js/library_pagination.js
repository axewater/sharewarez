function setCookie(name, value, days) {
    try {
        var expires = "";
        if (days) {
            var date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = "; expires=" + date.toUTCString();
        }
        const safeValue = JSON.stringify(value);
        document.cookie = `${name}=${encodeURIComponent(safeValue)}${expires}; path=/`;
        console.log(`Cookie set successfully: ${name}`);
    } catch (e) {
        console.error('Error setting cookie:', e);
    }
}

function getCookie(name) {
    try {
        const nameEQ = name + "=";
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') {
                c = c.substring(1);
            }
            if (c.indexOf(nameEQ) === 0) {
                const encodedValue = c.substring(nameEQ.length);
                const decodedValue = decodeURIComponent(encodedValue);
                try {
                    return JSON.parse(decodedValue);
                } catch (parseError) {
                    console.error('Error parsing cookie value:', parseError);
                    deleteCookie(name);
                    return null;
                }
            }
        }
    } catch (e) {
        console.error('Error reading cookie:', e);
        return null;
    }
    return null;
}
function deleteCookie(name) {
    document.cookie = name + '=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
}
var csrfToken;
var sortOrder = 'asc'; 
$('#sortOrderToggle').text(sortOrder === 'asc' ? '^' : '~');
$(document).ready(function() {
    var savedFilters = getCookie('libraryFilters');
    if (savedFilters) {
        try {
            $('#libraryNameSelect').val(savedFilters.library_uuid || '');
            $('#genreSelect').val(savedFilters.genre || '');
            $('#themeSelect').val(savedFilters.theme || '');
            $('#gameModeSelect').val(savedFilters.game_mode || '');
            $('#playerPerspectiveSelect').val(savedFilters.player_perspective || '');
            $('#ratingSlider').val(savedFilters.rating || 0);
            $('#ratingValue').text(savedFilters.rating || 0);
            console.log('Successfully restored filters from cookie');
        } catch (e) {
            console.error('Error parsing saved filters:', e);
            deleteCookie('libraryFilters');
            resetFilters();
        }
    }
    var userPerPage = $('body').data('user-per-page');
    var userDefaultSort = $('body').data('user-default-sort');
    var userDefaultSortOrder = $('body').data('user-default-sort-order');
    console.log("User preferences:", userPerPage, userDefaultSort, userDefaultSortOrder);
    var currentPage = 1;
    var totalPages = 0;
    csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    if (userPerPage) {
        $('#perPageSelect').val(userPerPage.toString());
    }
    if (userDefaultSort) {
        $('#sortSelect').val(userDefaultSort);
    }
    sortOrder = userDefaultSortOrder || 'asc';
    $('#sortOrderToggle').text(sortOrder === 'asc' ? '^' : '~');

    function populateLibraries(callback) {
        $.ajax({
            url: '/api/get_libraries',
            method: 'GET',
            success: function(response) {
                var librarySelect = $('#libraryNameSelect');
                librarySelect.empty().append($('<option>', { value: '', text: 'All Libraries' }));
                response.forEach(function(library) {
                    librarySelect.append($('<option>', {
                        value: library.uuid, 
                        text: library.name
                    }));
                });
                if (typeof callback === "function") callback();
            },
            error: function(xhr, status, error) {
                console.error("Error fetching libraries:", error);
            }
        }).done(function() {
            var initialParams = getUrlParams();
            if (initialParams.library_uuid) {
                $('#libraryNameSelect').val(initialParams.library_uuid);
            }
            fetchFilteredGames();
        });
    }
    function populateGenres(callback) {
        $.ajax({
            url: '/api/genres',
            method: 'GET',
            success: function(response) {
                var genreSelect = $('#genreSelect');
                genreSelect.empty().append($('<option>', { value: '', text: 'All Genres' }));
                response.forEach(function(genre) {
                    genreSelect.append($('<option>', {
                        value: genre.name,
                        text: genre.name
                    }));
                });
                if (typeof callback === "function") callback();
            },
            error: function(xhr, status, error) {
                console.error("Error fetching genres:", error);
            }
        }).done(function() {
            var initialParams = getUrlParams();
            if (initialParams.genre) {
                $('#genreSelect').val(initialParams.genre);
            }
        });
    }

    function populateGameModes(callback) {
        $.ajax({
            url: '/api/game_modes',
            method: 'GET',
            success: function(response) {
                var gameModeSelect = $('#gameModeSelect');
                gameModeSelect.empty().append($('<option>', { value: '', text: 'All Game Modes' }));
                response.forEach(function(gameMode) {
                    gameModeSelect.append($('<option>', {
                        value: gameMode.name,
                        text: gameMode.name
                    }));
                });
                if (typeof callback === "function") callback();
            },
            error: function(xhr, status, error) {
                console.error("Error fetching game modes:", error);
            }
        }).done(function() {
            var initialParams = getUrlParams();
            if (initialParams.genre) {
                $('#gameModeSelect').val(initialParams.gameMode);
            }
        });
    }

    function populatePlayerPerspectives(callback) {
        $.ajax({
            url: '/api/player_perspectives',
            method: 'GET',
            success: function(response) {
                var perspectiveSelect = $('#playerPerspectiveSelect');
                perspectiveSelect.empty().append($('<option>', { value: '', text: 'All Perspectives' }));
                response.forEach(function(perspective) {
                    perspectiveSelect.append($('<option>', {
                        value: perspective.name,
                        text: perspective.name
                    }));
                });
                if (typeof callback === "function") callback();
            },
            error: function(xhr, status, error) {
                console.error("Error fetching player perspectives:", error);
            }
        });
    }

    function populateThemes(callback) {
        $.ajax({
            url: '/api/themes',
            method: 'GET',
            success: function(response) {
                var themeSelect = $('#themeSelect');
                themeSelect.empty().append($('<option>', { value: '', text: 'All Themes' }));
                response.forEach(function(theme) {
                    themeSelect.append($('<option>', {
                        value: theme.name,
                        text: theme.name
                    }));
                });
                if (typeof callback === "function") callback();
            },
            error: function(xhr, status, error) {
                console.error("Error fetching themes:", error);
            }
        });
    }

    function getUrlParams() {
        var params = {};
        var queryString = window.location.search.substring(1);
        var vars = queryString.split('&');
        vars.forEach(function(param) {
            var pair = param.split('=');
            if (pair[0] && pair[1]) {
                params[pair[0]] = decodeURIComponent(pair[1].replace(/\+/g, ' '));
            }
        });
        return params;
    }

    function fetchFilteredGames(page) {
        var urlParams = getUrlParams(); 
        page = page || urlParams.page || 1; 
        var filters = {
            library_uuid: $('#libraryNameSelect').val() || urlParams.library_uuid || undefined,
            page: page,
            per_page: $('#perPageSelect').val() || 20,
            category: $('#categorySelect').val() || urlParams.category,
            genre: $('#genreSelect').val() || urlParams.genre,
            game_mode: $('#gameModeSelect').val() || urlParams.gameMode,
            player_perspective: $('#playerPerspectiveSelect').val() || urlParams.playerPerspective,
            theme: $('#themeSelect').val() || urlParams.theme,
            rating: $('#ratingSlider').val() !== '0' ? $('#ratingSlider').val() : undefined, 
            sort_by: $('#sortSelect').val(),
            sort_order: sortOrder,
        };
        console.log("Fetching games with filters:", filters);
        var queryString = $.param(filters);
        console.log(`Full query URL: /browse_games?${queryString}`);

        $.ajax({
            url: '/browse_games',
            data: filters,
            method: 'GET',
            success: function(response) {
                totalPages = response.pages;
                currentPage = response.current_page;
                $('#currentPageInfo').text(currentPage + '/' + totalPages);
                updateGamesContainer(response.games);
                updatePaginationControls();
            },
            error: function(xhr, status, error) {
                console.error("AJAX error:", error);
            }
        });
    }

    function updateGamesContainer(games) {
        $('#gamesContainer').empty();
        if (libraryCount < 1) {
            $.ajax({
                url: '/api/current_user_role',
                method: 'GET',
                success: function(response) {
                    let message;
                    if (response.role === 'admin') {
                        message = `<p>You have no Libraries!<br><br> Go to <a href="${libraryManagerUrl}">Library Manager</a> and create one.</p>`;
                    } else {
                        message = '<p>No games or libraries found. Complain to the Captain of this vessel!</p>';
                    }
                    if ($('#gamesContainer').empty()) {
                        $('#gamesContainer').append(message);
                    }
                },
                error: function() {
                    $('#gamesContainer').append('<p>Error fetching user role. Please try again later.</p>');
                }
            });
            return;
        }

        else if (gamesCount < 1) {
            $.ajax({
                url: '/api/current_user_role',
                method: 'GET',
                success: function(response) {
                    let message;
                    if (response.role === 'admin') {
                        message = `<p>You have no games!<br> <br>Go to <a href="${libraryScanUrl}">Scan Manager</a> and add some games.</p>`;
                    } else {
                        message = '<p>No games or libraries found. Complain to the Captain of this vessel!</p>';
                    }
                    if ($('#gamesContainer').empty()) {
                        $('#gamesContainer').append(message);
                    }
                },
                error: function() {
                    $('#gamesContainer').append('<p>Error fetching user role. Please try again later.</p>');
                }
            });
            return;
        }

        else if (games.length === 0) {
            $.ajax({
                url: '/api/current_user_role', 
                method: 'GET',
                success: function(response) {
                    let message; 
                    if (response.role === 'admin') {
                        message = `<p>You have no games in this library!<br> <br>Go to <a href="${libraryScanUrl}">Scan Manager</a> and add some games to the library.</p>`;
                    } else {
                        message = '<p>No games or libraries found. Complain to the Captain of this vessel!</p>';
                    }
                    if ($('#gamesContainer').empty()) {
                        $('#gamesContainer').append(message);
                    }
                },
                error: function() {
                    $('#gamesContainer').append('<p>Error fetching user role. Please try again later.</p>');
                }
            });
            return;
        }

        games.forEach(function(game) {
            var gameCardHtml = createGameCardHtml(game);
            $('#gamesContainer').append(gameCardHtml);
        });
    }

    function createGameCardHtml(game) {
        var genres = game.genres ? game.genres.join(', ') : 'No Genres';
        var defaultCover = 'newstyle/default_cover.jpg';
        var fullCoverUrl = !game.cover_url || game.cover_url === defaultCover ? '/static/' + defaultCover : '/static/library/images/' + game.cover_url;
        var popupMenuHtml = createPopupMenuHtml(game);
        var gameCardHtml = `
    <div class="game-card-container">
        <div class="game-card" onmouseover="showDetails(this, '${game.uuid}')" onmouseout="hideDetails()" data-name="${game.name}" data-size="${game.size}" data-genres="${genres}">
            <button id="menuButton-${game.uuid}" class="button-glass-hamburger"><i class="fas fa-bars"></i></button>
            <button class="favorite-btn" data-game-uuid="${game.uuid}">
                <i class="fas fa-heart"></i>
            </button>
            ${popupMenuHtml}
            
            <div class="game-cover">
                <a href="/game_details/${game.uuid}">
                <img src="${fullCoverUrl}" alt="${game.name}" class="game-cover">
                </a>
            </div>
            <div id="details-${game.uuid}" class="popup-game-details hidden">
                <!-- Details and screenshots will be injected here by JavaScript -->
            </div>
        </div>
    </div>
    `;
        return gameCardHtml;
    }

    function createPopupMenuHtml(game) {
        // update the popup_menu.html template as well
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const enableDeleteGameOnDisk = document.body.getAttribute('data-enable-delete-game-on-disk') === 'true';
        let menuHtml = `
    <div id="popupMenu-${game.uuid}" class="popup-menu" style="display: none;">
        <form action="/download_game/${game.uuid}" method="get" class="menu-item">
            <button type="submit" class="menu-button">Download</button>
        </form>
        <form action="/game_edit/${game.uuid}" method="get" class="menu-item">
            <button type="submit" class="menu-button">Edit Details</button>
        </form>
        <form action="/edit_game_images/${game.uuid}" method="get" class="menu-item">
            <button type="submit" class="menu-button">Edit Images</button>
        </form>
        <form action="/refresh_game_images/${game.uuid}" method="post" class="menu-item">
            <input type="hidden" name="csrf_token" value="${csrfToken}">
            <button type="submit" class="menu-button refresh-game-images" data-game-uuid="${game.uuid}">Refresh Images</button>
        </form>
        <div class="menu-item">
            <button type="button" class="menu-button delete-game" data-game-uuid="${game.uuid}">Remove Game</button>
        </div>`;
        if (enableDeleteGameOnDisk) {
            menuHtml += `
        <div class="menu-item">
            <button type="button" class="menu-button trigger-delete-disk-modal delete-game-from-disk" data-game-uuid="${game.uuid}">Delete Game from Disk</button>
        </div>`;
        }
        menuHtml += `
        <div class="menu-item">
            <button type="submit" onclick="window.open('{{ game.url }}', 'target=_new')" class="menu-button">Open IGDB Page</button>
        </div>
    </div>
    `;
        return menuHtml;
    }

    $('#sortOrderToggle').click(function() {
        sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
        $(this).text(sortOrder === 'asc' ? '^' : '~'); 
        console.log('sortOrderToggle clicked, new sort order:', sortOrder);
        fetchFilteredGames(currentPage);
    });

    function updatePaginationControls() {
        $('#prevPage').parent().toggleClass('disabled', currentPage <= 1);
        $('#nextPage').parent().toggleClass('disabled', currentPage >= totalPages);
    }

    $('#perPageSelect').change(function() {
        fetchFilteredGames(1);
        console.log('perPageSelect changed to ' + $(this).val());
    });

    $('#prevPage').click(function(e) {
        e.preventDefault();
        if (currentPage > 1) {
            fetchFilteredGames(--currentPage);
        }
    });

    $('#nextPage').click(function(e) {
        e.preventDefault();
        if (currentPage < totalPages) {
            fetchFilteredGames(++currentPage);
        }
    });

    $('#filterForm').on('submit', function(e) {
        e.preventDefault();
        var filters = {
            library_uuid: $('#libraryNameSelect').val(),
            genre: $('#genreSelect').val(),
            theme: $('#themeSelect').val(),
            game_mode: $('#gameModeSelect').val(),
            player_perspective: $('#playerPerspectiveSelect').val(),
            rating: $('#ratingSlider').val()
        };
        console.log('Saving filters to cookie:', filters);
        setCookie('libraryFilters', filters, 30);
        fetchFilteredGames(1);
    });

    $('#ratingSlider').on('input', function() {
        $('#ratingValue').text($(this).val());
    });

    $('#clearFilters').click(function() {
        $('#libraryNameSelect, #genreSelect, #themeSelect, #gameModeSelect, #playerPerspectiveSelect').val('');
        $('#ratingSlider').val(0);
        $('#ratingValue').text('0');
        $('#sortSelect').val('name');
        deleteCookie('libraryFilters');
        fetchFilteredGames(1);
    });

    $('#sortSelect').change(function() {
        fetchFilteredGames(1);
    });

    var initialParams = getUrlParams();
    if (initialParams.genre) {
        $('#genreSelect').val(initialParams.genre);
    }
    var initialParams = getUrlParams();
    if (initialParams.theme) {
        $('#themeSelect').val(initialParams.theme);
    }
    var initialParams = getUrlParams();
    if (initialParams.gameMode) {
        $('#gameModeSelect').val(initialParams.gameMode);
    }
    var initialParams = getUrlParams();
    if (initialParams.playerPerspective) {
        $('#playerPerspectiveSelect').val(initialParams.playerPerspective);
    }

    populateLibraries(function() {
        populateGenres(function() {
            populateThemes(function() {
                populateGameModes(function() {
                    populatePlayerPerspectives(function() {
                        // restore filters from cookie
                        var savedFilters = getCookie('libraryFilters');
                        if (savedFilters) {
                            console.log('Restoring filters from cookie:', savedFilters);
                            $('#libraryNameSelect').val(savedFilters.library_uuid || '');
                            $('#genreSelect').val(savedFilters.genre || '');
                            $('#themeSelect').val(savedFilters.theme || '');
                            $('#gameModeSelect').val(savedFilters.game_mode || '');
                            $('#playerPerspectiveSelect').val(savedFilters.player_perspective || '');
                            $('#ratingSlider').val(savedFilters.rating || 0);
                            $('#ratingValue').text(savedFilters.rating || 0);

                            // Now fetch games with restored filters
                            fetchFilteredGames();
                        } else {
                            fetchFilteredGames();
                        }
                    });
                });
            });
        });
    });
});

document.body.addEventListener('click', function(event) {
    if (event.target.classList.contains('refresh-game-images')) {
        event.preventDefault();
        const gameUuid = event.target.getAttribute('data-game-uuid');
        console.log(`Refreshing images for game UUID: ${gameUuid}`);

        fetch(`/refresh_game_images/${gameUuid}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ /*  */ })
        })
        .then(response => {
            console.log('Response status:', response.status);
            if (!response.ok) {
                throw new Error(`Network response was not ok, status: ${response.status}`);
            }
            return response.text().then(text => {
                try {
                    return JSON.parse(text);
                } catch (error) {
                    console.error('Error parsing JSON:', error);
                    console.log('Raw text response:', text);
                    throw new Error('Failed to parse JSON');
                }
            });
        })
        .then(data => {
            console.log('Game images refreshed successfully', data);
        })
        .catch(error => {
            console.error('There has been a problem with your fetch operation:', error);
        });
    }
});
