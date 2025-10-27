// Random Trailers JavaScript with Filtering
// Handles fetching and displaying random game trailers with filter support

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const loadingState = document.getElementById('loading-state');
    const errorState = document.getElementById('error-state');
    const videoContainer = document.getElementById('video-container');
    const trailerIframe = document.getElementById('trailer-iframe');
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
     * Display the trailer in the UI
     * @param {Object} data - Trailer data from API
     */
    function displayTrailer(data) {
        // Update iframe src with video URL
        trailerIframe.src = data.video_url;

        // Update game name
        gameName.textContent = data.game_name;

        // Update game details button link
        gameDetailsBtn.href = `/game_details/${data.game_uuid}`;

        // Hide loading, show video container
        hideLoading();
        showVideoContainer();
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
        trailerIframe.src = '';
    }
});
