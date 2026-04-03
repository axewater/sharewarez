


$(document).ready(function() {

    function debounce(func, timeout) {
        let timer;
        return function() {
            var context = this, args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function() {
                func.apply(context, args);
            }, timeout);
        };
    }
    

    var selectedIndex = -1; // No selection initially
    var accumulatedChars = ''; // For accumulating rapid keypresses
    var modalOpening = false; // Track if modal is in process of opening
    var accumTimeout; // Timeout to clear accumulated chars

    $(document).on('keypress', function(e) {
        if (!$("input, textarea").is(":focus")) {
            e.preventDefault(); // Prevent default to avoid double character input
            var char = String.fromCharCode(e.which);
            
            // Accumulate the character
            accumulatedChars += char;
            
            // Clear any existing timeout
            clearTimeout(accumTimeout);
            
            // Only open modal if it's not already opening
            if (!modalOpening) {
                modalOpening = true;
                $('#searchModal').modal('show');
            }
            
            // Set timeout to clear accumulated chars if user stops typing
            accumTimeout = setTimeout(function() {
                accumulatedChars = '';
                modalOpening = false;
            }, 1000); // Reset after 1 second of no typing
        }
    });

    $('#searchModal').on('shown.bs.modal', function() {
        console.log("Search modal shown");
        if (accumulatedChars) {
            $('#searchInput').focus().val(accumulatedChars);
            // Clear accumulated characters and reset state
            accumulatedChars = '';
            modalOpening = false;
            clearTimeout(accumTimeout);
        } else {
            $('#searchInput').focus();
        }
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

    function updateSelection() {
        $('#searchResults .search-result').removeClass('selected')
            .eq(selectedIndex).addClass('selected')
            .focus(); // Optionally, focus the selected result for accessibility
    }
    
    const fetchSearchResults = debounce(function(query) {
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
                
                $('#searchResults .search-result').on('focus', function() {
                    $('#searchResults .search-result').removeClass('selected');
                    $(this).addClass('selected');
                    selectedIndex = $(this).index();
                    console.log("Selected index:", selectedIndex);
                }).on('keydown', function(e) {
                    if (e.key === 'Enter') {
                        $(this).click();
                    }
                });
    
            },
            error: function(xhr, status, error) {
                console.error("Search error:", error);
            }
        });
    }, 250);
    
    
    
});

