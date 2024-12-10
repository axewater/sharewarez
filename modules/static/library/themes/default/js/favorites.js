document.addEventListener('DOMContentLoaded', async () => {
    console.log('[Favorites] Initializing favorites functionality');

    const favoriteButtons = document.querySelectorAll('.favorite-btn');
    console.log(`[Favorites] Found ${favoriteButtons.length} favorite buttons`);

    // Get CSRF token
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (!csrfMeta) {
        console.error('[Favorites] Error: CSRF token meta tag not found. Cannot proceed.');
        return; 
    }
    const csrfToken = csrfMeta.content;

    for (const button of favoriteButtons) {
        button.classList.add('processing');
        const gameUuid = button.dataset.gameUuid;
        console.log(`[Favorites] Setting up favorite button for game UUID: ${gameUuid}`);

        // Check initial favorite status
        try {
            const response = await fetch(`/check_favorite/${gameUuid}`);
            if (!response.ok) {
                throw new Error(`Failed to check favorite status: ${response.statusText}`);
            }
            const data = await response.json();
            console.log(`[Favorites] Initial status check for ${gameUuid}:`, data);
            if (data.is_favorite) {
                button.classList.add('favorited');
                console.log(`[Favorites] Game ${gameUuid} is favorited`);
            } else {
                console.log(`[Favorites] Game ${gameUuid} is not favorited`);
            }
        } catch (error) {
            console.error('[Favorites] Error checking initial favorite status:', error);
        }

        button.classList.remove('processing');
        // Add click handler to toggle favorite
        button.addEventListener('click', async () => {
            console.log(`[Favorites] Button clicked for game ${gameUuid}`);
            console.log(`[Favorites] CSRF Token: ${csrfToken.substring(0, 10)}...`);

            button.classList.add('processing');

            try {
                const toggleResponse = await fetch(`/toggle_favorite/${gameUuid}`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/json'
                    }
                });

                if (!toggleResponse.ok) {
                    throw new Error(`Failed to toggle favorite: ${toggleResponse.statusText}`);
                }

                const toggleData = await toggleResponse.json();
                console.log(`[Favorites] Server response for ${gameUuid}:`, toggleData);

                if (toggleData.is_favorite) {
                    button.classList.add('favorited');
                    console.log(`[Favorites] Added favorite class for ${gameUuid}`);
                } else {
                    button.classList.remove('favorited');
                    console.log(`[Favorites] Removed favorite class for ${gameUuid}`);
                }
            } catch (error) {
                console.error('[Favorites] Error toggling favorite:', error);
            } finally {
                button.classList.remove('processing');
            }
        });
    }
});
