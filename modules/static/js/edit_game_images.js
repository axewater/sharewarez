function uploadFile(file, gameUuid, csrfToken, imageType) {
    console.log('Uploading file:', file.name);
    let url = `/upload_image/${gameUuid}`;
    let formData = new FormData();
    formData.append('file', file);
    formData.append('image_type', imageType); // Add the image type to the form data

    console.log('Form data:', formData, url);
    fetch(url, {
        method: 'POST',
        body: formData,
        headers: new Headers({
            'X-CSRF-Token': csrfToken,
        }),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Upload response:', data);
        if (data.url) {
            if (imageType === 'cover') {
                displayCoverImage(data);
            } else {
                displayImage(data); // Existing function for screenshots
            }
        } else {
            alert('Upload failed');
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}



function displayImage(data) {
    let imageList = document.getElementById('image-editor-list');
    let newImgDiv = document.createElement('div');

    // Set the ID of the div to match the expected pattern
    newImgDiv.id = `image-${data.image_id}`;

    newImgDiv.innerHTML = `<button onclick="deleteImage(${data.image_id})">Delete</button><img src="${data.url}" alt="Image" class="image-editor-image" style="max-width: 300px; max-height: 300px;">`;
    imageList.appendChild(newImgDiv);
}

function displayCoverImage(data) {
    // Ensure this variable matches the ID of the div where the cover image is displayed
    let coverImageEditor = document.getElementById('cover-image-editor');

    // Check for and remove the existing image if present
    let existingImg = coverImageEditor.querySelector('img');
    if (existingImg) {
        existingImg.remove(); // A simpler approach to remove the element
    }

    // Create the new image element
    let img = document.createElement('img');
    img.src = data.url;
    img.alt = "Cover Image";
    img.style.maxWidth = "300px";
    img.style.maxHeight = "300px";

    // Insert the new image element at the beginning of the container
    coverImageEditor.insertBefore(img, coverImageEditor.firstChild);
}



function deleteImage(imageId) {
    console.log('Deleting image with ID:', imageId);
    console.log('Preparing fetch request with headers:', {
        'Content-Type': 'application/json',
    });
    console.log('JSON body to send:', JSON.stringify({ image_id: imageId }));
    var csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    fetch('/delete_image', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken, // Add the CSRF token
        },
        body: JSON.stringify({ image_id: imageId }),
        
    })
    .then(response => {
        console.log('Network response:', response);
        console.log('Response headers:', Array.from(response.headers.entries())); // Log all response headers
        if (!response.ok) {
            console.log('Network error response body:', response.statusText);
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        console.log('Delete response:', data);
        document.getElementById(`image-${imageId}`).remove();
    })
    .catch((error) => {
        console.error('Error:', error);
        console.error('Error response:', error);
    });
}



document.addEventListener('DOMContentLoaded', function() {
    
    var gameUuid = document.getElementById('upload-area').getAttribute('data-game-uuid');
    let selectedFiles = [];

    document.getElementById('cover-image-input').addEventListener('change', function(e) {
        let file = e.target.files[0];
        let csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        if (file) { // Ensure a file is selected
            uploadFile(file, gameUuid, csrfToken, 'cover'); // Call uploadFile with 'cover' as the imageType
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
            uploadFile(selectedFiles[i], gameUuid, csrfToken); // Pass gameUuid and csrfToken as arguments
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
            // Assume screenshots for drag & drop uploads, adjust accordingly if needed
            uploadFile(files[i], gameUuid, csrfToken, 'screenshot');
        }
    }

    
    

    
});