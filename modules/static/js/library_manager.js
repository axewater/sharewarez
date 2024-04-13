var deleteAllGamesBtn = document.getElementById('deleteAllGamesBtn');
if (deleteAllGamesBtn) {
    deleteAllGamesBtn.addEventListener('click', function() {
        console.log("Showing delete warning modal.");
        var deleteWarningModal = new bootstrap.Modal(document.getElementById('deleteWarningModal'));
        deleteWarningModal.show();
    });
}