document.addEventListener('DOMContentLoaded', function() {
    const editModal = new bootstrap.Modal(document.getElementById('editUserModal'));
    const deleteModal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
    let userToDelete = null;

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
            password: document.getElementById('editPassword').value
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
