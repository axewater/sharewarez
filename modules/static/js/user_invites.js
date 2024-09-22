function copyToClipboard(buttonElement, textToCopy) {
    // Copy text to clipboard
    navigator.clipboard.writeText(textToCopy).then(() => {
        // Change button text to "COPIED!"
        const originalText = buttonElement.textContent;
        buttonElement.textContent = 'COPIED!';
        
        // Wait for 5 seconds, then revert the button text
        setTimeout(() => {
            buttonElement.textContent = originalText;
        }, 5000);
    }).catch(err => {
        console.error('Failed to copy: ', err);
    });
}

function deleteInvite(token) {
    if (confirm('Are you sure you want to delete this invite?')) {
        fetch('/delete_invite/' + token, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.getElementById('csrf_token').textContent
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Failed to delete invite: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while deleting the invite.');
        });
    }
}
