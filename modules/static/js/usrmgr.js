// /static/js/usrmgr.js
document.addEventListener('DOMContentLoaded', function() {
    var userSelect = document.getElementById('user_id');
    var deleteButton = document.getElementById('delete');

    if (userSelect) {
        userSelect.addEventListener('change', function() {
            var userId = this.value;
            if (userId) {
                fetch('/get_user/' + userId)
                    .then(response => response.json())
                    .then(data => {
                        // Populate form fields with data
                        document.getElementById('name').value = data.name || '';
                        document.getElementById('email').value = data.email || '';
                        document.getElementById('role').value = data.role || '';
                        document.getElementById('state').checked = data.state || false;
                        document.getElementById('openai_api_key').value = data.openai_api_key || '';
                        document.getElementById('gcloud_api_key').value = data.gcloud_api_key || '';
                        document.getElementById('tts_engine').value = data.tts_engine || '';
                        document.getElementById('speech_enabled').checked = data.speech_enabled || false;
                        document.getElementById('quota_messages').value = data.quota_messages || 0;
                        document.getElementById('count_messages').value = data.count_messages || 0;
                        document.getElementById('country').value = data.country || '';
                        document.getElementById('about').value = data.about || '';
                    });
            }
        });
    }

    if (deleteButton) {
        deleteButton.addEventListener('click', function(event) {
            var userNameField = document.getElementById('name');
            var userName = userNameField ? userNameField.value : 'this user';
            var confirmDeletion = confirm("Euh zeker weten dat je " + userName + " wilt verwijderen?");
            if (!confirmDeletion) {
                event.preventDefault();
            }
        });
    }
});
