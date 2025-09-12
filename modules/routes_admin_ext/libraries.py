from flask import render_template, request, redirect, url_for, flash, current_app, abort, jsonify
from flask_login import login_required
from modules.utils_auth import admin_required
from modules.models import Library, LibraryPlatform
from modules import db
from sqlalchemy import select
from modules.forms import LibraryForm
from modules.utils_logging import log_system_event
from PIL import Image as PILImage
from uuid import uuid4
from werkzeug.utils import secure_filename
import os
import base64
import io
from . import admin2_bp

def process_cropped_image(image_bytes, crop_x, crop_y, crop_width, crop_height, original_width, original_height):
    """
    Process an image with crop coordinates and resize to library dimensions (250x332)
    """
    try:
        print(f"=== DEBUG: process_cropped_image ===")
        print(f"Received crop coordinates: x={crop_x}, y={crop_y}, w={crop_width}, h={crop_height}")
        print(f"Original image dimensions: {original_width}x{original_height}")
        
        # Target dimensions for library images
        target_width = 250
        target_height = 332
        
        # Load image from bytes
        image_stream = io.BytesIO(image_bytes)
        with PILImage.open(image_stream) as img:
            img = img.convert('RGBA')
            print(f"Actual loaded image dimensions: {img.width}x{img.height}")
            
            # Ensure crop coordinates are within image bounds
            crop_x = max(0, min(crop_x, img.width))
            crop_y = max(0, min(crop_y, img.height))
            crop_width = min(crop_width, img.width - crop_x)
            crop_height = min(crop_height, img.height - crop_y)
            
            print(f"Adjusted crop coordinates: x={crop_x}, y={crop_y}, w={crop_width}, h={crop_height}")
            
            # Crop the image
            crop_box = (int(crop_x), int(crop_y), int(crop_x + crop_width), int(crop_y + crop_height))
            print(f"Crop box (left, top, right, bottom): {crop_box}")
            cropped_img = img.crop(crop_box)
            print(f"Cropped image dimensions: {cropped_img.width}x{cropped_img.height}")
            
            # Create final image with target dimensions and black background
            final_img = PILImage.new('RGBA', (target_width, target_height), (42, 44, 53, 255))  # #2a2c35
            
            # Calculate scaling to fit cropped image in target dimensions
            scale_x = target_width / cropped_img.width
            scale_y = target_height / cropped_img.height
            scale = min(scale_x, scale_y)
            print(f"Scale factors: x={scale_x:.3f}, y={scale_y:.3f}, chosen={scale:.3f}")
            
            # Resize cropped image
            new_width = int(cropped_img.width * scale)
            new_height = int(cropped_img.height * scale)
            print(f"Resized dimensions: {new_width}x{new_height}")
            resized_img = cropped_img.resize((new_width, new_height), PILImage.LANCZOS)
            
            # Center the resized image on the final canvas
            x_offset = (target_width - new_width) // 2
            y_offset = (target_height - new_height) // 2
            print(f"Final positioning: offset=({x_offset}, {y_offset})")
            final_img.paste(resized_img, (x_offset, y_offset), resized_img)
            
            # Save to file
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder, exist_ok=True)
                
            image_folder = os.path.join(upload_folder, 'images')
            if not os.path.exists(image_folder):
                os.makedirs(image_folder, exist_ok=True)
                
            uuid_filename = str(uuid4()) + '.png'
            image_path = os.path.join(image_folder, uuid_filename)
            print(f"Saving to: {image_path}")
            final_img.save(image_path, 'PNG')
            
            # Return the URL
            image_url = url_for('static', filename=os.path.join('library/images/', uuid_filename))
            print(f"Generated URL: {image_url}")
            print(f"=== END DEBUG ===")
            return image_url
            
    except Exception as e:
        print(f"Error in process_cropped_image: {e}")
        return None

def process_traditional_image(file):
    """
    Process a traditional file upload and resize to library dimensions (250x332)
    """
    try:
        # Target dimensions for library images
        target_width = 250
        target_height = 332
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder, exist_ok=True)

        image_folder = os.path.join(upload_folder, 'images')
        if not os.path.exists(image_folder):
            os.makedirs(image_folder, exist_ok=True)
            
        uuid_filename = str(uuid4()) + '.png'
        image_path = os.path.join(image_folder, uuid_filename)

        # Open and process image
        with PILImage.open(file) as img:
            img = img.convert('RGBA')
            
            # Create final image with target dimensions and black background
            final_img = PILImage.new('RGBA', (target_width, target_height), (42, 44, 53, 255))  # #2a2c35
            
            # Calculate scaling to fit image in target dimensions
            scale_x = target_width / img.width
            scale_y = target_height / img.height
            scale = min(scale_x, scale_y)
            
            # Resize image
            new_width = int(img.width * scale)
            new_height = int(img.height * scale)
            resized_img = img.resize((new_width, new_height), PILImage.LANCZOS)
            
            # Center the resized image on the final canvas
            x_offset = (target_width - new_width) // 2
            y_offset = (target_height - new_height) // 2
            final_img.paste(resized_img, (x_offset, y_offset), resized_img)
            
            # Save the final image
            final_img.save(image_path, 'PNG')

        # Return the URL
        image_url = url_for('static', filename=os.path.join('library/images/', uuid_filename))
        return image_url
        
    except Exception as e:
        print(f"Error in process_traditional_image: {e}")
        return None

@admin2_bp.route('/admin/library/process-image', methods=['POST'])
@login_required
@admin_required
def process_image():
    """
    AJAX endpoint to process cropped image and return preview URL
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Validate required fields
        required_fields = ['image_data', 'crop_x', 'crop_y', 'crop_width', 'crop_height', 'original_width', 'original_height']
        for field in required_fields:
            if field not in data or data[field] is None:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Decode base64 image data
        image_data = data['image_data']
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        
        # Validate image size
        if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
            return jsonify({'error': 'Image data is too large. Maximum allowed is 10 MB.'}), 400
        
        # Parse crop coordinates
        crop_x = float(data['crop_x'])
        crop_y = float(data['crop_y'])
        crop_width = float(data['crop_width'])
        crop_height = float(data['crop_height'])
        original_width = float(data['original_width'])
        original_height = float(data['original_height'])
        
        # Process the cropped image
        processed_image_url = process_cropped_image(
            image_bytes, crop_x, crop_y, crop_width, crop_height,
            original_width, original_height
        )
        
        if processed_image_url:
            return jsonify({
                'success': True,
                'image_url': processed_image_url,
                'message': 'Image processed successfully'
            })
        else:
            return jsonify({'error': 'Failed to process image'}), 500
            
    except Exception as e:
        print(f"Error in process_image endpoint: {e}")
        return jsonify({'error': 'An error occurred while processing the image'}), 500

@admin2_bp.route('/admin/library/add', methods=['GET', 'POST'])
@admin2_bp.route('/admin/library/edit/<library_uuid>', methods=['GET', 'POST'])
@login_required
@admin_required
def add_edit_library(library_uuid=None):
    if library_uuid:
        library = db.session.execute(select(Library).filter_by(uuid=library_uuid)).scalars().first() or abort(404)
        form = LibraryForm(obj=library)
        page_title = "Edit Library"
        print(f"Editing library: {library.name}, Platform: {library.platform.name}")
    else:
        library = None
        form = LibraryForm()
        page_title = "Add Library"
        print("Adding new library")

    form.platform.choices = [(platform.name, platform.value) for platform in LibraryPlatform]
    print(f"Platform choices: {form.platform.choices}")
    
    if library:
        form.platform.data = library.platform.name  # Set the initial value for existing library
        print(f"Setting initial platform value: {form.platform.data}")

    if form.validate_on_submit():
        print(f"=== DEBUG: All Form Data Received ===")
        print(f"request.form keys: {list(request.form.keys())}")
        for key, value in request.form.items():
            if key == 'image_data':
                print(f"{key}: [base64 data - length: {len(value)}]")
            else:
                print(f"{key}: {value}")
        print(f"request.files keys: {list(request.files.keys())}")
        print(f"=== END FORM DATA ===")
        
        if library is None:
            library = Library(uuid=str(uuid4()))  # Generate a new UUID for new libraries

        library.name = form.name.data
        try:
            library.platform = LibraryPlatform[form.platform.data]
        except KeyError:
            flash(f'Invalid platform selected: {form.platform.data}', 'error')
            return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)

        # Handle image upload with crop support
        image_processed = False
        
        print(f"=== DEBUG: Library Save Processing ===")
        print(f"Library: {library.name if library else 'New Library'}")
        print(f"Form processed_image_url: {form.processed_image_url.data}")
        print(f"Form has crop data: x={form.crop_x.data}, y={form.crop_y.data}, w={form.crop_width.data}, h={form.crop_height.data}")
        print(f"Form has image_data: {bool(form.image_data.data)}")
        print(f"Form has file upload: {bool(form.image.data)}")
        if library and hasattr(library, 'image_url'):
            print(f"Current library image_url: {library.image_url}")
        
        # Priority 1: Use already processed image URL if available
        if form.processed_image_url.data:
            print(f"Using pre-processed image: {form.processed_image_url.data}")
            library.image_url = form.processed_image_url.data
            image_processed = True
        
        # Priority 2: Check if we have crop data from the interactive editor
        elif (form.crop_x.data and form.crop_y.data and 
              form.crop_width.data and form.crop_height.data and 
              form.image_data.data):
            print("Processing crop data from interactive editor")
            try:
                # Decode base64 image data
                image_data = form.image_data.data
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                
                image_bytes = base64.b64decode(image_data)
                
                # Validate image size
                if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
                    flash('Image data is too large. Maximum allowed is 10 MB.', 'error')
                    return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)
                
                # Parse crop coordinates
                crop_x = float(form.crop_x.data)
                crop_y = float(form.crop_y.data)
                crop_width = float(form.crop_width.data)
                crop_height = float(form.crop_height.data)
                original_width = float(form.crop_imageWidth.data)
                original_height = float(form.crop_imageHeight.data)
                
                # Process the cropped image
                processed_image = process_cropped_image(
                    image_bytes, crop_x, crop_y, crop_width, crop_height,
                    original_width, original_height
                )
                
                if processed_image:
                    library.image_url = processed_image
                    image_processed = True
                    print(f"Processed cropped image: {processed_image}")
                else:
                    flash('Failed to process cropped image. Please try again.', 'error')
                    return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)
                    
            except Exception as e:
                print(f"Error processing cropped image: {e}")
                flash('Failed to process cropped image. Please try again.', 'error')
                return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)
        
        # Priority 3: Fallback to traditional file upload if no crop data
        elif form.image.data:
            file = form.image.data
            # Validate file size (< 10 MB)
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            if file_length > 10 * 1024 * 1024:  # 10MB limit
                flash('File size is too large. Maximum allowed is 10 MB.', 'error')
                return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)

            # Reset file pointer after checking size
            file.seek(0)
            
            processed_image = process_traditional_image(file)
            if processed_image:
                library.image_url = processed_image
                image_processed = True
                print(f"Processed traditional image: {processed_image}")
            else:
                flash('Failed to process image. Please try again.', 'error')
                return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)
        
        # Set default image if no image was processed
        if not image_processed and not library.image_url:
            library.image_url = url_for('static', filename='newstyle/default_library.jpg')

        if library not in db.session:
            db.session.add(library)
        print(f"Final library image_url before save: {library.image_url}")
        print(f"Image processed flag: {image_processed}")
        print(f"=== END LIBRARY DEBUG ===")
        
        try:
            db.session.commit()
            print(f"Library saved successfully with image_url: {library.image_url}")
            log_system_event(f"Library created: {library.name}", event_type='library', event_level='information')
            flash('Library saved successfully!', 'success')
            return redirect(url_for('library.libraries'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to save library. Please try again.', 'error')
            print(f"Error saving library: {e}")

    return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)
