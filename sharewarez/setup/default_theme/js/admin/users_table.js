$(document).ready(function() {
    $('#usersTable').DataTable({
        responsive: true,
        pageLength: 25,
        order: [[1, 'asc']], // Sort by username by default
        dom: '<"top"lBf>rt<"bottom"ip><"clear">',
        buttons: [
            'copy', 'csv', 'excel', 'pdf', 'print'
        ],
        language: {
            search: "_INPUT_",
            searchPlaceholder: "Search users...",
            lengthMenu: "Show _MENU_ users per page",
            info: "Showing _START_ to _END_ of _TOTAL_ users",
            infoEmpty: "Showing 0 to 0 of 0 users",
            infoFiltered: "(filtered from _MAX_ total users)"
        },
        columnDefs: [
            {
                targets: 0, // Avatar column
                orderable: false,
                width: '50px'
            },
            {
                targets: -1, // Actions column
                orderable: false,
                searchable: false
            }
        ],
        initComplete: function() {
            // Add role filter dropdown
            this.api().columns(4).every(function() {
                var column = this;
                var select = $('<select class="form-select form-select-sm"><option value="">All Roles</option></select>')
                    .appendTo($('.top'))
                    .on('change', function() {
                        var val = $.fn.dataTable.util.escapeRegex($(this).val());
                        column.search(val ? '^'+val+'$' : '', true, false).draw();
                    });
                
                column.data().unique().sort().each(function(d) {
                    select.append('<option value="'+d+'">'+d+'</option>');
                });
            });
        }
    });
});
