document.addEventListener('DOMContentLoaded', function() {
    const addFilterModal = new bootstrap.Modal(document.getElementById('addFilterModal'));
    
    // Add click handlers to all delete buttons
    document.querySelectorAll('.admin_manage_filters-remove-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Show confirmation dialog
            if (confirm('Are you sure you want to remove this filter? This action cannot be undone.')) {
                // If confirmed, proceed with the original href
                window.location.href = this.getAttribute('href');
            }
        });
    });
    
    // Handle filter form submission
    document.getElementById('saveFilter').addEventListener('click', function() {
        const form = document.getElementById('addFilterForm');
        const formData = new FormData(form);
        
        fetch(window.location.pathname, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content,
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: new URLSearchParams(formData)
        })
        .then(response => {
            if (response.ok) {
                addFilterModal.hide();
                window.location.reload();
            } else {
                throw new Error('Failed to add filter');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to add filter. Please try again.');
        });
    });
    
    // Clear form when modal is hidden
    document.getElementById('addFilterModal').addEventListener('hidden.bs.modal', function () {
        document.getElementById('addFilterForm').reset();
    });
});
