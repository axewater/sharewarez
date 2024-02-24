$(document).ready(function() {
    $(document).on('keypress', function(e) {
        if (!$("input, textarea").is(":focus")) {
            $('#searchModal').modal('show');
            $('#searchInput').focus();
        }
    });

    $('#searchModal').on('shown.bs.modal', function() {
        console.log("Search modal shown");
        $('#searchInput').focus();
    });

    $('#searchInput').on('input', function() {
        var query = $(this).val();
        // Debounce this function to avoid excessive AJAX calls
        fetchSearchResults(query);
        console.log(`Search query: ${query}`);
    });


    $('#searchResults').on('click', '.search-result', function() {
        console.log("Search result clicked");
        var gameUuid = $(this).attr('data-game-uuid'); // Slightly changed from .data('game-uuid') for debugging
        console.log("Navigating to UUID:", gameUuid); // Debugging line to ensure UUID is captured
        window.location.href = '/game_details/' + gameUuid;
    });
});

function fetchSearchResults(query) {
    if (query.length < 2) { // Minimum query length
        $('#searchResults').empty();
        return;
    }

    // AJAX call to server to fetch search results
    $.ajax({
        url: '/api/search', // Your search API endpoint
        method: 'GET',
        data: { query: query },
        success: function(response) {
            // Assume response is an array of suggestions
            console.log("Search results:", response);
            var html = response.map(function(item) {
                return `<div class="search-result" data-game-uuid="${item.uuid}" tabindex="0">${item.name}</div>`;
            }).join('');
            $('#searchResults').html(html);
        },
        error: function(xhr, status, error) {
            console.error("Search error:", error);
        }
    });
}

