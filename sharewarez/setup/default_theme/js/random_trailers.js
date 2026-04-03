// Random Trailers JavaScript with Filtering
// Handles fetching and displaying random game trailers with filter support

// YouTube Player instance (global scope for API callback)
let player = null;
let isPlayerReady = false;

// Store current filter badge data for responsive rendering
let currentFilterData = {
    library: null,
    genres: [],
    themes: [],
    dateRange: null
};

// Auto-play settings
let autoplaySettings = {
    enabled: true,
    skipFirst: 0,
    skipAfter: 0
};

// Playback tracking
let playbackTimer = null;
let playedSeconds = 0;
let isPlaying = false;

// YouTube IFrame API ready callback
function onYouTubeIframeAPIReady() {
    isPlayerReady = true;
    console.log('YouTube IFrame API is ready');
}

document.addEventListener('DOMContentLoaded', function() {
    // Check if attract mode is active
    const urlParams = new URLSearchParams(window.location.search);
    const isAttractMode = urlParams.has('attract_mode');

    // DOM Elements
    const loadingState = document.getElementById('loading-state');
    const errorState = document.getElementById('error-state');
    const videoContainer = document.getElementById('video-container');
    const gameTitle = document.getElementById('game-title');
    const gameTitleLink = document.getElementById('game-title-link');
    const nextBtn = document.getElementById('next-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const errorText = document.getElementById('error-text');
    const exitAttractModeBtn = document.getElementById('exit-attract-mode-btn');

    // Modal Elements
    const settingsModal = document.getElementById('settings-modal');
    const modalClose = document.getElementById('modal-close');
    const modalCancel = document.getElementById('modal-cancel');
    const modalSave = document.getElementById('modal-save');
    const autoplayToggle = document.getElementById('autoplay-toggle');
    const skipFirstInput = document.getElementById('skip-first');
    const skipAfterInput = document.getElementById('skip-after');

    // Filter Elements
    const filterToggle = document.getElementById('filter-toggle');
    const filterPanel = document.getElementById('filter-panel');
    const toggleIcon = filterToggle.querySelector('.toggle-icon');
    const filterBadges = document.getElementById('filter-badges');
    const librarySelect = document.getElementById('library-filter');
    const genreSelect = document.getElementById('genre-filter');
    const themeSelect = document.getElementById('theme-filter');
    const dateFromInput = document.getElementById('date-from');
    const dateToInput = document.getElementById('date-to');
    const clearFiltersBtn = document.getElementById('clear-filters-btn');
    const filterStatus = document.getElementById('filter-status');

    // Load filter options first
    fetchFilterOptions();

    // Handle attract mode
    if (isAttractMode) {
        console.log('Attract mode is active');
        // Show exit button
        if (exitAttractModeBtn) {
            exitAttractModeBtn.style.display = 'block';
        }
        // Load attract mode settings from server
        loadAttractModeSettings();
    } else {
        // Load auto-play settings from localStorage
        loadSettings();
    }

    // Exit attract mode button handler
    if (exitAttractModeBtn) {
        exitAttractModeBtn.addEventListener('click', function() {
            // Try to get the stored return URL from sessionStorage
            const returnUrl = sessionStorage.getItem('attractModeReturnUrl');

            if (returnUrl) {
                // Clear the stored URL
                sessionStorage.removeItem('attractModeReturnUrl');
                console.log('Returning to previous page:', returnUrl);
                // Return to the page the user was on before attract mode
                window.location.href = returnUrl;
            } else {
                // No stored URL, go to discover page as default
                console.log('No return URL found, going to discover page');
                window.location.href = '/discover';
            }
        });
    }

    // Load initial trailer on page load
    fetchRandomTrailer();

    // Initialize badges visibility (panel starts collapsed)
    if (filterPanel.classList.contains('collapsed')) {
        filterBadges.classList.remove('hidden');
    } else {
        filterBadges.classList.add('hidden');
    }

    // Debounced window resize handler for responsive badges
    let resizeTimeout;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(function() {
            // Re-render badges with smart condensing based on new window size
            if (filterPanel.classList.contains('collapsed')) {
                renderSmartBadges();
            }
        }, 300); // 300ms debounce
    });

    // Filter panel toggle
    filterToggle.addEventListener('click', function() {
        filterPanel.classList.toggle('collapsed');
        toggleIcon.classList.toggle('rotated');

        // Toggle badge visibility
        if (filterPanel.classList.contains('collapsed')) {
            filterBadges.classList.remove('hidden');
        } else {
            filterBadges.classList.add('hidden');
        }
    });

    // Next button click handler
    nextBtn.addEventListener('click', function() {
        pauseCurrentVideo();
        fetchRandomTrailer();
    });

    // Settings button click handler
    settingsBtn.addEventListener('click', function() {
        openSettingsModal();
    });

    // Modal close handlers
    modalClose.addEventListener('click', closeSettingsModal);
    modalCancel.addEventListener('click', closeSettingsModal);

    // Click outside modal to close
    settingsModal.addEventListener('click', function(e) {
        if (e.target === settingsModal) {
            closeSettingsModal();
        }
    });

    // Modal save handler
    modalSave.addEventListener('click', function() {
        saveSettings();
        closeSettingsModal();
    });

    // Clear filters button
    clearFiltersBtn.addEventListener('click', function() {
        librarySelect.value = '';
        genreSelect.selectedIndex = -1;
        themeSelect.selectedIndex = -1;
        dateFromInput.value = '';
        dateToInput.value = '';
        updateFilterStatus();
    });

    // Update filter status when filters change
    [librarySelect, genreSelect, themeSelect, dateFromInput, dateToInput].forEach(element => {
        element.addEventListener('change', updateFilterStatus);
    });

    /**
     * Fetch available filter options from API
     */
    function fetchFilterOptions() {
        fetch('/api/trailers/filters')
            .then(response => {
                if (!response.ok) throw new Error('Failed to fetch filter options');
                return response.json();
            })
            .then(data => {
                populateLibraries(data.libraries);
                populateGenres(data.genres);
                populateThemes(data.themes);

                // Set date range placeholders if available
                if (data.date_range.min_year && data.date_range.max_year) {
                    dateFromInput.placeholder = `e.g., ${data.date_range.min_year}`;
                    dateToInput.placeholder = `e.g., ${data.date_range.max_year}`;
                    dateFromInput.min = data.date_range.min_year;
                    dateFromInput.max = data.date_range.max_year;
                    dateToInput.min = data.date_range.min_year;
                    dateToInput.max = data.date_range.max_year;
                }
            })
            .catch(error => {
                console.error('Error fetching filter options:', error);
            });
    }

    /**
     * Populate library dropdown
     */
    function populateLibraries(libraries) {
        libraries.forEach(library => {
            const option = document.createElement('option');
            option.value = library.uuid;  // Library UUID
            option.textContent = library.name;  // Library name
            librarySelect.appendChild(option);
        });
    }

    /**
     * Populate genre multi-select
     */
    function populateGenres(genres) {
        genres.forEach(genre => {
            const option = document.createElement('option');
            option.value = genre.id;
            option.textContent = genre.name;
            genreSelect.appendChild(option);
        });
    }

    /**
     * Populate theme multi-select
     */
    function populateThemes(themes) {
        themes.forEach(theme => {
            const option = document.createElement('option');
            option.value = theme.id;
            option.textContent = theme.name;
            themeSelect.appendChild(option);
        });
    }

    /**
     * Build filter query parameters from current filter state
     */
    function getFilterParams() {
        const params = new URLSearchParams();

        // Library filter
        const libraryUuid = librarySelect.value;
        if (libraryUuid) {
            params.append('library_uuid', libraryUuid);
        }

        // Genre filter (multi-select)
        const selectedGenres = Array.from(genreSelect.selectedOptions)
            .map(opt => opt.value);
        if (selectedGenres.length > 0) {
            params.append('genres', selectedGenres.join(','));
        }

        // Theme filter (multi-select)
        const selectedThemes = Array.from(themeSelect.selectedOptions)
            .map(opt => opt.value);
        if (selectedThemes.length > 0) {
            params.append('themes', selectedThemes.join(','));
        }

        // Date from filter
        const dateFrom = dateFromInput.value;
        if (dateFrom) {
            params.append('date_from', dateFrom);
        }

        // Date to filter
        const dateTo = dateToInput.value;
        if (dateTo) {
            params.append('date_to', dateTo);
        }

        return params.toString();
    }

    /**
     * Update filter status display and badges
     */
    function updateFilterStatus() {
        const activeFilters = [];

        // Store filter data for responsive badge rendering
        currentFilterData = {
            library: null,
            genres: [],
            themes: [],
            dateRange: null
        };

        // Library filter
        if (librarySelect.value) {
            const libraryText = librarySelect.options[librarySelect.selectedIndex].text;
            activeFilters.push(`Library: ${libraryText}`);
            currentFilterData.library = libraryText;
        }

        // Genre filter
        const selectedGenres = Array.from(genreSelect.selectedOptions);
        if (selectedGenres.length > 0) {
            activeFilters.push(`Genres: ${selectedGenres.length} selected`);
            currentFilterData.genres = selectedGenres.map(opt => opt.textContent);
        }

        // Theme filter
        const selectedThemes = Array.from(themeSelect.selectedOptions);
        if (selectedThemes.length > 0) {
            activeFilters.push(`Themes: ${selectedThemes.length} selected`);
            currentFilterData.themes = selectedThemes.map(opt => opt.textContent);
        }

        // Date range filter
        if (dateFromInput.value || dateToInput.value) {
            const from = dateFromInput.value || '...';
            const to = dateToInput.value || '...';
            activeFilters.push(`Years: ${from} - ${to}`);
            currentFilterData.dateRange = `${from}-${to}`;
        }

        // Update text status (in expanded panel)
        if (activeFilters.length > 0) {
            filterStatus.textContent = `Active: ${activeFilters.join(' | ')}`;
            filterStatus.style.display = 'block';
        } else {
            filterStatus.textContent = '';
            filterStatus.style.display = 'none';
        }

        // Update badges (in collapsed panel) with smart rendering
        renderSmartBadges();
    }

    /**
     * Smart badge rendering - tries to show full info, condenses if needed
     */
    function renderSmartBadges() {
        // If no filters, clear badges
        if (!currentFilterData.library &&
            currentFilterData.genres.length === 0 &&
            currentFilterData.themes.length === 0 &&
            !currentFilterData.dateRange) {
            filterBadges.innerHTML = '';
            return;
        }

        // Use requestAnimationFrame to ensure DOM is rendered before checking overflow
        requestAnimationFrame(() => {
            tryRenderAtLevel(0);
        });
    }

    /**
     * Try rendering badges at a specific condensing level
     * @param {number} level - Current condensing level to try
     */
    function tryRenderAtLevel(level) {
        const maxLevel = 4;

        // Generate and render badges for this level
        const badges = generateBadges(level);
        const badgeHTML = badges.map(badge =>
            `<span class="filter-badge">${badge}</span>`
        ).join('');

        filterBadges.innerHTML = badgeHTML;

        // Give browser time to render, then check if it fits
        requestAnimationFrame(() => {
            const overflowing = hasOverflow();

            if (overflowing && level < maxLevel) {
                // Still overflowing and we have more levels to try
                tryRenderAtLevel(level + 1);
            }
            // Otherwise, we're done (either fits or at max condensing)
        });
    }

    /**
     * Generate badge array based on condensing level
     * @param {number} level - 0 (full) to 4 (ultra condensed)
     * @returns {Array} Array of badge text strings
     */
    function generateBadges(level) {
        const badges = [];

        // Level 3: Count-only format
        if (level === 3) {
            if (currentFilterData.library) {
                badges.push(currentFilterData.library);
            }
            if (currentFilterData.genres.length > 0) {
                badges.push(`Genres: ${currentFilterData.genres.length}`);
            }
            if (currentFilterData.themes.length > 0) {
                badges.push(`Themes: ${currentFilterData.themes.length}`);
            }
            if (currentFilterData.dateRange) {
                badges.push(currentFilterData.dateRange);
            }
            return badges;
        }

        // Level 4: Ultra minimal - just counts
        if (level === 4) {
            if (currentFilterData.library) {
                // Use first word or full name if short
                const abbrev = currentFilterData.library.split(' ')[0];
                badges.push(abbrev);
            }
            if (currentFilterData.genres.length > 0) {
                badges.push(`G:${currentFilterData.genres.length}`);
            }
            if (currentFilterData.themes.length > 0) {
                badges.push(`T:${currentFilterData.themes.length}`);
            }
            if (currentFilterData.dateRange) {
                badges.push(currentFilterData.dateRange);
            }
            return badges;
        }

        // Levels 0-2: Normal condensing
        // Library - always show full
        if (currentFilterData.library) {
            badges.push(currentFilterData.library);
        }

        // Genres - condense based on level
        if (currentFilterData.genres.length > 0) {
            if (level === 0) {
                // Show all genres
                badges.push(...currentFilterData.genres);
            } else {
                // Condense to first + count
                const first = currentFilterData.genres[0];
                if (currentFilterData.genres.length === 1) {
                    badges.push(first);
                } else {
                    badges.push(`${first} +${currentFilterData.genres.length - 1}`);
                }
            }
        }

        // Themes - condense based on level
        if (currentFilterData.themes.length > 0) {
            if (level === 0 || level === 1) {
                // Show all themes (level 0 and 1)
                badges.push(...currentFilterData.themes);
            } else {
                // Condense to first + count (level 2)
                const first = currentFilterData.themes[0];
                if (currentFilterData.themes.length === 1) {
                    badges.push(first);
                } else {
                    badges.push(`${first} +${currentFilterData.themes.length - 1}`);
                }
            }
        }

        // Date range - always show full
        if (currentFilterData.dateRange) {
            badges.push(currentFilterData.dateRange);
        }

        return badges;
    }

    /**
     * Check if badges container has overflow
     * @returns {boolean} True if overflowing
     */
    function hasOverflow() {
        // Check if container has content and dimensions
        if (!filterBadges || filterBadges.children.length === 0) {
            return false;
        }

        // Force a reflow to ensure accurate measurements
        const scrollW = filterBadges.scrollWidth;
        const clientW = filterBadges.clientWidth;

        // Add small buffer (5px) to account for rendering differences and ensure we detect overflow
        const isOverflowing = scrollW > clientW + 5;

        // Debug logging (remove in production if needed)
        if (isOverflowing) {
            console.log(`Overflow detected: scrollWidth=${scrollW}, clientWidth=${clientW}`);
        }

        return isOverflowing;
    }

    /**
     * Fetch a random game trailer from the API with current filters
     */
    function fetchRandomTrailer() {
        // Show loading state
        showLoading();

        // Build URL with filter parameters
        const filterParams = getFilterParams();
        const url = `/api/trailers/random${filterParams ? '?' + filterParams : ''}`;

        // Fetch random trailer from API
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.message || 'Failed to fetch trailer');
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.has_videos) {
                    // Update UI with trailer data
                    displayTrailer(data);
                } else {
                    showError(data.message);
                }
            })
            .catch(error => {
                console.error('Error fetching trailer:', error);
                showError(error.message || 'Unable to load trailers. Try adjusting your filters.');
            });
    }

    /**
     * Extract YouTube video ID from URL
     * @param {string} url - YouTube video URL (watch or embed format)
     * @returns {string} Video ID
     */
    function getYouTubeVideoId(url) {
        // Handle different YouTube URL formats
        const patterns = [
            /youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)/,  // watch?v=VIDEO_ID
            /youtube\.com\/embed\/([a-zA-Z0-9_-]+)/,    // embed/VIDEO_ID
            /youtu\.be\/([a-zA-Z0-9_-]+)/               // youtu.be/VIDEO_ID
        ];

        for (const pattern of patterns) {
            const match = url.match(pattern);
            if (match && match[1]) {
                return match[1];
            }
        }

        console.error('Could not extract video ID from URL:', url);
        return null;
    }

    /**
     * Display the trailer in the UI
     * @param {Object} data - Trailer data from API
     */
    function displayTrailer(data) {
        // Reset playback tracking for new video
        stopPlaybackTimer();

        // Extract video ID from URL
        const videoId = getYouTubeVideoId(data.video_url);

        if (!videoId) {
            showError('Invalid video URL format');
            return;
        }

        // Update game title in header
        gameTitle.textContent = data.game_name;

        // Update game title link
        gameTitleLink.href = `/game_details/${data.game_uuid}`;

        // Hide loading, show video container
        hideLoading();
        showVideoContainer();

        // Wait for YouTube API to be ready, then create/update player
        const initializePlayer = () => {
            if (typeof YT === 'undefined' || typeof YT.Player === 'undefined') {
                console.log('YouTube API not ready yet, waiting...');
                setTimeout(initializePlayer, 100);
                return;
            }

            // Create or update YouTube player
            if (player === null) {
                // Clear the container and create new player
                const playerContainer = document.getElementById('trailer-player');
                playerContainer.innerHTML = '';

                player = new YT.Player('trailer-player', {
                    height: '100%',
                    width: '100%',
                    videoId: videoId,
                    playerVars: {
                        'autoplay': 1,
                        'rel': 0,  // Don't show related videos from other channels
                        'modestbranding': 1  // Minimal YouTube branding
                    },
                    events: {
                        'onStateChange': onPlayerStateChange
                    }
                });
            } else {
                // Update existing player with new video
                if (typeof player.loadVideoById === 'function') {
                    player.loadVideoById(videoId);
                } else {
                    console.error('Player not fully initialized, recreating...');
                    // Destroy old player if it exists
                    if (player && typeof player.destroy === 'function') {
                        player.destroy();
                    }
                    player = null;
                    initializePlayer();
                }
            }
        };

        initializePlayer();
    }

    /**
     * Handle YouTube player state changes
     * @param {Object} event - YouTube player state change event
     */
    function onPlayerStateChange(event) {
        // YT.PlayerState values:
        // -1 (unstarted)
        //  0 (ended)
        //  1 (playing)
        //  2 (paused)
        //  3 (buffering)
        //  5 (video cued)

        if (event.data === YT.PlayerState.PLAYING) {
            // Video started playing
            isPlaying = true;

            // Apply skip-first setting if this is the first time playing
            if (playedSeconds === 0 && autoplaySettings.skipFirst > 0) {
                console.log(`Skipping first ${autoplaySettings.skipFirst} seconds`);
                player.seekTo(autoplaySettings.skipFirst, true);
            }

            // Start tracking play time
            startPlaybackTimer();
        } else if (event.data === YT.PlayerState.PAUSED) {
            // Video paused
            isPlaying = false;
        } else if (event.data === YT.PlayerState.ENDED) {
            // Video ended
            console.log('Video ended');
            stopPlaybackTimer();

            // Auto-play next trailer if enabled
            if (autoplaySettings.enabled) {
                console.log('Auto-play enabled, loading next trailer...');
                fetchRandomTrailer();
            } else {
                console.log('Auto-play disabled');
            }
        }
    }

    /**
     * Show loading state
     */
    function showLoading() {
        loadingState.style.display = 'flex';
        errorState.style.display = 'none';
        videoContainer.style.display = 'none';
    }

    /**
     * Hide loading state
     */
    function hideLoading() {
        loadingState.style.display = 'none';
    }

    /**
     * Show video container
     */
    function showVideoContainer() {
        videoContainer.style.display = 'block';
        errorState.style.display = 'none';
    }

    /**
     * Show error message
     * @param {string} message - Error message to display
     */
    function showError(message) {
        errorText.textContent = message;
        loadingState.style.display = 'none';
        videoContainer.style.display = 'none';
        errorState.style.display = 'flex';
    }

    /**
     * Pause current video when loading new one
     * This helps with autoplay and prevents overlapping audio
     */
    function pauseCurrentVideo() {
        if (player && player.stopVideo) {
            player.stopVideo();
        }
        stopPlaybackTimer();
    }

    /**
     * Load settings from localStorage
     */
    function loadSettings() {
        const saved = localStorage.getItem('trailerAutoplaySettings');
        if (saved) {
            try {
                autoplaySettings = JSON.parse(saved);
            } catch (e) {
                console.error('Error loading settings:', e);
            }
        }
    }

    /**
     * Load attract mode settings from server
     */
    async function loadAttractModeSettings() {
        try {
            const response = await fetch('/api/attract-mode/settings');
            if (!response.ok) {
                console.error('Failed to load attract mode settings');
                // Fall back to localStorage
                loadSettings();
                return;
            }

            const data = await response.json();
            if (data && data.settings) {
                // Apply autoplay settings
                if (data.settings.autoplay) {
                    autoplaySettings = data.settings.autoplay;
                }

                // Apply filter settings
                if (data.settings.filters) {
                    const filters = data.settings.filters;

                    // Apply library filter
                    if (filters.library_uuid && librarySelect) {
                        librarySelect.value = filters.library_uuid;
                    }

                    // Apply genre filters
                    if (filters.genres && filters.genres.length > 0 && genreSelect) {
                        Array.from(genreSelect.options).forEach(option => {
                            option.selected = filters.genres.includes(parseInt(option.value));
                        });
                    }

                    // Apply theme filters
                    if (filters.themes && filters.themes.length > 0 && themeSelect) {
                        Array.from(themeSelect.options).forEach(option => {
                            option.selected = filters.themes.includes(parseInt(option.value));
                        });
                    }

                    // Apply date range
                    if (filters.date_from && dateFromInput) {
                        dateFromInput.value = filters.date_from;
                    }
                    if (filters.date_to && dateToInput) {
                        dateToInput.value = filters.date_to;
                    }

                    // Update filter data and badges
                    updateFilterData();
                    renderSmartBadges();
                }

                console.log('Attract mode settings loaded:', data.settings);
            }
        } catch (error) {
            console.error('Error loading attract mode settings:', error);
            // Fall back to localStorage
            loadSettings();
        }
    }

    /**
     * Save settings to localStorage and optionally to server for attract mode
     */
    async function saveSettings() {
        autoplaySettings.enabled = autoplayToggle.checked;
        autoplaySettings.skipFirst = parseInt(skipFirstInput.value) || 0;
        autoplaySettings.skipAfter = parseInt(skipAfterInput.value) || 0;

        localStorage.setItem('trailerAutoplaySettings', JSON.stringify(autoplaySettings));
        console.log('Settings saved:', autoplaySettings);

        // If user is authenticated, also save to server as user override
        // This allows user preferences to persist forever and override admin defaults
        try {
            // Get current filter data
            const filterData = {
                library_uuid: librarySelect.value || null,
                genres: Array.from(genreSelect.selectedOptions).map(opt => parseInt(opt.value)),
                themes: Array.from(themeSelect.selectedOptions).map(opt => parseInt(opt.value)),
                date_from: dateFromInput.value ? parseInt(dateFromInput.value) : null,
                date_to: dateToInput.value ? parseInt(dateToInput.value) : null
            };

            // Get CSRF token
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

            const response = await fetch('/api/attract-mode/user-override', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    autoplay: autoplaySettings,
                    filters: filterData
                })
            });

            if (response.ok) {
                const result = await response.json();
                console.log('User preferences saved to server:', result.message);
            } else {
                const error = await response.json();
                console.warn('Failed to save to server:', error.message);
            }
        } catch (error) {
            console.log('Could not save to server (user may not be authenticated):', error);
        }
    }

    /**
     * Open settings modal
     */
    function openSettingsModal() {
        // Populate modal with current settings
        autoplayToggle.checked = autoplaySettings.enabled;
        skipFirstInput.value = autoplaySettings.skipFirst;
        skipAfterInput.value = autoplaySettings.skipAfter;

        settingsModal.style.display = 'flex';
    }

    /**
     * Close settings modal
     */
    function closeSettingsModal() {
        settingsModal.style.display = 'none';
    }

    /**
     * Start playback timer to track play time
     */
    function startPlaybackTimer() {
        if (playbackTimer) return; // Already running

        playbackTimer = setInterval(function() {
            if (isPlaying) {
                playedSeconds++;

                // Check if we should skip to next
                if (autoplaySettings.skipAfter > 0 && playedSeconds >= autoplaySettings.skipAfter) {
                    console.log(`Played for ${playedSeconds}s, skipping to next...`);
                    stopPlaybackTimer();
                    fetchRandomTrailer();
                }
            }
        }, 1000); // Check every second
    }

    /**
     * Stop and reset playback timer
     */
    function stopPlaybackTimer() {
        if (playbackTimer) {
            clearInterval(playbackTimer);
            playbackTimer = null;
        }
        playedSeconds = 0;
        isPlaying = false;
    }
});
