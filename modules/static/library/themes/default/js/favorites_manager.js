document.addEventListener('DOMContentLoaded', () => {
    console.log('[FavoritesManager] Initializing...');

    const initializeFavoriteButtons = () => {
        const favoriteButtons = document.querySelectorAll('.favorite-btn');
        if (favoriteButtons.length === 0) {
            return;
        }

        const csrfToken = CSRFUtils.getToken();
        if (!csrfToken) {
            console.error('[FavoritesManager] CSRF token not found. Cannot proceed.');
            return;
        }

        favoriteButtons.forEach(button => {
            // Skip already initialized buttons
            if (button.dataset.favoriteInitialized) {
                return;
            }
            button.dataset.favoriteInitialized = 'true';

            const gameUuid = button.dataset.gameUuid;
            if (!gameUuid) {
                console.warn('[FavoritesManager] Found a favorite button without a game-uuid.');
                return;
            }

            // Set initial state from data attribute
            const isFavorite = button.dataset.isFavorite === 'true';
            updateButtonAppearance(button, isFavorite);

            // Add click handler
            button.addEventListener('click', async (e) => {
                e.preventDefault();
                e.stopPropagation();

                if (button.classList.contains('processing')) return;
                button.classList.add('processing');

                try {
                    const response = await fetch(`/api/toggle_favorite/${gameUuid}`, {
                        method: 'POST',
                        headers: CSRFUtils.getHeaders({
                            'Content-Type': 'application/json'
                        })
                    });

                    if (!response.ok) {
                        throw new Error(`Failed to toggle favorite: ${response.statusText}`);
                    }
                    const data = await response.json();

                    updateButtonAppearance(button, data.is_favorite);
                    // Update the data attribute for consistency
                    button.dataset.isFavorite = data.is_favorite;

                } catch (error) {
                    console.error('[FavoritesManager] Error toggling favorite:', error);
                } finally {
                    button.classList.remove('processing');
                }
            });
        });
    };

    const updateButtonAppearance = (button, isFavorite) => {
        const icon = button.querySelector('i');
        if (isFavorite) {
            button.classList.add('favorited');
            if (icon) icon.style.color = '#ff69b4';
        } else {
            button.classList.remove('favorited');
            if (icon) icon.style.color = 'white'; // Or your default color
        }
    };

    // Initial run
    initializeFavoriteButtons();

    // Use MutationObserver to handle dynamically added buttons (e.g., in library view with pagination)
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.addedNodes.length) {
                initializeFavoriteButtons();
            }
        });
    });

    const gamesContainer = document.getElementById('gamesContainer');
    if (gamesContainer) {
        observer.observe(gamesContainer, { childList: true, subtree: true });
    }
});
