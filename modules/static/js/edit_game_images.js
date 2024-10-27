function uploadFile(file, gameUuid, csrfToken, imageType = 'screenshot') {
    console.log('Uploading file:', file.name);
    let url = `/upload_image/${gameUuid}`;
    let formData = new FormData();
    formData.append('file', file);
    formData.append('image_type', imageType);

    console.log('Form data:', formData, url);
    fetch(url, {
        method: 'POST',
        body: formData,
        headers: new Headers({
            'X-CSRF-Token': csrfToken,
        }),
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Upload failed');
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Upload response:', data);
        if (data.url) {
            if (imageType === 'cover') {
                displayCoverImage(data);
            } else {
                displayImage(data);
            }
            if (data.flash) {
                console.log('Success:', data.flash);
            }
        } else {
            throw new Error('Upload succeeded but no URL was returned.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        var errorModalMessage = document.getElementById('errorModalMessage');
        errorModalMessage.textContent = error.message;
        
        var errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
        errorModal.show();
    });
}

function displayImage(data) {
    let imageList = document.getElementById('image-editor-list');
    let newImgDiv = document.createElement('div');

    newImgDiv.id = `image-${data.image_id}`;

    newImgDiv.innerHTML = `<button onclick="deleteImage(${data.image_id})">Delete</button><img src="${data.url}" alt="Image" class="image-editor-image" style="max-width: 300px; max-height: 300px;">`;
    imageList.appendChild(newImgDiv);
}

function displayCoverImage(data) {
    let coverImageEditor = document.getElementById('cover-image-editor');

    let existingImg = coverImageEditor.querySelector('img');
    if (existingImg) {
        existingImg.remove();
    }

    let img = document.createElement('img');
    img.src = data.url;
    img.alt = "Cover Image";
    img.style.maxWidth = "300px";
    img.style.maxHeight = "300px";

    coverImageEditor.insertBefore(img, coverImageEditor.firstChild);
}

function deleteImage(imageId) {
    console.log('Deleting image with ID:', imageId);
    var csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
    // Check if this is a cover image
    const coverImageEditor = document.getElementById('cover-image-editor');
    const isCoverImage = coverImageEditor.querySelector(`img[data-image-id="${imageId}"]`) !== null;

    // If it's a cover image, show confirmation dialog
    if (isCoverImage) {
        if (!confirm('Are you sure you want to delete the cover image?')) {
            return;
        }
    }

    fetch('/delete_image', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({ 
            image_id: imageId,
            is_cover: isCoverImage 
        }),
    })
    .then(response => {
        console.log('Network response:', response);
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Deletion failed');
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Delete response:', data);
        if (data.default_cover) {
            // This was a cover image, replace with default
            const coverImageEditor = document.getElementById('cover-image-editor');
            const img = coverImageEditor.querySelector('img');
            if (img) {
                img.src = data.default_cover;
                img.removeAttribute('data-image-id');
            }
        } else {
            // Regular screenshot, just remove it
            document.getElementById(`image-${imageId}`).remove();
        }
    })
    .catch((error) => {
        console.error('Error:', error);
        var errorModalMessage = document.getElementById('errorModalMessage');
        errorModalMessage.textContent = error.message;
        
        var errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
        errorModal.show();
    });
}

document.addEventListener('DOMContentLoaded', function() {
    
    var gameUuid = document.getElementById('upload-area').getAttribute('data-game-uuid');
    let selectedFiles = [];

    document.getElementById('cover-image-input').addEventListener('change', function(e) {
        let file = e.target.files[0];
        let csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        if (file) {
            uploadFile(file, gameUuid, csrfToken, 'cover');
        }
    });
    
    
    document.getElementById('upload-area').addEventListener('drop', handleDrop, false);
    document.getElementById('file-input').addEventListener('change', function(e) {
        console.log('Files selected');
        selectedFiles = e.target.files;
    });


    document.getElementById('upload-button').addEventListener('click', function() {
        let gameUuid = document.getElementById('upload-area').getAttribute('data-game-uuid');
        let csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        console.log('Uploading files:', selectedFiles);
        for (let i = 0; i < selectedFiles.length; i++) {
            uploadFile(selectedFiles[i], gameUuid, csrfToken);
        }
    });

    function handleDrop(e) {
        console.log('Drop event triggered');
        e.preventDefault();
        e.stopPropagation();
        let dt = e.dataTransfer;
        let files = dt.files;
        handleFiles(files);
    }

    function handleFiles(files) {
        console.log('Handling files');
        let csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        for (let i = 0; i < files.length; i++) {
            uploadFile(files[i], gameUuid, csrfToken, 'screenshot');
        }
    }
});
