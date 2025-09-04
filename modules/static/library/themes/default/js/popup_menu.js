document.addEventListener('DOMContentLoaded', function() {
    
    let currentLibrariesSubmenu = null;
    var csrfToken = CSRFUtils.getToken();

    // Adjusted for dynamic content using event delegation
    document.body.addEventListener('click', function(event) {
        // Handling deletion of a game (not from disk)
        if (event.target.classList.contains('delete-game')) {
            event.stopPropagation();
            const gameUuid = event.target.getAttribute('data-game-uuid');
			const game_library_uuid = event.target.getAttribute('data-game-library-uuid');
			const urlParams = new URLSearchParams(window.location.search);
			const library_uuid = urlParams.get('library_uuid');
            console.log(`Deleting game UUID: ${gameUuid}`);

            fetch(`/delete_game/${gameUuid}`, {
                method: 'POST',
                headers: CSRFUtils.getHeaders(),
                body: {}
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok.');
                }
                return response.text();
            })
            .then(() => {
                console.log('Game deleted successfully');
				if (library_uuid) {
					window.location.href = '/library?library_uuid=' + library_uuid;
				}
				else if (game_library_uuid) {
					window.location.href = '/library?library_uuid=' + game_library_uuid;
				}
				else {
					window.location.href = '/library';
				}
            })
            .catch(error => {
                console.error('There has been a problem with your fetch operation:', error);
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
    
            document.querySelectorAll('.popup-menu').forEach(function(menu) {
                if (menu.id !== 'popupMenu-' + uuid) {
                    menu.style.display = 'none';
                }
            });
    
            popupMenu.style.display = popupMenu.style.display === 'block' ? 'none' : 'block';
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

});
