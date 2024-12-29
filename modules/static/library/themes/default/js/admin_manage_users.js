document.addEventListener('DOMContentLoaded', function() {
    const editModal = new bootstrap.Modal(document.getElementById('editUserModal'));
    const addModal = new bootstrap.Modal(document.getElementById('addUserModal'));
    const deleteModal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
    let userToDelete = null;

    // Add new user button click handler
    document.getElementById('addNewUserBtn').addEventListener('click', function() {
        document.getElementById('addUserForm').reset();
        document.getElementById('usernameAvailabilityFeedback').textContent = '';
        addModal.show();
    });

    // Username availability check
    document.getElementById('newUsername').addEventListener('blur', function() {
        const username = this.value;
        if (username) {
            fetch('/api/check_username', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                },
                body: JSON.stringify({ username: username })
            })
            .then(response => response.json())
            .then(data => {
                const feedback = document.getElementById('usernameAvailabilityFeedback');
                if (data.exists) {
                    feedback.textContent = 'Username already taken';
                    feedback.style.color = 'red';
                } else {
                    feedback.textContent = 'Username available';
                    feedback.style.color = 'green';
                }
            });
        }
    });

    // Save new user button handler
    document.getElementById('saveNewUser').addEventListener('click', function() {
        const username = document.getElementById('newUsername').value;
        const email = document.getElementById('newEmail').value;
        const password = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('newConfirmPassword').value;

        if (password !== confirmPassword) {
            alert('Passwords do not match');
            return;
        }

        const userData = {
            username: username,
            email: email,
            password: password,
            is_email_verified: true,
            state: true,
            role: 'user'
        };

        fetch('/admin/api/user/0', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify(userData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                addModal.hide();
                window.location.reload();
            } else {
                alert(data.message || 'Error creating user');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error creating user');
        });
    });

    // Edit user button click handler
    document.querySelectorAll('.edit-user').forEach(button => {
        button.addEventListener('click', function() {
            const userId = this.dataset.userId;
            fetchUserDetails(userId);
        });
    });

    // Delete user button click handler
    document.querySelectorAll('.delete-user').forEach(button => {
        button.addEventListener('click', function() {
            userToDelete = this.dataset.userId;
            deleteModal.show();
        });
    });

    // Confirm delete button handler
    document.getElementById('confirmDelete').addEventListener('click', function() {
        if (userToDelete) {
            deleteUser(userToDelete);
        }
    });

    // Save changes button handler
    document.getElementById('saveUserChanges').addEventListener('click', function() {
        const userId = document.getElementById('editUserId').value;
        const userData = {
            email: document.getElementById('editEmail').value,
            role: document.getElementById('editRole').value,
            state: document.getElementById('editState').checked,
            is_email_verified: document.getElementById('editEmailVerified').checked,
            password: document.getElementById('editPassword').value,
            about: document.getElementById('editAbout').value
        };
        updateUser(userId, userData);
    });

    // Fetch user details function
    function fetchUserDetails(userId) {
        fetch(`/admin/api/user/${userId}`)
            .then(response => response.json())
            .then(data => {
                document.getElementById('editUserId').value = userId;
                document.getElementById('editEmail').value = data.email;
                document.getElementById('editRole').value = data.role;
                document.getElementById('editState').checked = data.state;
                document.getElementById('editEmailVerified').checked = data.is_email_verified;
                document.getElementById('editAbout').value = data.about || '';
                document.getElementById('editPassword').value = '';
                editModal.show();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error fetching user details');
            });
    }

    // Update user function
    function updateUser(userId, userData) {
        fetch(`/admin/api/user/${userId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify(userData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                editModal.hide();
                window.location.reload();
            } else {
                alert(data.message || 'Error updating user');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error updating user');
        });
    }

    // Delete user function
    function deleteUser(userId) {
        fetch(`/admin/api/user/${userId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                deleteModal.hide();
                window.location.reload();
            } else {
                alert(data.message || 'Error deleting user');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error deleting user');
        });
    }
});
