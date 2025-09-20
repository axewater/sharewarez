document.addEventListener('DOMContentLoaded', function() {
    let cropper = null;
    let currentFile = null;
    let croppedImageBlob = null;

    const imageInput = document.getElementById('imageInput');
    const imagePreview = document.getElementById('imagePreview');
    const imageEditorModal = new bootstrap.Modal(document.getElementById('imageEditorModal'));
    const imageEditorCanvas = document.getElementById('imageEditorCanvas');
    const saveImageBtn = document.getElementById('saveImageBtn');
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const resetCropBtn = document.getElementById('resetCropBtn');

    // Handle file input change - open editor instead of direct preview
    imageInput.addEventListener('change', function(event) {
        const file = event.target.files[0];
        const maxSize = 10 * 1024 * 1024; // 10MB in bytes

        if (file && file.size > maxSize) {
            alert('File is too large! Maximum size is 10MB.');
            event.target.value = '';
            return;
        }

        if (file) {
            currentFile = file;
            openImageEditor(file);
        }
    });

    // Open the image editor modal with the selected file
    function openImageEditor(file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            imageEditorCanvas.src = e.target.result;
            imageEditorCanvas.style.display = 'block';

            // Show the modal
            imageEditorModal.show();

            // Initialize cropper after modal is shown
            document.getElementById('imageEditorModal').addEventListener('shown.bs.modal', function() {
                if (cropper) {
                    cropper.destroy();
                }

                cropper = new Cropper(imageEditorCanvas, {
                    aspectRatio: 1, // Square aspect ratio for library images
                    viewMode: 1,
                    dragMode: 'move',
                    autoCropArea: 0.8,
                    restore: false,
                    guides: true,
                    center: true,
                    highlight: false,
                    cropBoxMovable: true,
                    cropBoxResizable: true,
                    toggleDragModeOnDblclick: false,
                    modal: true,
                    background: false,
                    responsive: true,
                    checkCrossOrigin: false,
                    zoomable: true,
                    scalable: false,
                    rotatable: false,
                    checkOrientation: false
                });
            }, { once: true });
        };
        reader.readAsDataURL(file);
    }

    // Save cropped image
    saveImageBtn.addEventListener('click', function() {
        if (cropper) {
            cropper.getCroppedCanvas({
                width: 512,
                height: 512,
                imageSmoothingEnabled: true,
                imageSmoothingQuality: 'high'
            }).toBlob(function(blob) {
                croppedImageBlob = blob;

                // Update preview with cropped image
                const url = URL.createObjectURL(blob);
                imagePreview.src = url;

                // Create a new File object from the blob to replace the original file
                const croppedFile = new File([blob], currentFile.name, {
                    type: 'image/png',
                    lastModified: Date.now()
                });

                // Update the file input with the cropped image
                updateFileInput(croppedFile);

                // Close modal
                imageEditorModal.hide();
            }, 'image/png', 0.9);
        }
    });

    // Helper function to update file input with cropped image
    function updateFileInput(croppedFile) {
        // Create a new DataTransfer object to simulate file selection
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(croppedFile);
        imageInput.files = dataTransfer.files;
    }

    // Zoom controls
    zoomInBtn.addEventListener('click', function() {
        if (cropper) {
            cropper.zoom(0.1);
        }
    });

    zoomOutBtn.addEventListener('click', function() {
        if (cropper) {
            cropper.zoom(-0.1);
        }
    });

    // Reset crop area
    resetCropBtn.addEventListener('click', function() {
        if (cropper) {
            cropper.reset();
        }
    });

    // Clean up cropper when modal is hidden
    document.getElementById('imageEditorModal').addEventListener('hidden.bs.modal', function() {
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        imageEditorCanvas.style.display = 'none';

        // If no image was saved, reset the file input
        if (!croppedImageBlob) {
            imageInput.value = '';
            imagePreview.src = imagePreview.getAttribute('data-default-src');
        }
    });

    // Handle modal cancel
    document.getElementById('imageEditorModal').addEventListener('hidden.bs.modal', function(e) {
        // Only reset if the modal was closed without saving
        if (e.target.classList.contains('modal') && !croppedImageBlob) {
            currentFile = null;
        }
    });

    // Add keyboard support for cropper
    document.addEventListener('keydown', function(e) {
        if (document.getElementById('imageEditorModal').classList.contains('show') && cropper) {
            switch(e.key) {
                case 'ArrowLeft':
                    e.preventDefault();
                    cropper.move(-10, 0);
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    cropper.move(10, 0);
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    cropper.move(0, -10);
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    cropper.move(0, 10);
                    break;
                case '+':
                case '=':
                    e.preventDefault();
                    cropper.zoom(0.1);
                    break;
                case '-':
                    e.preventDefault();
                    cropper.zoom(-0.1);
                    break;
                case 'r':
                case 'R':
                    e.preventDefault();
                    cropper.reset();
                    break;
            }
        }
    });
});