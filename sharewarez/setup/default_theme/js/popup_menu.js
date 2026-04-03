document.addEventListener('DOMContentLoaded', function() {
    
    let currentLibrariesSubmenu = null;
    var csrfToken = CSRFUtils.getToken();

    // Adjusted for dynamic content using event delegation
    document.body.addEventListener('click', function(event) {
        // Handling deletion of a game (not from disk)
        if (event.target.classList.contains('delete-game')) {
            event.stopPropagation();
            const gameUuid = event.target.getAttribute('data-game-uuid');
            console.log(`Removing game from library UUID: ${gameUuid}`);

            fetch(`/delete_game/${gameUuid}`, {
                method: 'POST',
                headers: CSRFUtils.getHeaders({
                    'Content-Type': 'application/json'
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Game removed successfully');
                    $.notify(data.message, "success");
                    
                    // Check if we're on game details page by looking for game-specific elements
                    const isGameDetailsPage = document.querySelector('.game-card-q1, .game-card-q2') !== null;
                    
                    if (isGameDetailsPage) {
                        // On game details page, redirect to library after a short delay to show the notification
                        setTimeout(() => {
                            window.location.href = '/library';
                        }, 1000);
                    } else {
                        // On library page, remove the game card with fade out animation
                        const gameCard = document.querySelector(`[data-game-uuid="${gameUuid}"]`).closest('.game-card-container');
                        if (gameCard) {
                            gameCard.style.transition = 'opacity 0.3s ease';
                            gameCard.style.opacity = '0';
                            setTimeout(() => {
                                gameCard.remove();
                                
                                // Check if this was the last game and show empty message if needed
                                const remainingCards = document.querySelectorAll('.game-card-container');
                                if (remainingCards.length === 0) {
                                    const container = document.querySelector('.game-library-container');
                                    if (container) {
                                        container.innerHTML = '<p>No games found in this library.</p>';
                                    }
                                }
                            }, 300);
                        }
                    }
                } else {
                    console.error('Error removing game:', data.message);
                    $.notify(data.message, "error");
                }
            })
            .catch(error => {
                console.error('There has been a problem with your fetch operation:', error);
                $.notify("An error occurred while removing the game.", "error");
            });
        }

        // Handling "Delete Game from Disk" with modal instead of alert
        if (event.target.classList.contains('delete-game-from-disk')) {
            event.preventDefault(); // Prevent any default action
            const gameUuid = event.target.getAttribute('data-game-uuid');
            console.log(`Preparing to delete from disk UUID: ${gameUuid}`);

            // Set the UUID in the modal's form hidden input
            document.getElementById('deleteGameUuid').value = gameUuid;
            // Display the modal
            document.getElementById('deleteGameModal').style.display = 'block';
        }

        // Handling Discord notification trigger
        if (event.target.classList.contains('trigger-discord-notification')) {
            event.stopPropagation();
            const gameUuid = event.target.getAttribute('data-game-uuid');
            console.log(`Triggering Discord notification for game UUID: ${gameUuid}`);

            // Disable the button to prevent double-clicks
            const button = event.target;
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = 'Sending...';

            fetch(`/trigger_discord_notification/${gameUuid}`, {
                method: 'POST',
                headers: CSRFUtils.getHeaders({ 'Content-Type': 'application/json' })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show success message
                    button.textContent = 'Sent!';
                    button.style.backgroundColor = '#28a745';
                    console.log('Discord notification sent successfully:', data.message);
                    
                    // Reset button after 2 seconds
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                        button.style.backgroundColor = '';
                    }, 2000);
                } else {
                    // Show error message
                    button.textContent = 'Failed';
                    button.style.backgroundColor = '#dc3545';
                    console.error('Failed to send Discord notification:', data.message);
                    
                    // Show user-friendly error message
                    alert('Failed to send Discord notification: ' + data.message);
                    
                    // Reset button after 2 seconds
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                        button.style.backgroundColor = '';
                    }, 2000);
                }
            })
            .catch(error => {
                console.error('Error sending Discord notification:', error);
                button.textContent = 'Error';
                button.style.backgroundColor = '#dc3545';
                alert('An error occurred while sending the Discord notification.');
                
                // Reset button after 2 seconds
                setTimeout(() => {
                    button.textContent = originalText;
                    button.disabled = false;
                    button.style.backgroundColor = '';
                }, 2000);
            });
        }
    });

    document.body.addEventListener('click', function(event) {
        var clickedElement = event.target.closest('[id^="menuButton-"]');
        if (clickedElement) {
            console.log('Menu button or its child clicked');
            event.stopPropagation();

            var uuid = clickedElement.id.replace('menuButton-', '');
            var popupMenu = document.getElementById('popupMenu-' + uuid);

            // Handle both library page (.game-card) and game details page (.game-card-coverimage)
            var gameCard = clickedElement.closest('.game-card');
            var coverImage = clickedElement.closest('.game-card-coverimage');
            var parentContainer = gameCard || coverImage;

            document.querySelectorAll('.popup-menu').forEach(function(menu) {
                if (menu.id !== 'popupMenu-' + uuid) {
                    menu.style.display = 'none';
                    // Show favorite button and game status elements for other cards
                    var otherCard = menu.closest('.game-card') || menu.closest('.game-card-coverimage');
                    if (otherCard) {
                        showCardButtons(otherCard);
                    }
                }
            });

            // Close any open screenshot slideshows when opening popup menu
            if (typeof hideDetails === 'function') {
                hideDetails();
            }

            // Toggle the popup menu
            var isOpening = popupMenu.style.display !== 'block';
            popupMenu.style.display = isOpening ? 'block' : 'none';

            // Hide or show the favorite button and game status elements
            if (isOpening) {
                hideCardButtons(parentContainer);
            } else {
                showCardButtons(parentContainer);
            }
        }
    });

    // Handle "Move Library" button click
    document.body.addEventListener('click', function(event) {
        if (event.target.classList.contains('move-library')) {
            event.stopPropagation();
            
            const gameUuid = event.target.getAttribute('data-game-uuid');
            const submenuContainer = event.target.closest('.move-library-container').querySelector('.submenu-libraries');
            
            // Close any other open libraries submenu
            if (currentLibrariesSubmenu && currentLibrariesSubmenu !== submenuContainer) {
                currentLibrariesSubmenu.style.display = 'none';
            }
            
            // Toggle the submenu
            if (submenuContainer.style.display === 'none') {
                submenuContainer.style.display = 'block';
                currentLibrariesSubmenu = submenuContainer;
                
                // Show loading indicator
                const loadingElement = submenuContainer.querySelector('.loading-libraries');
                const librariesList = submenuContainer.querySelector('.libraries-list');
                loadingElement.style.display = 'block';
                librariesList.style.display = 'none';
                
                // Fetch libraries
                fetch('/api/get_libraries')
                    .then(response => response.json())
                    .then(libraries => {
                        // Hide loading, show libraries list
                        loadingElement.style.display = 'none';
                        librariesList.style.display = 'block';
                        
                        // Clear previous libraries
                        librariesList.innerHTML = '';
                        
                        // Add libraries to the submenu
                        libraries.forEach(library => {
                            const libraryItem = document.createElement('div');
                            libraryItem.className = 'library-item';
                            libraryItem.textContent = library.name;
                            libraryItem.setAttribute('data-library-uuid', library.uuid);
                            libraryItem.setAttribute('data-game-uuid', gameUuid);
                            
                            libraryItem.addEventListener('click', function(e) {
                                e.stopPropagation();
                                const targetLibraryUuid = this.getAttribute('data-library-uuid');
                                const gameUuid = this.getAttribute('data-game-uuid');
                                
                                // Confirm with the user
                                if (confirm(`Are you sure you want to move this game to the "${library.name}" library?`)) {
                                    // Send request to move the game
                                    fetch('/api/move_game_to_library', {
                                        method: 'POST',
                                        headers: CSRFUtils.getHeaders({ 'Content-Type': 'application/json' }),
                                        body: JSON.stringify({
                                            game_uuid: gameUuid,
                                            target_library_uuid: targetLibraryUuid
                                        })
                                    })
                                    .then(response => response.json())
                                    .then(data => {
                                        if (data.success) {
                                            window.location.reload();
                                        } else {
                                            alert('Error: ' + data.message);
                                        }
                                    })
                                    .catch(error => {
                                        console.error('Error moving game:', error);
                                        alert('An error occurred while moving the game.');
                                    });
                                }
                            });
                            librariesList.appendChild(libraryItem);
                        });
                    });
            } else {
                submenuContainer.style.display = 'none';
                currentLibrariesSubmenu = null;
            }
        }
    });

    // Helper functions to hide/show card buttons
    function hideCardButtons(gameCard) {
        if (!gameCard) return;

        // Handle library page buttons
        var favoriteBtn = gameCard.querySelector('.favorite-btn');
        var statusBtn = gameCard.querySelector('.game-status-btn');
        var statusBadge = gameCard.querySelector('.game-status-badge');
        var statusDropdown = gameCard.querySelector('.status-dropdown');

        // Handle game details page buttons (with -cover suffix)
        var favoriteBtnCover = gameCard.querySelector('.favorite-btn-cover');
        var statusBtnCover = gameCard.querySelector('.game-status-btn-cover');

        if (favoriteBtn) favoriteBtn.style.display = 'none';
        if (statusBtn) statusBtn.style.display = 'none';
        if (statusBadge) statusBadge.style.display = 'none';
        if (statusDropdown) statusDropdown.style.display = 'none';
        if (favoriteBtnCover) favoriteBtnCover.style.display = 'none';
        if (statusBtnCover) statusBtnCover.style.display = 'none';
    }

    function showCardButtons(gameCard) {
        if (!gameCard) return;

        // Handle library page buttons
        var favoriteBtn = gameCard.querySelector('.favorite-btn');
        var statusBtn = gameCard.querySelector('.game-status-btn');
        var statusBadge = gameCard.querySelector('.game-status-badge');

        // Handle game details page buttons (with -cover suffix)
        var favoriteBtnCover = gameCard.querySelector('.favorite-btn-cover');
        var statusBtnCover = gameCard.querySelector('.game-status-btn-cover');

        if (favoriteBtn) favoriteBtn.style.display = '';
        if (statusBtn) statusBtn.style.display = '';
        if (statusBadge) statusBadge.style.display = '';
        if (favoriteBtnCover) favoriteBtnCover.style.display = '';
        if (statusBtnCover) statusBtnCover.style.display = '';
        // Note: status dropdown should remain hidden unless explicitly opened by user
    }

    window.addEventListener('click', function() {
        document.querySelectorAll('.popup-menu').forEach(function(menu) {
            menu.style.display = 'none';
            // Show favorite button and game status elements when menu closes
            // Handle both library page (.game-card) and game details page (.game-card-coverimage)
            var gameCard = menu.closest('.game-card') || menu.closest('.game-card-coverimage');
            if (gameCard) {
                showCardButtons(gameCard);
            }
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

});
