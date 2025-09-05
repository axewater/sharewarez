// Wait for document to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if DataTable is already initialized
    if (!$.fn.DataTable.isDataTable('#logsTable')) {
        // Initialize DataTables with custom styling for log levels
        const logsTable = $('#logsTable').DataTable({
            order: [[0, 'desc']],
            pageLength: 50,
            dom: '<"top"f>rt<"bottom"lip><"clear">',
            language: {
                search: "_INPUT_",
                searchPlaceholder: "Search logs..."
            },
            createdRow: function(row, data, dataIndex) {
                // Get the level from the third column (index 2)
                const level = $(data[2]).text().toLowerCase();
                
                // Add appropriate classes based on log level
                if (level === 'error') {
                    $(row).addClass('log-level-error');
                } else if (level === 'warning') {
                    $(row).addClass('log-level-warning');
                } else if (level === 'information') {
                    $(row).addClass('log-level-information');
                }
            }
        });
    }

    // Clear logs functionality
    const clearLogsBtn = document.getElementById('clearLogsBtn');
    const clearLogsModal = document.getElementById('clearLogsModal');
    const clearLogsForm = document.getElementById('clearLogsForm');
    
    if (clearLogsBtn && clearLogsModal && clearLogsForm) {
        // Show modal when clear button is clicked
        clearLogsBtn.addEventListener('click', function() {
            clearLogsModal.style.display = 'block';
        });

        // Close modal functions
        function closeClearModal() {
            clearLogsModal.style.display = 'none';
        }

        // Close button
        const closeButton = clearLogsModal.querySelector('.close-button');
        if (closeButton) {
            closeButton.addEventListener('click', closeClearModal);
        }

        // Cancel button
        const cancelButton = clearLogsModal.querySelector('.clear-cancel');
        if (cancelButton) {
            cancelButton.addEventListener('click', closeClearModal);
        }

        // Click outside modal to close
        clearLogsModal.addEventListener('click', function(event) {
            if (event.target === clearLogsModal) {
                closeClearModal();
            }
        });

        // Handle form submission
        clearLogsForm.addEventListener('submit', function(event) {
            event.preventDefault();
            
            const formData = new FormData(clearLogsForm);
            const csrfToken = formData.get('csrf_token');

            // Disable the button to prevent double-clicks
            const confirmButton = clearLogsForm.querySelector('.clear-confirm');
            const originalText = confirmButton.textContent;
            confirmButton.disabled = true;
            confirmButton.textContent = 'Clearing...';

            // Make AJAX request to clear logs
            fetch('/admin/api/system_logs/clear', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Close modal and redirect to main logs page
                    closeClearModal();
                    window.location.href = '/admin/system_logs';
                } else {
                    alert('Error clearing logs: ' + (data.error || 'Unknown error'));
                    // Re-enable button
                    confirmButton.disabled = false;
                    confirmButton.textContent = originalText;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error clearing logs: Network error');
                // Re-enable button
                confirmButton.disabled = false;
                confirmButton.textContent = originalText;
            });
        });
    }
});