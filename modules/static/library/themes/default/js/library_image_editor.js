class LibraryImageEditor {
    constructor(options) {
        this.containerId = options.containerId;
        this.canvasId = options.canvasId;
        this.previewId = options.previewId;
        this.onCropUpdate = options.onCropUpdate || (() => {});
        
        // Target dimensions (library image size)
        this.targetWidth = 250;
        this.targetHeight = 332;
        this.aspectRatio = this.targetWidth / this.targetHeight;
        
        // Canvas and context
        this.canvas = null;
        this.ctx = null;
        this.previewCanvas = null;
        this.previewCtx = null;
        
        // Image properties
        this.image = null;
        this.imageLoaded = false;
        
        // Transform properties
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.minScale = 0.1;
        this.maxScale = 5;
        
        // Interaction state
        this.isDragging = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        this.touches = [];
        
        this.init();
    }
    
    init() {
        this.canvas = document.getElementById(this.canvasId);
        this.ctx = this.canvas.getContext('2d');
        // Remove preview canvas code since we're using single canvas now
        
        // Set canvas dimensions
        this.canvas.width = this.targetWidth;
        this.canvas.height = this.targetHeight;
        
        this.setupEventListeners();
        this.drawGrid();
    }
    
    setupEventListeners() {
        // Mouse events
        this.canvas.addEventListener('mousedown', this.handleMouseDown.bind(this));
        this.canvas.addEventListener('mousemove', this.handleMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.handleMouseUp.bind(this));
        this.canvas.addEventListener('wheel', this.handleWheel.bind(this));
        
        // Touch events for mobile
        this.canvas.addEventListener('touchstart', this.handleTouchStart.bind(this));
        this.canvas.addEventListener('touchmove', this.handleTouchMove.bind(this));
        this.canvas.addEventListener('touchend', this.handleTouchEnd.bind(this));
        
        // Prevent context menu
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());
    }
    
    loadImage(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                this.image = new Image();
                this.image.onload = () => {
                    this.imageLoaded = true;
                    this.resetTransform();
                    this.draw();
                    resolve();
                };
                this.image.onerror = reject;
                this.image.src = e.target.result;
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }
    
    resetTransform() {
        if (!this.image) return;
        
        // Calculate initial scale to fit image in canvas
        const scaleX = this.targetWidth / this.image.width;
        const scaleY = this.targetHeight / this.image.height;
        this.scale = Math.min(scaleX, scaleY);
        
        // Center the image
        this.offsetX = (this.targetWidth - this.image.width * this.scale) / 2;
        this.offsetY = (this.targetHeight - this.image.height * this.scale) / 2;
        
        this.draw();
    }
    
    fitImage() {
        if (!this.image) return;
        
        // Scale to fit the larger dimension
        const scaleX = this.targetWidth / this.image.width;
        const scaleY = this.targetHeight / this.image.height;
        this.scale = Math.max(scaleX, scaleY);
        
        // Center the image
        this.offsetX = (this.targetWidth - this.image.width * this.scale) / 2;
        this.offsetY = (this.targetHeight - this.image.height * this.scale) / 2;
        
        this.draw();
    }
    
    zoom(factor, centerX = this.targetWidth / 2, centerY = this.targetHeight / 2) {
        if (!this.imageLoaded) return;
        
        const newScale = Math.max(this.minScale, Math.min(this.maxScale, this.scale * factor));
        
        if (newScale !== this.scale) {
            // Zoom towards the specified point
            const scaleDiff = newScale / this.scale;
            this.offsetX = centerX - (centerX - this.offsetX) * scaleDiff;
            this.offsetY = centerY - (centerY - this.offsetY) * scaleDiff;
            this.scale = newScale;
            
            this.draw();
        }
    }
    
    pan(deltaX, deltaY) {
        if (!this.imageLoaded) return;
        
        this.offsetX += deltaX;
        this.offsetY += deltaY;
        this.draw();
    }
    
    draw() {
        if (!this.ctx) return;
        
        // Clear canvas
        this.ctx.fillStyle = '#2a2c35';
        this.ctx.fillRect(0, 0, this.targetWidth, this.targetHeight);
        
        if (this.imageLoaded && this.image) {
            // Save context
            this.ctx.save();
            
            // Apply transforms
            this.ctx.translate(this.offsetX, this.offsetY);
            this.ctx.scale(this.scale, this.scale);
            
            // Draw image
            this.ctx.drawImage(this.image, 0, 0);
            
            // Restore context
            this.ctx.restore();
        }
        
        this.drawBorder();
        this.updateCropCoordinates();
    }
    
    drawBorder() {
        // Draw border around the crop area
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 2;
        this.ctx.strokeRect(1, 1, this.targetWidth - 2, this.targetHeight - 2);
    }
    
    drawGrid() {
        if (!this.ctx) return;
        
        this.ctx.fillStyle = '#2a2c35';
        this.ctx.fillRect(0, 0, this.targetWidth, this.targetHeight);
        
        // Draw grid pattern
        this.ctx.strokeStyle = '#444';
        this.ctx.lineWidth = 1;
        
        const gridSize = 20;
        for (let x = 0; x <= this.targetWidth; x += gridSize) {
            this.ctx.beginPath();
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, this.targetHeight);
            this.ctx.stroke();
        }
        
        for (let y = 0; y <= this.targetHeight; y += gridSize) {
            this.ctx.beginPath();
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(this.targetWidth, y);
            this.ctx.stroke();
        }
        
        this.drawBorder();
    }
    
    // Remove updatePreview method since we're using single canvas
    
    updateCropCoordinates() {
        if (!this.imageLoaded || !this.image) {
            this.onCropUpdate(null);
            return;
        }
        
        // Calculate crop coordinates in original image space
        const cropX = -this.offsetX / this.scale;
        const cropY = -this.offsetY / this.scale;
        const cropWidth = this.targetWidth / this.scale;
        const cropHeight = this.targetHeight / this.scale;
        
        // Ensure coordinates are within image bounds
        const clampedCropX = Math.max(0, Math.min(cropX, this.image.width));
        const clampedCropY = Math.max(0, Math.min(cropY, this.image.height));
        const clampedWidth = Math.min(cropWidth, this.image.width - clampedCropX);
        const clampedHeight = Math.min(cropHeight, this.image.height - clampedCropY);
        
        const cropData = {
            x: clampedCropX,
            y: clampedCropY,
            width: clampedWidth,
            height: clampedHeight,
            imageWidth: this.image.width,
            imageHeight: this.image.height
        };
        
        this.onCropUpdate(cropData);
    }
    
    // Mouse event handlers
    handleMouseDown(e) {
        if (!this.imageLoaded) return;
        
        this.isDragging = true;
        const rect = this.canvas.getBoundingClientRect();
        this.lastMouseX = e.clientX - rect.left;
        this.lastMouseY = e.clientY - rect.top;
        
        this.canvas.style.cursor = 'grabbing';
        e.preventDefault();
    }
    
    handleMouseMove(e) {
        if (!this.isDragging || !this.imageLoaded) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        const deltaX = mouseX - this.lastMouseX;
        const deltaY = mouseY - this.lastMouseY;
        
        this.pan(deltaX, deltaY);
        
        this.lastMouseX = mouseX;
        this.lastMouseY = mouseY;
        
        e.preventDefault();
    }
    
    handleMouseUp(e) {
        this.isDragging = false;
        this.canvas.style.cursor = this.imageLoaded ? 'grab' : 'default';
        e.preventDefault();
    }
    
    handleWheel(e) {
        if (!this.imageLoaded) return;
        
        e.preventDefault();
        
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
        this.zoom(zoomFactor, mouseX, mouseY);
    }
    
    // Touch event handlers
    handleTouchStart(e) {
        e.preventDefault();
        this.touches = Array.from(e.touches);
        
        if (this.touches.length === 1) {
            this.isDragging = true;
            const rect = this.canvas.getBoundingClientRect();
            this.lastMouseX = this.touches[0].clientX - rect.left;
            this.lastMouseY = this.touches[0].clientY - rect.top;
        }
    }
    
    handleTouchMove(e) {
        e.preventDefault();
        const newTouches = Array.from(e.touches);
        
        if (newTouches.length === 1 && this.isDragging) {
            // Single touch - pan
            const rect = this.canvas.getBoundingClientRect();
            const touchX = newTouches[0].clientX - rect.left;
            const touchY = newTouches[0].clientY - rect.top;
            
            const deltaX = touchX - this.lastMouseX;
            const deltaY = touchY - this.lastMouseY;
            
            this.pan(deltaX, deltaY);
            
            this.lastMouseX = touchX;
            this.lastMouseY = touchY;
        } else if (newTouches.length === 2 && this.touches.length === 2) {
            // Two touches - pinch to zoom
            const rect = this.canvas.getBoundingClientRect();
            
            const oldDistance = this.getTouchDistance(this.touches);
            const newDistance = this.getTouchDistance(newTouches);
            
            if (oldDistance > 0) {
                const zoomFactor = newDistance / oldDistance;
                const centerX = (newTouches[0].clientX + newTouches[1].clientX) / 2 - rect.left;
                const centerY = (newTouches[0].clientY + newTouches[1].clientY) / 2 - rect.top;
                
                this.zoom(zoomFactor, centerX, centerY);
            }
        }
        
        this.touches = newTouches;
    }
    
    handleTouchEnd(e) {
        e.preventDefault();
        this.touches = Array.from(e.touches);
        
        if (this.touches.length === 0) {
            this.isDragging = false;
        }
    }
    
    getTouchDistance(touches) {
        if (touches.length < 2) return 0;
        
        const dx = touches[0].clientX - touches[1].clientX;
        const dy = touches[0].clientY - touches[1].clientY;
        
        return Math.sqrt(dx * dx + dy * dy);
    }
    
    // Public methods for external controls
    zoomIn() {
        this.zoom(1.2);
    }
    
    zoomOut() {
        this.zoom(0.8);
    }
    
    reset() {
        this.resetTransform();
    }
    
    fit() {
        this.fitImage();
    }
    
    getCropData() {
        if (!this.imageLoaded || !this.image) return null;
        
        const cropX = -this.offsetX / this.scale;
        const cropY = -this.offsetY / this.scale;
        const cropWidth = this.targetWidth / this.scale;
        const cropHeight = this.targetHeight / this.scale;
        
        return {
            x: Math.max(0, cropX),
            y: Math.max(0, cropY),
            width: Math.min(cropWidth, this.image.width),
            height: Math.min(cropHeight, this.image.height),
            imageWidth: this.image.width,
            imageHeight: this.image.height
        };
    }
}

// Initialize the editor when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const editorContainer = document.getElementById('library-image-editor-container');
    if (!editorContainer) return;
    
    let editor = null;
    let currentFile = null;
    let cropData = null;
    let processedImageUrl = null;
    
    // Initialize editor
    function initEditor() {
        editor = new LibraryImageEditor({
            containerId: 'library-image-editor-container',
            canvasId: 'library-image-editor-canvas',
            previewId: null, // No separate preview canvas
            onCropUpdate: (data) => {
                cropData = data;
                updateCropInfo(data);
            }
        });
    }
    
    // Update crop information display
    function updateCropInfo(data) {
        const infoElement = document.getElementById('crop-info');
        if (infoElement && data) {
            infoElement.innerHTML = `
                <div class="crop-coordinates">
                    <small>
                        Crop: ${Math.round(data.x)}, ${Math.round(data.y)} 
                        Size: ${Math.round(data.width)}×${Math.round(data.height)}
                    </small>
                </div>
            `;
        }
    }
    
    // File input handler
    const fileInput = document.getElementById('library-image-input');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file && file.type.startsWith('image/')) {
                currentFile = file;
                loadImageIntoEditor(file);
            }
        });
    }
    
    // Drag and drop handlers
    const dropZone = document.getElementById('library-image-drop-zone');
    if (dropZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        dropZone.addEventListener('drop', function(e) {
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].type.startsWith('image/')) {
                currentFile = files[0];
                loadImageIntoEditor(files[0]);
            }
        });
        
        dropZone.addEventListener('click', function() {
            fileInput.click();
        });
    }
    
    // Load image into editor
    function loadImageIntoEditor(file) {
        if (!editor) initEditor();
        
        editor.loadImage(file).then(() => {
            document.getElementById('library-image-editor-container').style.display = 'block';
            document.getElementById('editor-controls').style.display = 'block';
        }).catch(error => {
            console.error('Failed to load image:', error);
            alert('Failed to load image. Please try again.');
        });
    }
    
    // Control button handlers
    const zoomInBtn = document.getElementById('zoom-in-btn');
    const zoomOutBtn = document.getElementById('zoom-out-btn');
    const resetBtn = document.getElementById('reset-btn');
    const fitBtn = document.getElementById('fit-btn');
    const saveImageBtn = document.getElementById('save-image-btn');
    
    if (zoomInBtn) zoomInBtn.addEventListener('click', () => editor && editor.zoomIn());
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => editor && editor.zoomOut());
    if (resetBtn) resetBtn.addEventListener('click', () => editor && editor.reset());
    if (fitBtn) fitBtn.addEventListener('click', () => editor && editor.fit());
    if (saveImageBtn) saveImageBtn.addEventListener('click', () => handleSaveImage());
    
    // Handle Save Image button click
    function handleSaveImage() {
        console.log('=== DEBUG: handleSaveImage called ===');
        console.log('Current processedImageUrl before processing:', processedImageUrl);
        
        if (!editor || !currentFile || !cropData) {
            alert('Please load an image first.');
            return;
        }
        
        const previewContainer = document.getElementById('image-preview-container');
        const previewImage = document.getElementById('preview-image');
        const previewLoading = document.getElementById('preview-loading');
        
        // Show loading state
        previewContainer.style.display = 'block';
        previewLoading.style.display = 'flex';
        previewImage.style.display = 'none';
        
        // Disable save button during processing
        saveImageBtn.disabled = true;
        saveImageBtn.textContent = '⏳ Processing...';
        
        // Read the current file as base64
        const reader = new FileReader();
        reader.onload = function(e) {
            const imageData = e.target.result;
            
            // Prepare data for AJAX call
            const requestData = {
                image_data: imageData,
                crop_x: cropData.x,
                crop_y: cropData.y,
                crop_width: cropData.width,
                crop_height: cropData.height,
                original_width: cropData.imageWidth,
                original_height: cropData.imageHeight
            };
            
            console.log('=== DEBUG: JavaScript crop data ===');
            console.log('Crop coordinates:', {
                x: cropData.x,
                y: cropData.y,
                width: cropData.width,
                height: cropData.height
            });
            console.log('Original dimensions:', {
                width: cropData.imageWidth,
                height: cropData.imageHeight
            });
            console.log('Editor transform state:', {
                scale: editor.scale,
                offsetX: editor.offsetX,
                offsetY: editor.offsetY,
                targetWidth: editor.targetWidth,
                targetHeight: editor.targetHeight
            });
            console.log('=== END DEBUG ===');
            
            // Make AJAX call to process image
            fetch('/admin/library/process-image', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify(requestData)
            })
            .then(response => response.json())
            .then(data => {
                console.log('=== DEBUG: AJAX Response ===');
                console.log('Full response data:', data);
                console.log('data.success:', data.success);
                console.log('data.image_url:', data.image_url);
                
                if (data.success) {
                    // Store processed image URL directly in the form field
                    const processedUrlField = document.querySelector('input[name="processed_image_url"]');
                    if (processedUrlField) {
                        processedUrlField.value = data.image_url;
                        console.log('Set processed_image_url field to:', data.image_url);
                    } else {
                        console.error('processed_image_url field not found in form');
                    }
                    
                    // Also store in variable for backwards compatibility
                    processedImageUrl = data.image_url;
                    console.log('Setting processedImageUrl to:', processedImageUrl);
                    
                    // Show processed image
                    previewImage.src = data.image_url;
                    previewImage.style.display = 'block';
                    previewLoading.style.display = 'none';
                    
                    console.log('processedImageUrl after preview update:', processedImageUrl);
                } else {
                    // Show error
                    alert('Error processing image: ' + (data.error || 'Unknown error'));
                    previewContainer.style.display = 'none';
                }
                console.log('=== END AJAX RESPONSE DEBUG ===');
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to process image. Please try again.');
                previewContainer.style.display = 'none';
            })
            .finally(() => {
                // Re-enable save button
                saveImageBtn.disabled = false;
                saveImageBtn.textContent = '💾 Save Image';
            });
        };
        
        reader.readAsDataURL(currentFile);
    }
    
    // Helper function to get CSRF token
    function getCsrfToken() {
        const csrfToken = document.querySelector('input[name="csrf_token"]');
        return csrfToken ? csrfToken.value : '';
    }
    
    // Form submission handler
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            console.log('=== DEBUG: Form Submission ===');
            
            // Check if we have a processed image URL in the form field
            const processedUrlField = document.querySelector('input[name="processed_image_url"]');
            const processedUrl = processedUrlField ? processedUrlField.value : '';
            
            console.log('processedImageUrl variable:', processedImageUrl);
            console.log('processed_image_url field value:', processedUrl);
            console.log('cropData:', cropData);
            console.log('currentFile:', currentFile);
            
            // If we have a processed image URL from "Save Image", let form submit normally
            if (processedUrl) {
                console.log('Using processed image URL path - field contains:', processedUrl);
                
                // Debug: Log all form fields before submission
                console.log('=== ALL FORM FIELDS BEFORE SUBMISSION ===');
                const formData = new FormData(form);
                for (let [key, value] of formData.entries()) {
                    console.log(`${key}: ${value}`);
                }
                console.log('=== END FORM FIELDS ===');
                
                // Let form submit normally - no need to prevent default
                return true;
            }
            // Fallback to original logic if no processed image (user didn't click "Save Image")
            else if (cropData && currentFile) {
                console.log('Using crop data processing path');
                e.preventDefault();
                
                // Add crop data as hidden fields
                ['x', 'y', 'width', 'height', 'imageWidth', 'imageHeight'].forEach(prop => {
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = `crop_${prop}`;
                    input.value = cropData[prop];
                    form.appendChild(input);
                });
                
                // Add the original file as a data URL for backend processing
                const reader = new FileReader();
                reader.onload = function(e) {
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'image_data';
                    input.value = e.target.result;
                    form.appendChild(input);
                    
                    console.log('Added crop data and image data to form');
                    
                    // Submit the form
                    form.submit();
                };
                reader.readAsDataURL(currentFile);
                
                return false;
            }
            // If no image editing was done, let form submit normally
            else {
                console.log('No image editing - normal form submission');
            }
            console.log('=== END FORM DEBUG ===');
        });
    }
});