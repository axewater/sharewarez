// Global variables for modal state
let modalState = {
    originalScrollPosition: 0,
    slideIndex: 1,
    modalOpen: false,
    bodyOverflowOriginal: ''
};

function openModal(clickedIndex) {
    modalState.originalScrollPosition = window.scrollY;
    modalState.slideIndex = clickedIndex || 1;
    modalState.modalOpen = true;
     
    const modal = document.getElementById("myModal");
    modal.style.display = "block";
    document.body.classList.add('modal-open');
    
    // Prevent background scrolling
    modalState.bodyOverflowOriginal = document.body.style.overflow;
    document.body.style.position = 'fixed';
    document.body.style.top = `-${modalState.originalScrollPosition}px`;
     
    showSlides(modalState.slideIndex);
    addEscapeKeyListener();
    
    // Add click outside listener
    modal.addEventListener('click', handleModalClick);
}

function handleModalClick(event) {
    if (event.target.id === "myModal") {
        closeModal();
    }
}

function cleanupModal() {
    const modal = document.getElementById("myModal");
    modal.removeEventListener('click', handleModalClick);
}

function closeModal() {
    cleanupModal();
    document.getElementById("myModal").style.display = "none";
    document.body.classList.remove('modal-open');
    
    // Restore body position and scrolling
    removeEscapeKeyListener();
    document.body.style.position = '';
    document.body.style.overflow = modalState.bodyOverflowOriginal;
    document.body.style.width = '';
    window.scrollTo(0, modalState.originalScrollPosition);
    
    modalState.modalOpen = false;
}

function addEscapeKeyListener() {
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && modalState.modalOpen) {
            closeModal();
        }
    });
}

function removeEscapeKeyListener() {
    document.removeEventListener('keydown', function(event) {
        if (event.key === 'Escape' && modalState.modalOpen) {
        }
    });
}

function plusSlides(n) {
    showSlides(modalState.slideIndex += n);
}

function showSlides(n) {
    var i;
    var slides = document.getElementsByClassName("mySlides");
    
    // Ensure slides exist
    if (!slides || slides.length === 0) {
        return;
    }
 
    if (n > slides.length) {
        modalState.slideIndex = 1; 
    }    
    if (n < 1) {
        modalState.slideIndex = slides.length;
    }
    
    // Hide all slides
    for (i = 0; i < slides.length; i++) {
        slides[i].style.display = "none";
    }

    // Safely display the current slide
    if (slides[modalState.slideIndex - 1]) {
        slides[modalState.slideIndex - 1].style.display = "flex";
    }
    
    // Add keyboard navigation
    document.onkeydown = function(e) {
        if (!modalState.modalOpen) return;
        
        if (e.key === "ArrowLeft") {
            plusSlides(-1);
        } else if (e.key === "ArrowRight") {
            plusSlides(1);
        }
    };
}


// DOMContentLoaded event listener for "Read More" functionality
document.addEventListener("DOMContentLoaded", function() {
    // Ensure modal is not displayed on page load
    const modal = document.getElementById("myModal");
    if (modal) {
        modal.style.display = "none";
        modalState.modalOpen = false;
    }
    
    // Read More functionality
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
