document.addEventListener('DOMContentLoaded', function() {
        // Retrieve CSRF token from meta tag
    var csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    document.querySelectorAll('.delete-game').forEach(button => {
        button.addEventListener('click', function(event) {
            event.stopPropagation(); // Prevent the click from being immediately closed by window event
            const gameUuid = this.getAttribute('data-game-uuid');
            console.log(`Deleting game UUID: ${gameUuid}`); // Log the game UUID for debugging

            fetch(`/delete_game/${gameUuid}`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: {} // Since your Flask route might not explicitly require a request body, this is just a placeholder
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok.');
                }
                return response.text(); // Assuming the response is not JSON but a redirect or simple message
            })
            .then(() => {
                console.log('Game deleted successfully');
                window.location.href = '/browse_games'; // Redirect to the browse games page or handle as needed
            })
            .catch(error => {
                console.error('There has been a problem with your fetch operation:', error);
            });
        });
    });

    var menuButtons = document.querySelectorAll('[id^="menuButton-"]');
    menuButtons.forEach(function(button) {
        
        var uuid = button.id.replace('menuButton-', '');
        var popupMenu = document.getElementById('popupMenu-' + uuid);

        button.addEventListener('click', function(event) {
            console.log('Menu button clicked'); // Log when menu button is clicked
            event.stopPropagation(); // Prevent the click from being immediately closed by window event
            
            // Close all popup menus before opening the clicked one
            document.querySelectorAll('.popup-menu').forEach(function(menu) {
                if (menu.id !== 'popupMenu-' + uuid) { // Check if it's not the menu to open
                    menu.style.display = 'none';
                }
            });

            // Toggle the display of the clicked menu
            popupMenu.style.display = popupMenu.style.display === 'block' ? 'none' : 'block';
        });
    });

    // Close the popup menus if the user clicks outside of them
    window.addEventListener('click', function() {
        console.log('Window clicked'); // Log when window is clicked
        document.querySelectorAll('.popup-menu').forEach(function(menu) {
            menu.style.display = 'none';
        });
    });
});
