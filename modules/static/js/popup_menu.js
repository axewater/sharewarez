document.addEventListener('DOMContentLoaded', function() {
    
    var csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // Adjusted for dynamic content using event delegation
    document.body.addEventListener('click', function(event) {
        if (event.target.classList.contains('delete-game')) {
            event.stopPropagation();
            const gameUuid = event.target.getAttribute('data-game-uuid');
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
                window.location.href = '/library';
            })
            .catch(error => {
                console.error('There has been a problem with your fetch operation:', error);
            });
        }

        //delete-game-from-disk

        if (event.target.classList.contains('delete-game-from-disk')) {
            event.stopPropagation();
            const gameUuid = event.target.getAttribute('data-game-uuid');
            alert('We are deleting from disk... beware');
            console.log(`Deleting folder from disk UUID: ${gameUuid}`);

            const jsonData = {
                game_uuid: gameUuid
            };

            console.log(jsonData);

            fetch(`/delete_full_game`, {
                method: 'POST',
                headers: {
                    'X-CSRF-Token': csrfToken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(jsonData)
            })
            .then(response => {
                if (!response.ok) {
                    console.log(response.text());
                    throw new Error('Network response was not ok.');
                }
                return response.text();
            })
            .then(() => {
                console.log('Game deleted successfully');
                window.location.href = '/library';
            })
            .catch(error => {
                console.error('There has been a problem with your fetch operation:', error);
            });
        }


    });
     

    document.body.addEventListener('click', function(event) {
        // Check if the click is on the menu button or any of its descendants
        var clickedElement = event.target.closest('[id^="menuButton-"]');
        if (clickedElement) {
            console.log('Menu button or its child clicked');
            event.stopPropagation();
    
            var uuid = clickedElement.id.replace('menuButton-', '');
            var popupMenu = document.getElementById('popupMenu-' + uuid);
    
            // Toggle the display of the popup menu for the clicked button
            document.querySelectorAll('.popup-menu').forEach(function(menu) {
                if (menu.id !== 'popupMenu-' + uuid) {
                    menu.style.display = 'none';
                }
            });
    
            popupMenu.style.display = popupMenu.style.display === 'block' ? 'none' : 'block';
        }
    })


    // Close popup menus when clicking anywhere else on the window
    window.addEventListener('click', function() {
        
        document.querySelectorAll('.popup-menu').forEach(function(menu) {
            menu.style.display = 'none';
        });
    });

    // Prevent menu close when clicking inside the menu
    document.body.addEventListener('click', function(event) {
        if (event.target.closest('.popup-menu')) {
            event.stopPropagation();
        }
    });
});
