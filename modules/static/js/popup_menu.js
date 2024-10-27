document.addEventListener('DOMContentLoaded', function() {
    
    var csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

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
                headers: {
                    'X-CSRF-Token': csrfToken
                },
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

    window.addEventListener('click', function() {
        document.querySelectorAll('.popup-menu').forEach(function(menu) {
            menu.style.display = 'none';
        });
    });

    document.body.addEventListener('click', function(event) {
        if (event.target.closest('.popup-menu')) {
            event.stopPropagation();
        }
    });

});
