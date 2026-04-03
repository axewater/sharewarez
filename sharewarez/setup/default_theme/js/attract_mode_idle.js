// Site-wide Attract Mode Idle Detection
// Tracks user activity and redirects to trailers page when idle

(function() {
    'use strict';

    // State management
    let attractModeSettings = null;
    let idleTimer = null;
    let idleSeconds = 0;
    let isEnabled = false;
    let idleTimeout = 60; // default 60 seconds

    // Check if we're already on the trailers page in attract mode
    const currentPath = window.location.pathname;
    const urlParams = new URLSearchParams(window.location.search);
    const isInAttractMode = currentPath === '/trailers' && urlParams.has('attract_mode');

    // Don't initialize idle detection if already in attract mode
    if (isInAttractMode) {
        return;
    }

    // Initialize attract mode
    init();

    async function init() {
        try {
            // Fetch attract mode settings from server
            const response = await fetch('/api/attract-mode/settings');
            if (!response.ok) {
                console.log('Attract mode settings not available');
                return;
            }

            attractModeSettings = await response.json();

            if (!attractModeSettings || !attractModeSettings.enabled) {
                console.log('Attract mode is disabled');
                return;
            }

            isEnabled = true;
            idleTimeout = attractModeSettings.idle_timeout || 60;

            // Set up event listeners for user activity
            setupActivityListeners();

            // Start the idle timer
            startIdleTimer();

        } catch (error) {
            console.error('Error initializing attract mode:', error);
        }
    }

    function setupActivityListeners() {
        // Events that indicate user activity
        const activityEvents = [
            'mousedown',
            'mousemove',
            'keypress',
            'scroll',
            'touchstart',
            'click'
        ];

        // Add event listeners
        activityEvents.forEach(eventType => {
            document.addEventListener(eventType, resetIdleTimer, true);
        });
    }

    function startIdleTimer() {
        // Check idle status every second
        idleTimer = setInterval(() => {
            idleSeconds++;

            // Debug logging (can be removed in production)
            if (idleSeconds % 10 === 0) {
                console.log(`Idle for ${idleSeconds}s (threshold: ${idleTimeout}s)`);
            }

            // Check if idle timeout reached
            if (idleSeconds >= idleTimeout) {
                activateAttractMode();
            }
        }, 1000);
    }

    function resetIdleTimer() {
        if (!isEnabled) {
            return;
        }

        idleSeconds = 0;
    }

    function activateAttractMode() {
        console.log('Activating attract mode...');

        // Stop the idle timer
        if (idleTimer) {
            clearInterval(idleTimer);
            idleTimer = null;
        }

        // Remove event listeners to prevent interference
        const activityEvents = [
            'mousedown',
            'mousemove',
            'keypress',
            'scroll',
            'touchstart',
            'click'
        ];

        activityEvents.forEach(eventType => {
            document.removeEventListener(eventType, resetIdleTimer, true);
        });

        // Store current page URL so we can return to it later
        const currentUrl = window.location.href;
        sessionStorage.setItem('attractModeReturnUrl', currentUrl);
        console.log('Stored return URL:', currentUrl);

        // Redirect to trailers page with attract mode flag
        window.location.href = '/trailers?attract_mode=true';
    }

    // Expose a method to manually disable attract mode (for debugging)
    window.disableAttractMode = function() {
        isEnabled = false;
        if (idleTimer) {
            clearInterval(idleTimer);
            idleTimer = null;
        }
        console.log('Attract mode disabled');
    };

    // Expose a method to check current idle time (for debugging)
    window.getIdleTime = function() {
        return {
            idleSeconds: idleSeconds,
            idleTimeout: idleTimeout,
            isEnabled: isEnabled
        };
    };

})();
