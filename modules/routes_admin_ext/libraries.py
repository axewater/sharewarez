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
        if library is None:
            library = Library(uuid=str(uuid4()))  # Generate a new UUID for new libraries

        library.name = form.name.data
        try:
            library.platform = LibraryPlatform[form.platform.data]
        except KeyError:
            flash(f'Invalid platform selected: {form.platform.data}', 'error')
            return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)

        file = form.image.data
        if file:
            # Validate file size (< 10 MB)
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            if file_length > 10 * 1024 * 1024:  # 10MB limit
                flash('File size is too large. Maximum allowed is 10 MB.', 'error')
                return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)

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
        elif not library.image_url:
            library.image_url = url_for('static', filename='newstyle/default_library.jpg')

        if library not in db.session:
            db.session.add(library)
        try:
            db.session.commit()
            log_system_event(f"Library created: {library.name}", event_type='library', event_level='information')
            flash('Library saved successfully!', 'success')
            return redirect(url_for('library.libraries'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to save library. Please try again.', 'error')
            print(f"Error saving library: {e}")

    return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)
