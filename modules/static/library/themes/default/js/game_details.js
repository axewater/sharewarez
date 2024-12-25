// Modal functionality
let originalScrollPosition = 0;
let modalOpen = false;

function openModal() {
    // Store original scroll position
    originalScrollPosition = window.scrollY;

    // Reset scroll position before showing modal
    window.scrollTo(0, 0);
    modalOpen = true;

    // Show modal
    const modal = document.getElementById("myModal");
    modal.style.display = "block";

    // Prevent body scrolling
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    document.getElementById("myModal").style.display = "none";
    document.body.style.overflow = 'auto';
    modalOpen = false;
    // Restore original scroll position
    window.scrollTo(0, originalScrollPosition);
}

var slideIndex = 1;
showSlides(slideIndex);

function plusSlides(n) {
    showSlides(slideIndex += n);
}

function showSlides(n) {
    var i;
    var slides = document.getElementsByClassName("mySlides");
    if (slides.length === 0) {
        return;  // No slides, exit early
    }
    
    if (n > slides.length) {
        slideIndex = 1;
    }    
    if (n < 1) {
        slideIndex = slides.length;
    }
    
    // Hide all slides
    for (i = 0; i < slides.length; i++) {
        slides[i].style.display = "none";
    }

    // Safely display the current slide
    if (slides[slideIndex - 1]) {
        slides[slideIndex - 1].style.display = "block";
    }
}


// DOMContentLoaded event listener for "Read More" functionality
document.addEventListener("DOMContentLoaded", function() {
    var readMoreLink = document.querySelector('.read-more-link');
    var summaryModal = document.getElementById('summaryModal');

    // Only if readMoreLink exists
    if (readMoreLink) {
        var summarySpan = document.querySelector('.summary-close');
        var fullSummary = document.querySelector('.summary-full');
        
        if (fullSummary) {
            fullSummary = fullSummary.textContent;

            readMoreLink.onclick = function() {
                summaryModal.style.display = "block";
                document.querySelector('.summary-modal-text').textContent = fullSummary;
                return false;
            }
        }

        summarySpan.onclick = function() {
            summaryModal.style.display = "none";
        }

        window.onclick = function(event) {
            if (event.target == summaryModal) {
                summaryModal.style.display = "none";
            }
        }
    }
});

// Handle modal cleanup for Updates & Extras modal
document.addEventListener('DOMContentLoaded', function() {
    const extrasModal = document.getElementById('extrasModal');
    let modalScrollPos = 0;

    if (extrasModal) {
        extrasModal.addEventListener('show.bs.modal', function () {
            // Store current scroll position
            modalScrollPos = window.scrollY;
            
            // Reset scroll position and prevent body scrolling
            window.scrollTo(0, 0);
            document.body.style.overflow = 'hidden';
        });

        extrasModal.addEventListener('hidden.bs.modal', function () {
            // Clean up modal
            const modalBackdrops = document.querySelectorAll('.modal-backdrop');
            modalBackdrops.forEach(backdrop => backdrop.remove());
            
            // Remove modal-open class from body
            document.body.classList.remove('modal-open');
            
            // Reset body styles
            document.body.style.paddingRight = '';
            
            // Restore scrolling and position
            document.body.style.overflow = 'auto';
            window.scrollTo(0, modalScrollPos);
            modalScrollPos = 0;
        });
    }
});
