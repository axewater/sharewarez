// /static/js/usrmgr.js
document.addEventListener('DOMContentLoaded', function() {
    var userSelect = document.getElementById('user_id');
    var deleteButton = document.getElementById('delete');

    if (userSelect) {
        userSelect.addEventListener('change', function() {
            var userId = this.value;
            if (userId) {
                fetch('/get_user/' + userId)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Network response was not ok');
                        }
                        return response.json();
                    })
                    .then(data => {
                        // Populate form fields with data
                        document.getElementById('name').value = data.name || '';
                        document.getElementById('email').value = data.email || '';
                        document.getElementById('role').value = data.role || '';
                        document.getElementById('state').checked = data.state || false;
                        document.getElementById('is_email_verified').checked = data.is_email_verified || false;
                        document.getElementById('about').value = data.about || '';                    })
                    .catch(error => console.error('There has been a problem with your fetch operation:', error));

                fetch('/get_user/' + userId)
                    .then(response => response.json())
                    .then(data => {
                        
                    });
            }
        });
    }

    if (deleteButton) {
        deleteButton.addEventListener('click', function(event) {
            var userNameField = document.getElementById('name');
            var userName = userNameField ? userNameField.value : 'this user';
            var confirmDeletion = confirm("Remove " + userName + " from your pirate crew?");
            if (!confirmDeletion) {
                event.preventDefault();
            }
        });
    }
});
