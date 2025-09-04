document.addEventListener('DOMContentLoaded', function() {
    // Initialize Sortable on the libraries table
    const tbody = document.querySelector('#librariesTable tbody');
    new Sortable(tbody, {
        handle: '.drag-handle',
        animation: 150,
        onEnd: function(evt) {
            const newOrder = Array.from(tbody.querySelectorAll('tr')).map(row => row.dataset.libraryUuid);
            
            // Send the new order to the server
            fetch('/api/reorder_libraries', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRFUtils.getToken()
                },
                body: JSON.stringify({ order: newOrder })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    $.notify('Library order updated successfully', 'success');
                } else {
                    $.notify('Error updating library order', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                $.notify('Error updating library order', 'error');
            });
        }
    });

    // Existing delete functionality
    const spinner = document.getElementById('deleteSpinner');
    var confirmDeleteButton = document.getElementById('confirmDeleteButton');
    var deleteForm = document.createElement('form');
    deleteForm.method = 'post';
    deleteForm.style.display = 'none'; // Ensure the form isn't visible on the page.
    document.body.appendChild(deleteForm);
    var csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrf_token';
    csrfInput.value = CSRFUtils.getToken(); // Ensure CSRF token is pulled from CSRFUtils
    deleteForm.appendChild(csrfInput);

    var body = document.querySelector('body');
    var deleteAllUrl = body.getAttribute('data-delete-url');
    var baseDeleteUrl = document.body.getAttribute('data-base-delete-url');
    var baseProgressUrl = document.body.getAttribute('data-progress-url');
    var baseCheckProgressUrl = document.body.getAttribute('data-check-progress-url');

    // Handle individual delete buttons
    document.querySelectorAll('.delete-btn').forEach(button => {
        button.addEventListener('click', function() {
            console.log('clicked delete button');
            var libraryUuid = this.getAttribute('data-library-uuid');
            document.querySelector('#deleteWarningModal .modal-body').textContent = 'Are you sure you want to delete this library? This action cannot be undone.';
            deleteForm.action = baseDeleteUrl + libraryUuid;
            confirmDeleteButton.textContent = 'Confirm Delete';

            // show modal
            var deleteWarningModal = new bootstrap.Modal(document.getElementById('deleteWarningModal'));
            deleteWarningModal.show();

            confirmDeleteButton.onclick = function() {
                // Hide the modal
                deleteWarningModal.hide();
                // Show the spinner with initial progress
                spinner.style.display = 'flex';
                
                const progressText = document.getElementById('progressText');
                const progressBar = document.getElementById('progressBar');
                const progressFill = document.getElementById('progressFill');
                const progressCounter = document.getElementById('progressCounter');
                
                progressText.textContent = 'Starting deletion...';
                progressBar.style.display = 'block';
                progressFill.style.width = '0%';
                progressCounter.textContent = '0/0';
                
                // Start the deletion with AJAX instead of form submit
                fetch(deleteForm.action, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': CSRFUtils.getToken()
                    },
                    body: new URLSearchParams(new FormData(deleteForm))
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'started') {
                        // Start listening for progress updates
                        startProgressTracking(data.job_id);
                    } else {
                        throw new Error(data.message || 'Failed to start deletion');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    spinner.style.display = 'none';
                    $.notify('Error starting deletion: ' + error.message, 'error');
                });
            };
        });
    });

    // Handle delete all libraries button
    var deleteAllGamesBtn = document.getElementById('deleteAllGamesBtn');
    if (deleteAllGamesBtn) {
        deleteAllGamesBtn.addEventListener('click', function() {
            document.querySelector('#deleteWarningModal .modal-body').textContent = 'Are you sure you want to delete all libraries? This action cannot be undone.';
            deleteForm.action = deleteAllUrl;
            confirmDeleteButton.textContent = 'Confirm Delete All Libraries';

            var deleteWarningModal = new bootstrap.Modal(document.getElementById('deleteWarningModal'));
            deleteWarningModal.show();
            
            confirmDeleteButton.onclick = function() {
                // Hide the modal
                deleteWarningModal.hide();
                // Show the spinner
                spinner.style.display = 'flex';
                
                // Submit the form
                deleteForm.onsubmit = function() {
                    return true;
                };
                
                setTimeout(() => {
                    deleteForm.submit();
                }, 100);
            };
        });
    }

    // Function to track progress via Server-Sent Events
    function startProgressTracking(jobId) {
        console.log('Starting progress tracking for job:', jobId);
        const progressText = document.getElementById('progressText');
        const progressBar = document.getElementById('progressBar');
        const progressFill = document.getElementById('progressFill');
        const progressCounter = document.getElementById('progressCounter');
        const spinner = document.getElementById('deleteSpinner');
        
        const eventSource = new EventSource(baseProgressUrl + jobId);
        
        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                console.log('Progress update:', data);
                
                // Handle initial connection confirmation
                if (data.status === 'connected') {
                    console.log('Progress tracking connected successfully');
                    return;
                }
                
                // Update progress text
                progressText.textContent = data.message || 'Processing...';
                
                // Update progress bar if we have progress info
                if (data.total > 0) {
                    const percentage = Math.round((data.current / data.total) * 100);
                    progressFill.style.width = percentage + '%';
                    progressCounter.textContent = `${data.current}/${data.total}`;
                    
                    // Show progress bar once we have data
                    if (progressBar.style.display === 'none') {
                        progressBar.style.display = 'block';
                    }
                }
                
                // Handle completion
                if (data.status === 'completed') {
                    eventSource.close();
                    progressFill.style.width = '100%';
                    setTimeout(() => {
                        spinner.style.display = 'none';
                        if (data.games_failed === 0) {
                            $.notify(data.message, 'success');
                        } else {
                            $.notify(data.message, 'warning');
                        }
                        // Refresh the page to show updated library list
                        window.location.reload();
                    }, 2000);
                }
                
                // Handle errors
                if (data.status === 'error') {
                    eventSource.close();
                    spinner.style.display = 'none';
                    $.notify('Error: ' + data.message, 'error');
                }
                
            } catch (error) {
                console.error('Error parsing progress data:', error, 'Raw event:', event.data);
            }
        };
        
        eventSource.onerror = function(error) {
            console.error('SSE Error:', error);
            console.log('EventSource readyState:', eventSource.readyState);
            console.log('Falling back to polling mechanism...');
            eventSource.close();
            
            // Fall back to polling
            startPollingFallback(jobId);
        };
    }

    // Fallback polling mechanism if SSE fails
    function startPollingFallback(jobId) {
        console.log('Starting fallback polling for job:', jobId);
        const progressText = document.getElementById('progressText');
        const progressBar = document.getElementById('progressBar');
        const progressFill = document.getElementById('progressFill');
        const progressCounter = document.getElementById('progressCounter');
        const spinner = document.getElementById('deleteSpinner');
        
        progressText.textContent = 'Using fallback progress tracking...';
        
        function pollProgress() {
            fetch(baseCheckProgressUrl + jobId)
                .then(response => response.json())
                .then(data => {
                    console.log('Fallback progress update:', data);
                    
                    if (data.status === 'not_found') {
                        console.log('Job completed or not found, stopping polling');
                        return;
                    }
                    
                    // Update progress text
                    progressText.textContent = data.message || 'Processing...';
                    
                    // Update progress bar if we have progress info
                    if (data.total > 0) {
                        const percentage = Math.round((data.current / data.total) * 100);
                        progressFill.style.width = percentage + '%';
                        progressCounter.textContent = `${data.current}/${data.total}`;
                        
                        // Show progress bar once we have data
                        if (progressBar.style.display === 'none') {
                            progressBar.style.display = 'block';
                        }
                    }
                    
                    // Handle completion
                    if (data.status === 'completed') {
                        progressFill.style.width = '100%';
                        setTimeout(() => {
                            spinner.style.display = 'none';
                            if (data.games_failed === 0) {
                                $.notify(data.message, 'success');
                            } else {
                                $.notify(data.message, 'warning');
                            }
                            // Refresh the page to show updated library list
                            window.location.reload();
                        }, 2000);
                        return;
                    }
                    
                    // Handle errors
                    if (data.status === 'error') {
                        spinner.style.display = 'none';
                        $.notify('Error: ' + data.message, 'error');
                        return;
                    }
                    
                    // Continue polling
                    setTimeout(pollProgress, 1000);
                })
                .catch(error => {
                    console.error('Polling error:', error);
                    spinner.style.display = 'none';
                    $.notify('Progress tracking failed', 'error');
                });
        }
        
        // Start polling
        setTimeout(pollProgress, 500);
    }
});
