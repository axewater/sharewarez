document.addEventListener('DOMContentLoaded', function() {
    var gameUuid = document.getElementById('upload-area').getAttribute('data-game-uuid');
    let selectedFiles = []; // Array to store selected files
    document.getElementById('upload-area').addEventListener('drop', handleDrop, false);
    document.getElementById('file-input').addEventListener('change', function(e) {
        console.log('Files selected');
        selectedFiles = e.target.files; // Store selected files in array
    });


    document.getElementById('upload-button').addEventListener('click', function() {
        console.log('Uploading files:', selectedFiles);
        for (let i = 0; i < selectedFiles.length; i++) {
            uploadFile(selectedFiles[i]); // Upload each selected file
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
        for (let i = 0; i < files.length; i++) {
            uploadFile(files[i]);
        }
    }

    function uploadFile(file) {
        console.log('Uploading file:', file.name);
        let url = `/upload_image/${gameUuid}`; // Ensure `gameUuid` is passed to this script from the template
        let formData = new FormData();
        formData.append('file', file);

        fetch(url, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            console.log('Upload response:', data);
            if (data.url) {
                let imageList = document.getElementById('image-list');
                let newImgDiv = document.createElement('div');
                // Assuming `data.image_id` is the ID returned from the server
                newImgDiv.innerHTML = `<img src="${data.url}" alt="Image"><button onclick="deleteImage(${data.image_id})">Delete</button>`;
                imageList.appendChild(newImgDiv);
            } else {
                alert('Upload failed');
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
    }

    function deleteImage(imageId) {
        console.log('Deleting image with ID:', imageId);
        fetch('/delete_image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ image_id: imageId }),
            
        })
        .then(response => {
            if (!response.ok) {
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
        });
    }
});