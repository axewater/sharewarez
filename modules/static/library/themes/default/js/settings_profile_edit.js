document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.querySelector('.upload-zone');
    const fileInput = document.getElementById('avatar');

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        dropZone.classList.add('highlight');
    }

    function unhighlight(e) {
        dropZone.classList.remove('highlight');
    }

    dropZone.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileInput.files = files;
        
        // Trigger change event on file input
        const event = new Event('change', { bubbles: true });
        fileInput.dispatchEvent(event);
        
        // Update the upload hint text
        const uploadHint = dropZone.querySelector('.upload-hint');
        if (uploadHint) {
            uploadHint.textContent = `File selected: ${files[0].name}`;
        }
    }

    // Handle click to select file
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle file selection via input
    fileInput.addEventListener('change', (e) => {
        if (fileInput.files.length > 0) {
            const uploadHint = dropZone.querySelector('.upload-hint');
            if (uploadHint) {
                uploadHint.textContent = `File selected: ${fileInput.files[0].name}`;
            }
        }
    });
});
