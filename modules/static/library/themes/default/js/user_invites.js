function copyToClipboard(textToCopy) {
    // Use the full URL that's already in the textToCopy parameter
    const buttonElement = event.target;
    
    // Copy text to clipboard
    navigator.clipboard.writeText(textToCopy).then(() => {
        // Store original text and change to "COPIED!"
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
        const csrfToken = CSRFUtils.getToken();
        fetch('/delete_invite/' + token, {
            method: 'POST',
            headers: CSRFUtils.getHeaders({ 'Content-Type': 'application/json' }),
            credentials: 'same-origin'
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
