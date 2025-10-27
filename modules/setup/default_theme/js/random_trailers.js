// Random Trailers JavaScript
// Handles fetching and displaying random game trailers

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

    // Load initial trailer on page load
    fetchRandomTrailer();

    // Next button click handler
    nextBtn.addEventListener('click', function() {
        fetchRandomTrailer();
    });

    /**
     * Fetch a random game trailer from the API
     */
    function fetchRandomTrailer() {
        // Show loading state
        showLoading();

        // Fetch random trailer from API
        fetch('/api/trailers/random')
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
                showError(error.message || 'Unable to load trailers. Please try again later.');
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

    // Pause video before fetching new one
    nextBtn.addEventListener('click', function() {
        pauseCurrentVideo();
    }, true);
});
