$(document).ready(function() {
    var selectedIndex = -1; // No selection initially

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

    $('#searchInput').on('keydown', function(e) {
        var resultsCount = $('#searchResults .search-result').length;
        
        if (e.key === 'ArrowDown') {
            e.preventDefault(); // Prevent the cursor from moving in the input field
            selectedIndex = (selectedIndex + 1) % resultsCount;
            updateSelection();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault(); // Prevent the cursor from moving in the input field
            selectedIndex = (selectedIndex - 1 + resultsCount) % resultsCount;
            updateSelection();
        } else if (e.key === 'Enter') {
            e.preventDefault(); // Prevent form submission
            if (selectedIndex >= 0) {
                $('#searchResults .search-result').eq(selectedIndex).click();
            }
        }
    });
    

    $('#searchResults').on('click', '.search-result', function() {
        console.log("Search result clicked");
        var gameUuid = $(this).attr('data-game-uuid'); // Slightly changed from .data('game-uuid') for debugging
        console.log("Navigating to UUID:", gameUuid); // Debugging line to ensure UUID is captured
        window.location.href = '/game_details/' + gameUuid;
    });
});

function updateSelection() {
    $('#searchResults .search-result').removeClass('selected')
        .eq(selectedIndex).addClass('selected')
        .focus(); // Optionally, focus the selected result for accessibility
}

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
            selectedIndex = -1; 
        },
        error: function(xhr, status, error) {
            console.error("Search error:", error);
        }
    });
}
