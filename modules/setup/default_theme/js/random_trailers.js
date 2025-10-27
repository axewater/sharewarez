// Random Trailers JavaScript with Filtering
// Handles fetching and displaying random game trailers with filter support

// YouTube Player instance (global scope for API callback)
let player = null;
let isPlayerReady = false;

// YouTube IFrame API ready callback
function onYouTubeIframeAPIReady() {
    isPlayerReady = true;
    console.log('YouTube IFrame API is ready');
}

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const loadingState = document.getElementById('loading-state');
    const errorState = document.getElementById('error-state');
    const videoContainer = document.getElementById('video-container');
    const gameName = document.getElementById('game-name');
    const nextBtn = document.getElementById('next-btn');
    const gameDetailsBtn = document.getElementById('game-details-btn');
    const errorText = document.getElementById('error-text');

    // Filter Elements
    const filterToggle = document.getElementById('filter-toggle');
    const filterPanel = document.getElementById('filter-panel');
    const toggleIcon = filterToggle.querySelector('.toggle-icon');
    const platformSelect = document.getElementById('platform-filter');
    const genreSelect = document.getElementById('genre-filter');
    const themeSelect = document.getElementById('theme-filter');
    const dateFromInput = document.getElementById('date-from');
    const dateToInput = document.getElementById('date-to');
    const clearFiltersBtn = document.getElementById('clear-filters-btn');
    const filterStatus = document.getElementById('filter-status');

    // Load filter options first
    fetchFilterOptions();

    // Load initial trailer on page load
    fetchRandomTrailer();

    // Filter panel toggle
    filterToggle.addEventListener('click', function() {
        filterPanel.classList.toggle('collapsed');
        toggleIcon.classList.toggle('rotated');
    });

    // Next button click handler
    nextBtn.addEventListener('click', function() {
        pauseCurrentVideo();
        fetchRandomTrailer();
    });

    // Clear filters button
    clearFiltersBtn.addEventListener('click', function() {
        platformSelect.value = '';
        genreSelect.selectedIndex = -1;
        themeSelect.selectedIndex = -1;
        dateFromInput.value = '';
        dateToInput.value = '';
        updateFilterStatus();
    });

    // Update filter status when filters change
    [platformSelect, genreSelect, themeSelect, dateFromInput, dateToInput].forEach(element => {
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
                populatePlatforms(data.platforms);
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
     * Populate platform dropdown
     */
    function populatePlatforms(platforms) {
        platforms.forEach(platform => {
            const option = document.createElement('option');
            option.value = platform.name;  // Enum member name (e.g., "PCWIN")
            option.textContent = platform.display_name;  // Display value (e.g., "PC Windows")
            platformSelect.appendChild(option);
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

        // Platform filter
        const platform = platformSelect.value;
        if (platform) {
            params.append('platform', platform);
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
     * Update filter status display
     */
    function updateFilterStatus() {
        const activeFilters = [];

        if (platformSelect.value) {
            // Get the display text (user-friendly name) from the selected option
            const platformText = platformSelect.options[platformSelect.selectedIndex].text;
            activeFilters.push(`Platform: ${platformText}`);
        }

        const selectedGenres = Array.from(genreSelect.selectedOptions);
        if (selectedGenres.length > 0) {
            activeFilters.push(`Genres: ${selectedGenres.length} selected`);
        }

        const selectedThemes = Array.from(themeSelect.selectedOptions);
        if (selectedThemes.length > 0) {
            activeFilters.push(`Themes: ${selectedThemes.length} selected`);
        }

        if (dateFromInput.value || dateToInput.value) {
            const from = dateFromInput.value || '...';
            const to = dateToInput.value || '...';
            activeFilters.push(`Years: ${from} - ${to}`);
        }

        if (activeFilters.length > 0) {
            filterStatus.textContent = `Active: ${activeFilters.join(' | ')}`;
            filterStatus.style.display = 'block';
        } else {
            filterStatus.textContent = '';
            filterStatus.style.display = 'none';
        }
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
        // Extract video ID from URL
        const videoId = getYouTubeVideoId(data.video_url);

        if (!videoId) {
            showError('Invalid video URL format');
            return;
        }

        // Update game name
        gameName.textContent = data.game_name;

        // Update game details button link
        gameDetailsBtn.href = `/game_details/${data.game_uuid}`;

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
        // YT.PlayerState.ENDED = 0
        if (event.data === YT.PlayerState.ENDED) {
            console.log('Video ended, loading next trailer...');
            // Auto-play next trailer when current one ends
            fetchRandomTrailer();
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
    }
});
