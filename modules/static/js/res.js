document.addEventListener('DOMContentLoaded', function() {
    // Trigger modal open
    document.querySelectorAll('.delete-game-from-disk').forEach(button => {
        
        button.addEventListener('click', function(event) {
            console.log('delete-game-from-disk clicked');
            event.preventDefault(); // Stop the form from submitting immediately

            document.getElementById('deleteGameUuid').value = button.getAttribute('data-game-uuid');
            document.getElementById('deleteGameModal').style.display = 'block';
        });
    });

    // Close modal
    document.querySelector('.close-button').addEventListener('click', () => {
        console.log('close-button clicked');
        document.getElementById('deleteGameModal').style.display = 'none';
    });

    // Cancel button in modal
    document.querySelector('.delete-cancel').addEventListener('click', () => {
        console.log('delete-cancel clicked');
        document.getElementById('deleteGameModal').style.display = 'none';
    });

    // Handle form submit
    document.getElementById('deleteGameForm').addEventListener('submit', function(event) {
        console.log('deleteGameForm submitted');
        event.preventDefault();
        const gameUuid = document.getElementById('deleteGameUuid').value;
        const csrftoken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        console.log('deleting gameUuid:', gameUuid);
        fetch(`/delete_full_game`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken,
            },
            body: JSON.stringify({ game_uuid: gameUuid })
        })
        .then(response => {
            if(response.ok) {
                return response.json();
            }
            throw new Error('Network response was not ok.');
        })
        .then(data => {
            // console.log(data); // Print out all response data
            window.location.href = '/library';
        })
        .catch(error => {
            console.error('Error:', error);
        });
    });
});