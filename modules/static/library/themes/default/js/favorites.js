document.addEventListener('DOMContentLoaded', async () => {
    console.log('[Favorites] Initializing favorites functionality');

    const favoriteButtons = document.querySelectorAll('.favorite-btn');
    console.log(`[Favorites] Found ${favoriteButtons.length} favorite buttons`);

    // Add transition class to all buttons
    favoriteButtons.forEach(button => {
        button.querySelector('i').style.transition = 'color 0.3s ease';
    });

    // Get CSRF token
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (!csrfMeta) {
        console.error('[Favorites] Error: CSRF token meta tag not found. Cannot proceed.');
        return; 
    }
    const csrfToken = csrfMeta.content;

    for (const button of favoriteButtons) {
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
                button.querySelector('i').style.color = '#ff69b4';
            } else {
                console.log(`[Favorites] Game ${gameUuid} is not favorited`);
            }
        } catch (error) {
            console.error('[Favorites] Error checking initial favorite status:', error);
        }

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

                button.classList.remove('processing');
                if (toggleData.is_favorite) {
                    button.classList.add('favorited');
                    button.querySelector('i').style.color = '#ff69b4';
                } else {
                    button.classList.remove('favorited');
                    button.querySelector('i').style.color = 'white';
                }
            } catch (error) {
                console.error('[Favorites] Error toggling favorite:', error);
                button.classList.remove('processing');
            }
        });
    }
});
