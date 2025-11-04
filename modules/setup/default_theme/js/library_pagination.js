let currentLibrariesSubmenu = null;
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
$('#sortOrderToggle').html(sortOrder === 'asc' ? '<i class="fas fa-sort-up"></i>' : '<i class="fas fa-sort-down"></i>');
$(document).ready(function() {
    // Get server-rendered filter data
    var currentFilters = {};
    var currentPageFromServer = 1;
    var totalPagesFromServer = 0;
    
    try {
        var filtersData = $('body').data('current-filters');
        currentFilters = filtersData || {};
        currentPageFromServer = $('body').data('current-page') || 1;
        totalPagesFromServer = $('body').data('total-pages') || 0;
        console.log('Server-provided filters:', currentFilters);
        console.log('Server pagination:', currentPageFromServer, '/', totalPagesFromServer);
    } catch (e) {
        console.error('Error reading server filter data:', e);
    }
    
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
    
    // Function to compare if saved filters match server filters
    function filtersMatch(savedFilters, currentFilters) {
        if (!savedFilters || !currentFilters) return false;
        
        var keyMappings = {
            'library_uuid': 'library_uuid',
            'genre': 'genre', 
            'theme': 'theme',
            'game_mode': 'game_mode',
            'player_perspective': 'player_perspective',
            'rating': 'rating'
        };
        
        for (var key in keyMappings) {
            var savedVal = savedFilters[key] || '';
            var currentVal = currentFilters[keyMappings[key]] || '';
            
            // Convert to strings for comparison
            if (String(savedVal) !== String(currentVal)) {
                console.log(`Filter mismatch on ${key}: saved="${savedVal}" vs current="${currentVal}"`);
                return false;
            }
        }
        return true;
    }
    var userPerPage = $('body').data('user-per-page');
    var userDefaultSort = $('body').data('user-default-sort');
    var userDefaultSortOrder = $('body').data('user-default-sort-order');
    console.log("User preferences:", userPerPage, userDefaultSort, userDefaultSortOrder);
    
    // Initialize pagination from server data
    var currentPage = currentPageFromServer;
    var totalPages = totalPagesFromServer;
    
    // Initialize pagination display
    if (totalPages > 0) {
        $('#currentPageInfo, #currentPageInfoBottom').text(currentPage + '/' + totalPages);
        updatePaginationControls();
    }
    csrfToken = CSRFUtils.getToken();
    if (userPerPage) {
        $('#perPageSelect').val(userPerPage.toString());
    }
    if (userDefaultSort) {
        $('#sortSelect').val(userDefaultSort);
    }
    sortOrder = userDefaultSortOrder || 'asc';
    $('#sortOrderToggle').html(sortOrder === 'asc' ? '<i class="fas fa-sort-up"></i>' : '<i class="fas fa-sort-down"></i>');

    function populateDropdown(options) {
        const { apiUrl, elementId, defaultText, valueField, textField, paramName, callback } = options;
        return $.ajax({
            url: apiUrl,
            method: 'GET',
            success: function(response) {
                const selectElement = $(elementId);
                selectElement.empty().append($('<option>', { value: '', text: defaultText }));
                response.forEach(function(item) {
                    selectElement.append($('<option>', {
                        value: item[valueField],
                        text: item[textField]
                    }));
                });
                if (typeof callback === "function") {
                    callback();
                }
            },
            error: function(xhr, status, error) {
                console.error(`Error fetching data for ${elementId}:`, error);
            }
        }).done(function() {
            if (paramName) {
                const initialParams = getUrlParams();
                if (initialParams[paramName]) {
                    $(elementId).val(initialParams[paramName]);
                }
            }
        });
    }

    function populateLibraries(callback) {
        populateDropdown({
            apiUrl: '/api/get_libraries',
            elementId: '#libraryNameSelect',
            defaultText: 'All Libraries',
            valueField: 'uuid',
            textField: 'name',
            paramName: 'library_uuid',
            callback: callback
        }).done(function() {
            // Skip initial fetchFilteredGames() - server already rendered correct games
            console.log('Libraries populated, skipping initial fetch since server already rendered filtered games');
        });
    }

    function populateGenres(callback) {
        populateDropdown({
            apiUrl: '/api/genres',
            elementId: '#genreSelect',
            defaultText: 'All Genres',
            valueField: 'name',
            textField: 'name',
            paramName: 'genre',
            callback: callback
        });
    }

    function populateGameModes(callback) {
        populateDropdown({
            apiUrl: '/api/game_modes',
            elementId: '#gameModeSelect',
            defaultText: 'All Game Modes',
            valueField: 'name',
            textField: 'name',
            paramName: 'gameMode',
            callback: callback
        });
    }

    function populatePlayerPerspectives(callback) {
        populateDropdown({
            apiUrl: '/api/player_perspectives',
            elementId: '#playerPerspectiveSelect',
            defaultText: 'All Perspectives',
            valueField: 'name',
            textField: 'name',
            paramName: 'playerPerspective',
            callback: callback
        });
    }

    function populateThemes(callback) {
        populateDropdown({
            apiUrl: '/api/themes',
            elementId: '#themeSelect',
            defaultText: 'All Themes',
            valueField: 'name',
            textField: 'name',
            paramName: 'theme',
            callback: callback
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
                $('#currentPageInfo, #currentPageInfoBottom').text(currentPage + '/' + totalPages);
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

    function createPopupMenuHtml(game) {
        const csrfToken = CSRFUtils.getToken();
        const enableDeleteGameOnDisk = document.body.getAttribute('data-enable-delete-game-on-disk') === 'true';
        const discordConfigured = document.body.getAttribute('data-discord-configured') === 'true';
        const discordManualTrigger = document.body.getAttribute('data-discord-manual-trigger') === 'true';
        const isAdmin = document.body.getAttribute('data-is-admin') === 'true';
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
        </div>
        <div class="menu-item move-library-container">
            <button type="button" class="menu-button move-library" data-game-uuid="${game.uuid}">Move Library</button>
            <div class="submenu-libraries" style="display: none;">
                <div class="loading-libraries">
                    <span>Loading libraries...</span>
                </div>
                <div class="libraries-list" style="display: none;">
                </div>
            </div>
        </div>`;
        if (enableDeleteGameOnDisk) {
            menuHtml += `
        <div class="menu-item">
            <button type="button" class="menu-button trigger-delete-disk-modal delete-game-from-disk" data-game-uuid="${game.uuid}">Delete Game from Disk</button>
        </div>`;
        }
        if (game.url) {
            menuHtml += `
        <div class="menu-item">
            <button type="submit" onclick="window.open('${game.url}', '_blank')" class="menu-button">Open IGDB Page</button>
        </div>`;
        }
        
        if (discordConfigured && discordManualTrigger && isAdmin) {
            menuHtml += `
        <div class="menu-item">
            <button type="button" class="menu-button trigger-discord-notification" data-game-uuid="${game.uuid}">Send Discord Notification</button>
        </div>`;
        }
        
        menuHtml += `
    </div>
    `;
        return menuHtml;
    }

    function createGameCardHtml(game) {
        var genres = game.genres ? game.genres.join(', ') : 'No Genres';
        var defaultCover = 'newstyle/default_cover.jpg';
        var fullCoverUrl = !game.cover_url || game.cover_url === defaultCover ? '/static/' + defaultCover : '/static/library/images/' + game.cover_url;
        var popupMenuHtml = createPopupMenuHtml(game);

        // Generate status badge HTML if user has set a status
        var statusBadgeHtml = '';
        if (game.user_status) {
            const statusConfig = {
                'unplayed': { icon: 'fa-box', color: '#808080' },
                'unfinished': { icon: 'fa-gamepad', color: '#4A90E2' },
                'beaten': { icon: 'fa-flag-checkered', color: '#50C878' },
                'completed': { icon: 'fa-trophy', color: '#FFD700' },
                'null': { icon: 'fa-ban', color: '#DC3545' }
            };
            const config = statusConfig[game.user_status];
            if (config) {
                statusBadgeHtml = `
                    <div class="game-status-badge">
                        <i class="fas ${config.icon}" style="color: ${config.color};"></i>
                    </div>
                `;
            }
        }

        var gameCardHtml = `
    <div class="game-card-container">
        <div class="game-card" onmouseover="showDetails(this, '${game.uuid}')" onmouseout="hideDetails()" data-name="${game.name}" data-size="${game.size}" data-genres="${genres}">
            <button id="menuButton-${game.uuid}" class="button-glass-hamburger"><i class="fas fa-bars"></i></button>
            <button class="favorite-btn" data-game-uuid="${game.uuid}" data-is-favorite="${game.is_favorite}">
                <i class="fas fa-heart"></i>
            </button>
            ${popupMenuHtml}
            ${statusBadgeHtml}

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


    $('#sortOrderToggle').click(function() {
        sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
        $(this).html(sortOrder === 'asc' ? '<i class="fas fa-sort-up"></i>' : '<i class="fas fa-sort-down"></i>'); 
        console.log('sortOrderToggle clicked, new sort order:', sortOrder);
        fetchFilteredGames(currentPage);
    });

    function updatePaginationControls() {
        // Update top pagination controls
        $('#firstPage, #firstPageBottom').prop('disabled', currentPage <= 1);
        $('#prevPage, #prevPageBottom').prop('disabled', currentPage <= 1);
        $('#nextPage, #nextPageBottom').prop('disabled', currentPage >= totalPages);
        $('#lastPage, #lastPageBottom').prop('disabled', currentPage >= totalPages);

        // Legacy support for old pagination
        $('#prevPage').parent().toggleClass('disabled', currentPage <= 1);
        $('#nextPage').parent().toggleClass('disabled', currentPage >= totalPages);
    }

    $('#perPageSelect').change(function() {
        fetchFilteredGames(1);
        console.log('perPageSelect changed to ' + $(this).val());
    });

    // First page handlers
    $('#firstPage, #firstPageBottom').click(function(e) {
        e.preventDefault();
        if (currentPage > 1) {
            currentPage = 1;
            fetchFilteredGames(currentPage);
        }
    });

    // Previous page handlers
    $('#prevPage, #prevPageBottom').click(function(e) {
        e.preventDefault();
        if (currentPage > 1) {
            fetchFilteredGames(--currentPage);
        }
    });

    // Next page handlers
    $('#nextPage, #nextPageBottom').click(function(e) {
        e.preventDefault();
        if (currentPage < totalPages) {
            fetchFilteredGames(++currentPage);
        }
    });

    // Last page handlers
    $('#lastPage, #lastPageBottom').click(function(e) {
        e.preventDefault();
        if (currentPage < totalPages) {
            currentPage = totalPages;
            fetchFilteredGames(currentPage);
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
        fetchFilteredGames(currentPage);
    });

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

                            // Only fetch games if saved filters don't match server-rendered filters
                            if (!filtersMatch(savedFilters, currentFilters)) {
                                console.log('Filters changed from server-rendered, fetching updated games');
                                fetchFilteredGames();
                            } else {
                                console.log('Filters match server-rendered data, skipping redundant fetch');
                            }
                        } else {
                            // No saved filters, check if server has any filters applied
                            var hasServerFilters = Object.keys(currentFilters).length > 0;
                            if (hasServerFilters) {
                                console.log('No saved filters but server has filters, skipping redundant fetch');
                            } else {
                                console.log('No filters anywhere, server should have rendered all games already');
                            }
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

        // Close the popup menu
        const popupMenu = document.getElementById(`popupMenu-${gameUuid}`);
        if (popupMenu) {
            popupMenu.style.display = 'none';
        }

        fetch(`/refresh_game_images/${gameUuid}`, {
            method: 'POST',
            headers: CSRFUtils.getHeaders({ 
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }),
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
            if (data.message) {
                $.notify(data.message, "success");
            }
        })
        .catch(error => {
            console.error('There has been a problem with your fetch operation:', error);
            $.notify("An error occurred while refreshing game images.", "error");
        });
    }

});

window.addEventListener('click', function() {
    document.querySelectorAll('.popup-menu').forEach(function(menu) {
        menu.style.display = 'none';
    });
    
    // Also close any open libraries submenu
    if (currentLibrariesSubmenu) {
        currentLibrariesSubmenu.style.display = 'none';
        currentLibrariesSubmenu = null;
    }
});

document.body.addEventListener('click', function(event) {
    if (event.target.closest('.popup-menu')) {
        event.stopPropagation();
    }
});
