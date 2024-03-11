function debounce(func, wait, immediate) {
    var timeout;
    return function() {
        var context = this, args = arguments;
        var later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        var callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
}

const slideshowIntervals = {};

function startSlideshowForGameUuid(gameUuid) {
    if (slideshowIntervals[gameUuid]) {
        clearTimeout(slideshowIntervals[gameUuid]);
    }

    let slideIndex = 0;
    const slides = document.querySelectorAll(`#details-${gameUuid} .screenshot-slide`);
    if (slides.length === 0) return;

    const showSlides = () => {
        slides.forEach(slide => slide.style.display = "none");
        slideIndex++;
        if (slideIndex > slides.length) slideIndex = 1;
        slides[slideIndex - 1].style.display = "block";
        slideshowIntervals[gameUuid] = setTimeout(showSlides, 2000); 
    };
    showSlides();
}

function clearSlideshowForGameUuid(gameUuid) {
    if (slideshowIntervals[gameUuid]) {
        clearTimeout(slideshowIntervals[gameUuid]);
        delete slideshowIntervals[gameUuid]; 
    }
}

const showDetailsDebounced = debounce(function(element, gameUuid) {
    
    const detailsDiv = document.getElementById(`details-${gameUuid}`);
    if (!detailsDiv) {
        return;
    }

    // prevent flickering and overlapping animations
    detailsDiv.innerHTML = '';
    clearSlideshowForGameUuid(gameUuid);

    fetch(`/api/game_screenshots/${gameUuid}`)
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error('Network response was not ok.');
            }
        })
        .then(screenshots => {
            let detailsHtml = '<div class="slideshow-container"><div class="slides-wrapper">';
            screenshots.forEach((url, index) => {
                detailsHtml += `<div class="screenshot-slide" style="display: ${index === 0 ? 'block' : 'none'};"><img src="${url}" class="screenshot"></div>`;
            });
            detailsHtml += '</div></div>'; // End slideshow container

            detailsHtml += `<div class="game-info-box" style="animation: fadein 0.5s;">
                                <div class="game-name">${element.dataset.name}</div>
                                <div class="game-size chip file-size-chip">${element.dataset.size}</div>
                                <div>${element.dataset.genres.split(', ').map(genre => `<span class="chip">${genre}</span>`).join('')}</div>
                            </div>`;

            detailsDiv.innerHTML = detailsHtml;

            startSlideshowForGameUuid(gameUuid);
            detailsDiv.classList.remove('hidden');
        })
        .catch(error => {
            console.error('Fetch error:', error);
        });
        adjustDetailsSizeForGameUuid(gameUuid); 
}, 300); // 300 ms

function adjustDetailsSizeForGameUuid(gameUuid) {
    const gameCard = document.querySelector(`.game-card[data-uuid="${gameUuid}"]`);
    if (!gameCard) return;

    const coverImage = gameCard.querySelector('img.game-cover');
    if (!coverImage) return;

    const detailsDiv = document.getElementById(`details-${gameUuid}`);
    if (!detailsDiv) return;

    const coverWidth = coverImage.offsetWidth;
    const coverHeight = coverImage.offsetHeight;

    detailsDiv.style.width = `${coverWidth}px`;
    detailsDiv.style.height = `${coverHeight}px`;
}

const debouncedResize = debounce(function() {
    document.querySelectorAll('.popup-game-details').forEach(details => {
        const gameUuid = details.id.replace('details-', '');
        adjustDetailsSizeForGameUuid(gameUuid);
    });
}, 250);

window.addEventListener('resize', debouncedResize);

function showDetails(element, gameUuid) {
    const detailsDiv = document.getElementById(`details-${gameUuid}`);
    if (!detailsDiv) {
        return;
    }

    showDetailsDebounced(element, gameUuid);

    // Calculate the space needed for the popup
    const popupWidth = 300; // Assuming a fixed width for the popup
    const viewportWidth = window.innerWidth;
    const gameCardRect = element.getBoundingClientRect();
    const spaceOnRight = viewportWidth - gameCardRect.right;

    // Check if there's enough space on the right, if not, adjust to show on the left
    if (spaceOnRight < popupWidth + 20) { // 20px for some margin
        detailsDiv.style.left = 'auto'; // Reset left property
        detailsDiv.style.right = '105%'; // Position to the left of the game card
    } else {
        detailsDiv.style.right = 'auto'; // Reset right property
        detailsDiv.style.left = '105%'; // Default position to the right of the game card
    }

    // Existing logic to show game details
    showDetailsDebounced(element, gameUuid);
}

function hideDetails() {
    const detailsElements = document.querySelectorAll('.popup-game-details');
    detailsElements.forEach(details => {
        const gameUuid = details.id.replace('details-', '');
        clearSlideshowForGameUuid(gameUuid); 
        details.classList.add('hidden');
    });
}

