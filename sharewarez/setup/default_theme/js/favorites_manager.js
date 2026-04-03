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

                // Check if we're on the favorites page
                const isFavoritesPage = window.location.pathname === '/favorites';
                const isFavorite = button.dataset.isFavorite === 'true';
                
                // If on favorites page and trying to remove favorite, show confirmation modal
                if (isFavoritesPage && isFavorite) {
                    const gameName = button.dataset.gameName;
                    showRemoveFavoriteModal(gameUuid, gameName, button);
                    return;
                }

                // Normal toggle behavior for other pages
                await toggleFavorite(button, gameUuid);
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

    const toggleFavorite = async (button, gameUuid) => {
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

            return data;
        } catch (error) {
            console.error('[FavoritesManager] Error toggling favorite:', error);
            throw error;
        } finally {
            button.classList.remove('processing');
        }
    };

    const showRemoveFavoriteModal = (gameUuid, gameName, button) => {
        const modal = document.getElementById('removeFavoriteModal');
        const gameNameSpan = document.getElementById('gameNameToRemove');
        
        if (!modal || !gameNameSpan) {
            console.error('[FavoritesManager] Modal elements not found');
            return;
        }

        gameNameSpan.textContent = gameName;
        modal.style.display = 'block';

        // Store references for the confirmation handler
        modal.dataset.gameUuid = gameUuid;
        modal.dataset.buttonRef = button.dataset.gameUuid; // Use UUID as reference
    };

    const handleModalConfirmation = async (gameUuid) => {
        const modal = document.getElementById('removeFavoriteModal');
        const button = document.querySelector(`[data-game-uuid="${gameUuid}"]`);
        
        if (!button) {
            console.error('[FavoritesManager] Button not found for game UUID:', gameUuid);
            return;
        }

        try {
            await toggleFavorite(button, gameUuid);
            
            // Update the favorite counter (decrease by 1)
            const counterSpan = button.closest('.favorite-count').querySelector('.favorite-number');
            if (counterSpan) {
                const currentCount = parseInt(counterSpan.textContent) || 0;
                counterSpan.textContent = Math.max(0, currentCount - 1);
            }

            // Remove the game card with fade out animation
            const gameCard = button.closest('.game-card-container');
            if (gameCard) {
                gameCard.style.transition = 'opacity 0.3s ease';
                gameCard.style.opacity = '0';
                setTimeout(() => {
                    gameCard.remove();
                    
                    // Check if this was the last favorite
                    const remainingCards = document.querySelectorAll('.game-card-container');
                    if (remainingCards.length === 0) {
                        const container = document.querySelector('.discovery-favorites-games');
                        if (container) {
                            container.innerHTML = '<p>You haven\'t added any favorites yet!</p>';
                        }
                    }
                }, 300);
            }
        } catch (error) {
            console.error('[FavoritesManager] Error removing favorite:', error);
        } finally {
            modal.style.display = 'none';
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

    // Initialize modal event listeners
    const modal = document.getElementById('removeFavoriteModal');
    if (modal) {
        // Close button
        const closeButton = modal.querySelector('.close-button');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                modal.style.display = 'none';
            });
        }

        // Cancel button
        const cancelButton = modal.querySelector('.cancel-remove');
        if (cancelButton) {
            cancelButton.addEventListener('click', () => {
                modal.style.display = 'none';
            });
        }

        // Confirm button
        const confirmButton = modal.querySelector('.confirm-remove');
        if (confirmButton) {
            confirmButton.addEventListener('click', async () => {
                const gameUuid = modal.dataset.gameUuid;
                if (gameUuid) {
                    await handleModalConfirmation(gameUuid);
                }
            });
        }

        // Close modal when clicking outside
        window.addEventListener('click', (event) => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    }
});
