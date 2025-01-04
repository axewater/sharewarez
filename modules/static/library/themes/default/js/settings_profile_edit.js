document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.querySelector('.upload-zone');
    const fileInput = document.getElementById('avatarInput');
    const previewSection = document.querySelector('.preview-section');
    const avatarPreview = document.getElementById('avatarPreview');

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
            const file = fileInput.files[0];
            const uploadHint = dropZone.querySelector('.upload-hint');
            if (uploadHint) {
                uploadHint.textContent = `File selected: ${file.name}`;
            }

            // Validate file type
            const validTypes = ['image/jpeg', 'image/png', 'image/gif'];
            if (!validTypes.includes(file.type)) {
                alert('Unsupported file type. Please select a JPG, PNG, or GIF image.');
                fileInput.value = '';
                uploadHint.textContent = 'Click to select or drag an image here';
                previewSection.style.display = 'none';
                return;
            }

            // Validate file size (Max 5MB)
            const maxSize = 5 * 1024 * 1024; // 5MB
            if (file.size > maxSize) {
                alert('File size exceeds 5MB. Please select a smaller image.');
                fileInput.value = '';
                uploadHint.textContent = 'Click to select or drag an image here';
                previewSection.style.display = 'none';
                return;
            }

            // Show preview
            const reader = new FileReader();
            reader.onload = function(e) {
                avatarPreview.src = e.target.result;
                previewSection.style.display = 'block';
            }
            reader.readAsDataURL(file);
        } else {
            const uploadHint = dropZone.querySelector('.upload-hint');
            if (uploadHint) {
                uploadHint.textContent = 'Click to select or drag an image here';
            }
            previewSection.style.display = 'none';
        }
    });
});
