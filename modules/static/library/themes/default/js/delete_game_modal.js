document.addEventListener('DOMContentLoaded', function() {
    const deleteModal = document.getElementById('deleteGameModal');
    if (!deleteModal) return;

    // Function to close the modal
    function closeModal() {
        deleteModal.style.display = 'none';
    }

    // Use event delegation for dynamically added buttons
    document.body.addEventListener('click', function(event) {
        if (event.target.matches('.trigger-delete-modal')) {
            event.preventDefault();
            const gameUuid = event.target.getAttribute('data-game-uuid');
            const deleteGameUuidInput = document.getElementById('deleteGameUuid');
            if (deleteGameUuidInput) {
                deleteGameUuidInput.value = gameUuid;
            }
            deleteModal.style.display = 'block';
        }
    });

    // Close button event listener
    const closeButton = deleteModal.querySelector('.close-button');
    if (closeButton) {
        closeButton.addEventListener('click', function(event) {
            event.preventDefault();
            closeModal();
        });
    }

    // Cancel button event listener
    const cancelButton = deleteModal.querySelector('.delete-cancel');
    if (cancelButton) {
        cancelButton.addEventListener('click', function(event) {
            event.preventDefault();
            closeModal();
        });
    }

    // Click outside modal to close
    deleteModal.addEventListener('click', function(event) {
        if (event.target === deleteModal) {
            closeModal();
        }
    });

    // Escape key to close modal
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && deleteModal.style.display === 'block') {
            closeModal();
        }
    });

    // Form submission handler
    const deleteForm = document.getElementById('deleteGameForm');
    if (deleteForm) {
        deleteForm.addEventListener('submit', function(event) {
            event.preventDefault();
            const deleteGameUuidInput = document.getElementById('deleteGameUuid');
            if (!deleteGameUuidInput) {
                console.error('Delete game UUID input not found');
                return;
            }
            
            const gameUuid = deleteGameUuidInput.value;
            if (!gameUuid) {
                console.error('No game UUID provided');
                return;
            }

            fetch(`/delete_full_game`, {
                method: 'POST',
                headers: CSRFUtils.getHeaders({
                    'Content-Type': 'application/json'
                }),
                body: JSON.stringify({ game_uuid: gameUuid })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    $.notify(data.message, "success");
                    // Optionally remove the game card from the DOM or reload the page
                    window.location.reload();
                } else {
                    $.notify(data.message, "error");
                }
                closeModal();
            })
            .catch(error => {
                console.error('Error:', error);
                $.notify("An error occurred while deleting the game.", "error");
                closeModal();
            });
        });
    }
});