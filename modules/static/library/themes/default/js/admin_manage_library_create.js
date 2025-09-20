document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('imageInput').addEventListener('change', function(event) {
        const file = event.target.files[0];
        const maxSize = 10 * 1024 * 1024; // 10MB in bytes

        if (file && file.size > maxSize) {
            alert('File is too large! Maximum size is 10MB.');
            event.target.value = ''; // Clear the file input
            document.getElementById('imagePreview').src = document.getElementById('imagePreview').getAttribute('data-default-src');
            return;
        }

        if (file) {
            var reader = new FileReader();
            reader.onload = function() {
                var output = document.getElementById('imagePreview');
                output.src = reader.result;
            };
            reader.readAsDataURL(file);
        }
    });
});