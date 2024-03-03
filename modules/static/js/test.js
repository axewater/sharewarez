document.addEventListener('DOMContentLoaded', function() {
        
    document.querySelectorAll('.delete-folder-form').forEach(form => {
        form.addEventListener('submit', function(event) {
            event.preventDefault(); 

            const formData = new FormData(form);
            const folderPath = formData.get('folder_path');
            const csrfToken = "{{ csrf_token() }}"; 
            document.addEventListener('DOMContentLoaded', function() {
        
                document.querySelectorAll('.delete-folder-form').forEach(form => {
                    form.addEventListener('submit', function(event) {
                        event.preventDefault(); 
            
                        const formData = new FormData(form);
                        const folderPath = formData.get('folder_path');
                        const csrfToken = "{{ csrf_token() }}"; 
                        console.log
                        // Perform the AJAX request
                        fetch('/delete_folder', { // Using direct path instead of url_for
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRF-Token': csrfToken
                            },
                            body: JSON.stringify({folder_path: folderPath})
                        }).then(response => response.json())
                        .then(data => {
                            
                            // Instead of alert, consider using a more user-friendly method 
                            alert(data.message);
            
                            
                            if(data.status === 'success') {
                                form.parentElement.parentElement.remove();
                            }
                        }).catch(error => console.error('Error:', error));
                    });
                });
                var activeTab = "{{ active_tab }}";
                console.log("Active tab:", activeTab);
        
                if (activeTab === 'manual') {
                    new bootstrap.Tab(document.querySelector('#manualScan-tab')).show();
                } else if (activeTab === 'unmatched') {
                    new bootstrap.Tab(document.querySelector('#unmatchedFolders-tab')).show();
                } else if (activeTab === 'deleteLibrary') {
                    new bootstrap.Tab(document.querySelector('#deleteLibrary-tab')).show();
                } else {
                    new bootstrap.Tab(document.querySelector('#autoScan-tab')).show();
                }
        
                
                var deleteAllGamesBtn = document.getElementById('deleteAllGamesBtn');
                if (deleteAllGamesBtn) {
                    deleteAllGamesBtn.addEventListener('click', function() {
                        var deleteWarningModal = new bootstrap.Modal(document.getElementById('deleteWarningModal'));
                        deleteWarningModal.show();
                    });
                }
            });
  
            // Perform the AJAX request
            fetch('/delete_folder', { // Using direct path instead of url_for
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({folder_path: folderPath})
            }).then(response => response.json())
            .then(data => {
                
                // Instead of alert, consider using a more user-friendly method 
                alert(data.message);

                
                if(data.status === 'success') {
                    form.parentElement.parentElement.remove();
                }
            }).catch(error => console.error('Error:', error));
        });
    });
    var activeTab = "{{ active_tab }}";
    console.log("Active tab:", activeTab);

    if (activeTab === 'manual') {
        new bootstrap.Tab(document.querySelector('#manualScan-tab')).show();
    } else if (activeTab === 'unmatched') {
        new bootstrap.Tab(document.querySelector('#unmatchedFolders-tab')).show();
    } else if (activeTab === 'deleteLibrary') {
        new bootstrap.Tab(document.querySelector('#deleteLibrary-tab')).show();
    } else {
        new bootstrap.Tab(document.querySelector('#autoScan-tab')).show();
    }

    
    var deleteAllGamesBtn = document.getElementById('deleteAllGamesBtn');
    if (deleteAllGamesBtn) {
        deleteAllGamesBtn.addEventListener('click', function() {
            var deleteWarningModal = new bootstrap.Modal(document.getElementById('deleteWarningModal'));
            deleteWarningModal.show();
        });
    }
});