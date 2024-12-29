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
});