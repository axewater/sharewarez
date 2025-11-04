// game_status_manager.js
// Manages game completion status UI and API interactions

console.log('[GameStatusManager] ===== SCRIPT LOADED =====');
console.log('[GameStatusManager] Script execution started, waiting for DOMContentLoaded...');

document.addEventListener('DOMContentLoaded', () => {
    console.log('[GameStatusManager] ===== INITIALIZING =====');
    console.log('[GameStatusManager] DOMContentLoaded event fired');

    // Check if play status feature is disabled - if no buttons exist, don't proceed
    const statusButtons = document.querySelectorAll('.game-status-btn');
    if (statusButtons.length === 0) {
        console.log('[GameStatusManager] Play status feature is disabled or no status buttons found. Skipping initialization.');
        return;
    }

    // Status configuration matching models.py
    const STATUS_CONFIG = {
        'unplayed': {
            icon: 'fa-box',
            color: '#808080',
            label: 'Unplayed'
        },
        'unfinished': {
            icon: 'fa-gamepad',
            color: '#4A90E2',
            label: 'Unfinished'
        },
        'beaten': {
            icon: 'fa-flag-checkered',
            color: '#50C878',
            label: 'Beaten'
        },
        'completed': {
            icon: 'fa-trophy',
            color: '#FFD700',
            label: 'Completed'
        },
        'null': {
            icon: 'fa-ban',
            color: '#DC3545',
            label: "Won't Play"
        },
        '': {
            icon: 'fa-circle',
            color: '#808080',
            label: 'No Status',
            empty: true
        }
    };

    // Initialize all status buttons on the page
    const initializeStatusButtons = () => {
        console.log('[GameStatusManager] initializeStatusButtons() called');
        console.log('[GameStatusManager] Found status buttons:', statusButtons.length);

        const csrfToken = CSRFUtils.getToken();
        if (!csrfToken) {
            console.error('[GameStatusManager] CSRF token not found. Cannot proceed.');
            return;
        }
        console.log('[GameStatusManager] CSRF token found:', csrfToken.substring(0, 10) + '...');

        statusButtons.forEach((button, index) => {
            console.log(`[GameStatusManager] Processing button ${index + 1}:`, button);
            // Skip already initialized buttons
            if (button.dataset.statusInitialized) {
                return;
            }
            button.dataset.statusInitialized = 'true';

            const gameUuid = button.dataset.gameUuid;
            console.log(`[GameStatusManager] Button ${index + 1} game UUID:`, gameUuid);
            if (!gameUuid) {
                console.warn('[GameStatusManager] Found a status button without a game-uuid.');
                return;
            }

            // Set initial state from data attribute
            const currentStatus = button.dataset.currentStatus || '';
            console.log(`[GameStatusManager] Button ${index + 1} current status:`, currentStatus);
            updateButtonAppearance(button, currentStatus);
            console.log(`[GameStatusManager] Button ${index + 1} appearance updated`);

            // Add click handler to toggle dropdown
            button.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                const dropdown = button.nextElementSibling;
                if (dropdown && dropdown.classList.contains('status-dropdown')) {
                    // Toggle this dropdown
                    const isVisible = dropdown.style.display === 'block';

                    // Close all other dropdowns first
                    document.querySelectorAll('.status-dropdown').forEach(d => {
                        d.style.display = 'none';
                    });

                    dropdown.style.display = isVisible ? 'none' : 'block';
                }
            });
        });

        // Initialize dropdown option click handlers
        const dropdownOptions = document.querySelectorAll('.status-dropdown-option');
        dropdownOptions.forEach(option => {
            if (option.dataset.optionInitialized) {
                return;
            }
            option.dataset.optionInitialized = 'true';

            option.addEventListener('click', async (e) => {
                e.preventDefault();
                e.stopPropagation();

                const dropdown = option.closest('.status-dropdown');
                const gameUuid = dropdown.dataset.gameUuid;
                const newStatus = option.dataset.status;
                const button = dropdown.previousElementSibling;

                // Hide dropdown
                dropdown.style.display = 'none';

                // Update status
                await setGameStatus(button, gameUuid, newStatus);
            });
        });

        console.log(`[GameStatusManager] Initialized ${statusButtons.length} status buttons`);
    };

    // Update button appearance based on status
    const updateButtonAppearance = (button, status) => {
        const icon = button.querySelector('i');
        const config = STATUS_CONFIG[status] || STATUS_CONFIG[''];

        if (icon) {
            // Remove all possible status icon classes
            icon.className = '';
            icon.classList.add('fas', config.icon);
            icon.style.color = config.color;

            // Add opacity for empty status
            if (config.empty) {
                icon.style.opacity = '0.4';
            } else {
                icon.style.opacity = '1';
            }
        }

        // Update data attribute
        button.dataset.currentStatus = status || '';
        button.title = config.label;
    };

    // Set game status via API
    const setGameStatus = async (button, gameUuid, newStatus) => {
        const icon = button.querySelector('i');
        const originalIconClass = icon.className;
        const originalColor = icon.style.color;

        try {
            // Show loading spinner
            icon.className = 'fas fa-circle-notch fa-spin';
            icon.style.color = '#4A90E2';
            button.classList.add('processing');

            const response = await fetch(`/api/set_game_status/${gameUuid}`, {
                method: 'POST',
                headers: CSRFUtils.getHeaders({
                    'Content-Type': 'application/json'
                }),
                body: JSON.stringify({ status: newStatus })
            });

            if (!response.ok) {
                throw new Error(`Failed to set status: ${response.statusText}`);
            }

            const data = await response.json();

            if (data.success) {
                // Update button appearance
                updateButtonAppearance(button, data.status);

                // Show success animation
                await showSuccessAnimation(button);

                // Show toast notification
                $.notify(data.message, "success");

                return data;
            } else {
                throw new Error(data.error || 'Failed to set status');
            }
        } catch (error) {
            console.error('[GameStatusManager] Error setting status:', error);

            // Revert appearance
            icon.className = originalIconClass;
            icon.style.color = originalColor;

            $.notify("Failed to update status", "error");
            throw error;
        } finally {
            button.classList.remove('processing');
        }
    };

    // Show success animation (checkmark)
    const showSuccessAnimation = async (button) => {
        return new Promise((resolve) => {
            const icon = button.querySelector('i');
            const originalClass = icon.className;
            const originalColor = icon.style.color;

            // Show checkmark
            icon.className = 'fas fa-check';
            icon.style.color = '#50C878';

            // Restore after 1 second
            setTimeout(() => {
                icon.className = originalClass;
                icon.style.color = originalColor;
                resolve();
            }, 1000);
        });
    };

    // Close all dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.game-status-btn') && !e.target.closest('.status-dropdown')) {
            document.querySelectorAll('.status-dropdown').forEach(dropdown => {
                dropdown.style.display = 'none';
            });
        }
    });

    // Close dropdowns when popup menus open/close
    document.addEventListener('click', (e) => {
        if (e.target.closest('[id^="menuButton-"]')) {
            document.querySelectorAll('.status-dropdown').forEach(dropdown => {
                dropdown.style.display = 'none';
            });
        }
    });

    // Initial run
    initializeStatusButtons();

    // Use MutationObserver to handle dynamically added buttons (e.g., in library view with pagination)
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.addedNodes.length) {
                initializeStatusButtons();
            }
        });
    });

    const gamesContainer = document.getElementById('gamesContainer');
    if (gamesContainer) {
        observer.observe(gamesContainer, { childList: true, subtree: true });
    }

    // Also observe the game details container
    const gameDetailsContainer = document.querySelector('.glass-panel-gamecard');
    if (gameDetailsContainer) {
        observer.observe(gameDetailsContainer, { childList: true, subtree: true });
    }

    console.log('[GameStatusManager] Ready');
});
