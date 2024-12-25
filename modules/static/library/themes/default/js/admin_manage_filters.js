document.addEventListener('DOMContentLoaded', function() {
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
});
