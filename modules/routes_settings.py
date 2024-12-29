import os
from PIL import Image as PILImage
from werkzeug.utils import secure_filename
from uuid import uuid4
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from modules.forms import EditProfileForm, UserPasswordForm, UserPreferencesForm
from modules.models import User, InviteToken, UserPreference
from modules.utils_functions import square_image
from modules.utils_processors import get_global_settings
from modules import cache
from modules import db



settings_bp = Blueprint('settings', __name__)

@settings_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()


@settings_bp.context_processor
def inject_current_theme():
    if current_user.is_authenticated and current_user.preferences:
        current_theme = current_user.preferences.theme or 'default'
    else:
        current_theme = 'default'
    return dict(current_theme=current_theme)


@settings_bp.route('/settings_profile_edit', methods=['GET', 'POST'])
@login_required
def settings_profile_edit():
    print("Route: Settings profile edit")
    form = EditProfileForm()

    if form.validate_on_submit():
        file = form.avatar.data
        if file:
            MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > MAX_FILE_SIZE:
                flash(f"File size exceeds the {MAX_FILE_SIZE//1024//1024}MB limit.", "error")
                return redirect(url_for('settings.settings_profile_edit'))

            upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'images/avatars_users')
            if not os.path.exists(upload_folder):
                try:
                    os.makedirs(upload_folder, exist_ok=True)
                except Exception as e:
                    print(f"Error creating upload directory: {e}")
                    flash("Error processing request. Please try again.", 'error')
                    return redirect(url_for('settings.settings_profile_edit'))

            old_avatarpath = current_user.avatarpath
            if old_avatarpath and old_avatarpath != 'newstyle/avatar_default.jpg':
                old_thumbnailpath = os.path.splitext(old_avatarpath)[0] + '_thumbnail' + os.path.splitext(old_avatarpath)[1]
            else:
                old_thumbnailpath = None

            filename = secure_filename(file.filename)
            uuid_filename = str(uuid4()) + '.' + filename.rsplit('.', 1)[1].lower()
            image_path = os.path.join(upload_folder, uuid_filename)
            file.save(image_path)

            # Image processing
            img = PILImage.open(image_path)
            is_gif = img.format == 'GIF' and 'duration' in img.info

            if is_gif:
                # For GIFs, maintain animation but resize each frame
                frames = []
                try:
                    while True:
                        # Copy the current frame
                        frame = img.copy()
                        # Resize the frame maintaining aspect ratio
                        frame.thumbnail((500, 500), PILImage.LANCZOS)
                        # Add the frame to our list
                        frames.append(frame)
                        # Go to next frame
                        img.seek(img.tell() + 1)
                except EOFError:
                    pass  # We've hit the end of the GIF

                # Save the resized GIF with all frames
                frames[0].save(
                    image_path,
                    save_all=True,
                    append_images=frames[1:],
                    format='GIF',
                    duration=img.info.get('duration', 100),
                    loop=img.info.get('loop', 0)
                )

                # Create thumbnail (first frame only for performance)
                thumbnail = frames[0].copy()
                thumbnail.thumbnail((50, 50), PILImage.LANCZOS)
                thumbnail_path = os.path.splitext(image_path)[0] + '_thumbnail' + os.path.splitext(image_path)[1]
                thumbnail.save(thumbnail_path, 'GIF')

            else:
                # For non-GIF images, use the existing square_image processing
                img = square_image(img, 500)
                img.save(image_path)
                
                # Create thumbnail
                thumbnail = img.copy()
                thumbnail.thumbnail((50, 50), PILImage.LANCZOS)
                thumbnail_path = os.path.splitext(image_path)[0] + '_thumbnail' + os.path.splitext(image_path)[1]
                thumbnail.save(thumbnail_path)

            # Delete old avatar files if they exist
            if old_avatarpath and old_avatarpath != 'newstyle/avatar_default.jpg':
                try:
                    old_avatar_full_path = os.path.join(upload_folder, os.path.basename(old_avatarpath))
                    if os.path.exists(old_avatar_full_path):
                        os.remove(old_avatar_full_path)
                    if old_thumbnailpath:
                        old_thumbnail_full_path = os.path.join(upload_folder, os.path.basename(old_thumbnailpath))
                        if os.path.exists(old_thumbnail_full_path):
                            os.remove(old_thumbnail_full_path)
                except Exception as e:
                    print(f"Error deleting old avatar: {e}")
                    flash("Error deleting old avatar. Please try again.", 'error')

            current_user.avatarpath = 'library/images/avatars_users/' + uuid_filename
        else:
            if not current_user.avatarpath:
                current_user.avatarpath = 'newstyle/avatar_default.jpg'

        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Error updating profile: {e}")
            flash('Failed to update profile. Please try again.', 'error')

        return redirect(url_for('settings.settings_profile_edit'))

    print("Form validation failed" if request.method == 'POST' else "Settings profile Form rendering")

    for field, errors in form.errors.items():
        for error in errors:
            print(f"Error in field '{getattr(form, field).label.text}': {error}")
            flash(f"Error in field '{getattr(form, field).label.text}': {error}", 'error')

    return render_template('settings/settings_profile_edit.html', form=form, avatarpath=current_user.avatarpath)


@settings_bp.route('/settings_profile_view', methods=['GET'])
@login_required
def settings_profile_view():
    print("Route: Settings profile view")
    unused_invites = InviteToken.query.filter_by(
        creator_user_id=current_user.user_id, 
        used=False
    ).count()
    remaining_invites = max(0, current_user.invite_quota - unused_invites)
    
    return render_template('settings/settings_profile_view.html', 
                         remaining_invites=remaining_invites,
                         total_invites=current_user.invite_quota)

@settings_bp.route('/settings_password', methods=['GET', 'POST'])
@login_required
def account_pw():
    form = UserPasswordForm()
    user = User.query.get(current_user.id)

    if form.validate_on_submit():
        try:
            user.set_password(form.password.data)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            print('Password changed successfully for user ID:', current_user.id)
            return redirect(url_for('settings.account_pw'))
        except Exception as e:
            db.session.rollback()
            print('An error occurred while changing the password:', str(e))
            flash('An error occurred. Please try again.', 'error')

    return render_template('settings/settings_password.html', title='Change Password', form=form, user=user)

@settings_bp.route('/settings_panel', methods=['GET', 'POST'])
@login_required
def settings_panel():
    print("Route: /settings_panel")
    form = UserPreferencesForm()
    
    if request.method == 'POST' and form.validate_on_submit():
        # Ensure preferences exist
        if not current_user.preferences:
            current_user.preferences = UserPreference(user_id=current_user.id)
        
        current_user.preferences.items_per_page = form.items_per_page.data or current_user.preferences.items_per_page
        current_user.preferences.default_sort = form.default_sort.data or current_user.preferences.default_sort
        current_user.preferences.default_sort_order = form.default_sort_order.data or current_user.preferences.default_sort_order
        current_user.preferences.theme = form.theme.data if form.theme.data != 'default' else None
        db.session.add(current_user.preferences)
        db.session.commit()
        flash('Your settings have been updated.', 'success')
        return redirect(url_for('discover.discover'))
    elif request.method == 'GET':
        # Ensure preferences exist
        if not current_user.preferences:
            current_user.preferences = UserPreference(user_id=current_user.id)
            db.session.add(current_user.preferences)
            db.session.commit()
        
        form.items_per_page.data = current_user.preferences.items_per_page
        form.default_sort.data = current_user.preferences.default_sort
        form.default_sort_order.data = current_user.preferences.default_sort_order
        form.theme.data = current_user.preferences.theme or 'default'

    return render_template('settings/settings_panel.html', form=form)