from flask import render_template, request, redirect, url_for, flash, current_app, abort
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
from . import admin2_bp

def _process_library_image(file, library):
    """Process and save library image file."""
    if not file:
        if not library.image_url:
            library.image_url = url_for('static', filename='newstyle/default_library.jpg')
        return

    # Validate file size (< 10 MB)
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    if file_length > 10 * 1024 * 1024:  # 10MB limit
        flash('File size is too large. Maximum allowed is 10 MB.', 'error')
        return False

    # Reset file pointer after checking size
    file.seek(0)

    upload_folder = current_app.config['UPLOAD_FOLDER']
    print(f"Upload folder now: {upload_folder}")
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)

    filename = secure_filename(file.filename)
    uuid_filename = str(uuid4()) + '.png'  # Always save as PNG
    image_folder = os.path.join(upload_folder, 'images')
    print(f"Image folder: {image_folder}")
    if not os.path.exists(image_folder):
        os.makedirs(image_folder, exist_ok=True)
    image_path = os.path.join(image_folder, uuid_filename)
    print(f"Image path: {image_path}")

    # Open, convert to PNG, and resize if necessary
    with PILImage.open(file) as img:
        img = img.convert('RGBA')
        if img.width > 1024 or img.height > 1024:
            img.thumbnail((1024, 1024), PILImage.LANCZOS)
        img.save(image_path, 'PNG')

    image_url = url_for('static', filename=os.path.join('library/images/', uuid_filename))
    print(f"Image URL: {image_url}")
    library.image_url = image_url
    return True

def _save_library(library, is_new=False):
    """Save library to database with proper error handling."""
    if is_new and library not in db.session:
        db.session.add(library)

    try:
        db.session.commit()
        action = "created" if is_new else "updated"
        log_system_event(f"Library {action}: {library.name}", event_type='library', event_level='information')
        flash('Library saved successfully!', 'success')
        return True
    except Exception as e:
        db.session.rollback()
        flash('Failed to save library. Please try again.', 'error')
        print(f"Error saving library: {e}")
        return False

@admin2_bp.route('/admin/library/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_library():
    """Handle adding new libraries."""
    form = LibraryForm()
    page_title = "Add Library"
    print("Adding new library")

    form.platform.choices = [(platform.name, platform.value) for platform in LibraryPlatform]
    print(f"Platform choices: {form.platform.choices}")

    if form.validate_on_submit():
        library = Library(uuid=str(uuid4()))  # Generate a new UUID for new libraries
        library.name = form.name.data

        try:
            library.platform = LibraryPlatform[form.platform.data]
        except KeyError:
            flash(f'Invalid platform selected: {form.platform.data}', 'error')
            return render_template('admin/admin_manage_library_create.html', form=form, library=None, page_title=page_title)

        # Process image upload
        file = form.image.data
        image_result = _process_library_image(file, library)
        if image_result is False:  # Explicit check for file size error
            return render_template('admin/admin_manage_library_create.html', form=form, library=None, page_title=page_title)

        # Save library
        if _save_library(library, is_new=True):
            return redirect(url_for('library.libraries'))

    return render_template('admin/admin_manage_library_create.html', form=form, library=None, page_title=page_title)

@admin2_bp.route('/admin/library/edit/<library_uuid>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_library(library_uuid):
    """Handle editing existing libraries."""
    library = db.session.execute(select(Library).filter_by(uuid=library_uuid)).scalars().first() or abort(404)
    form = LibraryForm(obj=library)
    page_title = "Edit Library"
    print(f"Editing library: {library.name}, Platform: {library.platform.name}")

    form.platform.choices = [(platform.name, platform.value) for platform in LibraryPlatform]
    print(f"Platform choices: {form.platform.choices}")

    # Set the initial value for existing library
    form.platform.data = library.platform.name
    print(f"Setting initial platform value: {form.platform.data}")

    if form.validate_on_submit():
        library.name = form.name.data

        try:
            library.platform = LibraryPlatform[form.platform.data]
        except KeyError:
            flash(f'Invalid platform selected: {form.platform.data}', 'error')
            return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)

        # Process image upload
        file = form.image.data
        image_result = _process_library_image(file, library)
        if image_result is False:  # Explicit check for file size error
            return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)

        # Save library
        if _save_library(library, is_new=False):
            return redirect(url_for('library.libraries'))

    return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)

