document.addEventListener('DOMContentLoaded', () => {
    console.log('[LibFavs] Initializing library favorites functionality');

    // Function to initialize favorite buttons for newly loaded content
    const initializeFavoriteButtons = () => {
        const favoriteButtons = document.querySelectorAll('.favorite-btn');
        console.log(`[LibFavs] Found ${favoriteButtons.length} favorite buttons`);

        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (!csrfMeta) {
            console.error('[LibFavs] Error: CSRF token meta tag not found');
            return;
        }
        const csrfToken = csrfMeta.content;

        favoriteButtons.forEach(async (button) => {
            // Use the pre-computed favorite status from the server
            if (button.dataset.isFavorite === 'true') {
                button.classList.add('favorited');
                button.querySelector('i').style.color = '#ff69b4';
            }

            // Add click handler
            button.addEventListener('click', async (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                if (button.classList.contains('processing')) return;
                button.classList.add('processing');

                try {
                    const gameUuid = button.dataset.gameUuid;
                    const response = await fetch(`/api/toggle_favorite/${gameUuid}`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'Content-Type': 'application/json'
                        }
                    });

                    if (!response.ok) throw new Error(`Failed to toggle favorite: ${response.statusText}`);
                    const data = await response.json();

                    if (data.is_favorite) {
                        button.classList.add('favorited');
                        button.querySelector('i').style.color = '#ff69b4';
                    } else {
                        button.classList.remove('favorited');
                        button.querySelector('i').style.color = 'white';
                    }
                } catch (error) {
                    console.error('[LibFavs] Error toggling favorite:', error);
                } finally {
                    button.classList.remove('processing');
                }
            });
        });
    };

    // Initialize favorites for initial page load
    initializeFavoriteButtons();

    // Create a MutationObserver to watch for new content
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.addedNodes.length) {
                initializeFavoriteButtons();
            }
        });
    });

    // Start observing the games container for changes
    const gamesContainer = document.getElementById('gamesContainer');
    if (gamesContainer) {
        observer.observe(gamesContainer, { childList: true, subtree: true });
    }
});
