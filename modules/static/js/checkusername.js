let initialUsername = document.getElementById('username').value;
let timeout = null;

document.getElementById('username').addEventListener('input', function() {
  clearTimeout(timeout);  // If there's a timeout pending, cancel it
  const username = this.value;
  // If the username has not changed, no need to check availability
  if (username === initialUsername) {
    console.log('username unchanged')
    return;
  }

  // Wait for 500ms of inactivity before sending the request
  timeout = setTimeout(function() {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    fetch('/api/check_username', {
      method: 'POST',
      body: JSON.stringify({
        username: username
      }),
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      credentials: 'same-origin'
    })
    .then(response => {
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      return response.json();
    })
    .then(data => {
      let usernameCheckResultDiv = document.getElementById('usernameAvailabilityFeedback');
      if (data.exists) {
        usernameCheckResultDiv.textContent = "Username not available";
        usernameCheckResultDiv.style.color = "red";
        document.getElementById('createUserForm').querySelector('button[type="submit"]').disabled = true;
      } else {
        usernameCheckResultDiv.textContent = "Username available";
        usernameCheckResultDiv.style.color = "green";
        document.getElementById('createUserForm').querySelector('button[type="submit"]').disabled = false;
      }
    })
    .catch((error) => {
      console.error('Error:', error);
      let usernameCheckResultDiv = document.getElementById('usernameAvailabilityFeedback');
      usernameCheckResultDiv.textContent = "Error checking username availability";
      usernameCheckResultDiv.style.color = "orange";
    });
  }, 500);
});