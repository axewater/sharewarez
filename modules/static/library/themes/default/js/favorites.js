document.addEventListener('DOMContentLoaded', function() {
    // Initialize favorite buttons
    const favoriteButtons = document.querySelectorAll('.favorite-btn');
    
    favoriteButtons.forEach(button => {
        const gameUuid = button.dataset.gameUuid;
        
        // Check initial favorite status
        fetch(`/check_favorite/${gameUuid}`)
            .then(response => response.json())
            .then(data => {
                if (data.is_favorite) {
                    button.classList.add('favorited');
                }
            });

        // Add click handler
        button.addEventListener('click', function() {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
            
            button.classList.add('processing');
            
            fetch(`/toggle_favorite/${gameUuid}`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                button.classList.remove('processing');
                if (data.is_favorite) {
                    button.classList.add('favorited');
                } else {
                    button.classList.remove('favorited');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                button.classList.remove('processing');
            });
        });
    });
});
