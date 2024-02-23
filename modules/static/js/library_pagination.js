$(document).ready(function() {
    var currentPage = 1;
    var totalPages = 0;
  
    function fetchPage(page) {
      $.getJSON('/browse_games', { page: page, per_page: 20 }, function(data) {
        $('.game-library-container').empty(); // Ensure this matches your actual container
        totalPages = data.pages;
        currentPage = data.current_page;
        $('#currentPageInfo').text(currentPage + '/' + totalPages);
  
        $.each(data.games, function(i, game) {
            var fullCoverUrl = game.cover_url.startsWith('http') ? game.cover_url : '/static/images/' + game.cover_url;
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
                    <img src="${fullCoverUrl}" alt="${game.name}" class="game-cover">
                </a>
                <div id="details-${game.uuid}" class="popup-game-details hidden">
                    <!-- Details and screenshots will be injected here by JavaScript -->
                </div>
            </div>
            `;
            $('.game-library-container').append(gameCardHtml);
        });
        
  
        $('#prevPage').parent().toggleClass('disabled', currentPage <= 1);
        $('#nextPage').parent().toggleClass('disabled', currentPage >= totalPages);
      });
    }
  
    fetchPage(currentPage);
  
    $('#prevPage').click(function(e) {
      e.preventDefault();
      if (currentPage > 1) {
        fetchPage(--currentPage);
      }
    });
  
    $('#nextPage').click(function(e) {
      e.preventDefault();
      if (currentPage < totalPages) {
        fetchPage(++currentPage);
      }
    });
  });
  
  