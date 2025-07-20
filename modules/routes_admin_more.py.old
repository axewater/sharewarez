from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from modules.utils_auth import admin_required
from modules.models import User, InviteToken, ReleaseGroup, AllowedFileType, GlobalSettings, SystemEvents, Library, LibraryPlatform, DiscoverySection
from modules import db, cache
from modules.forms import ReleaseGroupForm, ThemeUploadForm, LibraryForm
from modules.utils_processors import get_global_settings
from modules.discord_handler import DiscordWebhookHandler
from modules.utils_themes import ThemeManager
from modules.utils_logging import log_system_event
from PIL import Image as PILImage
from uuid import uuid4
from werkzeug.utils import secure_filename
import os
import zipfile


admin2_bp = Blueprint('admin2', __name__)

@admin2_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()

@admin2_bp.route('/admin/help')
@login_required
@admin_required
def admin_help():
    """Display the administrator help page"""
    return render_template('admin/admin_help.html')

@admin2_bp.route('/admin/manage_invites', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_invites():

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        invites_number = int(request.form.get('invites_number'))

        user = User.query.filter_by(user_id=user_id).first()
        if user:
            user.invite_quota += invites_number
            db.session.commit()
            flash('Invites updated successfully.', 'success')
        else:
            flash('User not found.', 'error')

    users = User.query.all()
    # Calculate unused invites for each user
    user_unused_invites = {}
    for user in users:
        unused_count = InviteToken.query.filter_by(
            creator_user_id=user.user_id,
            used=False
        ).count()
        user_unused_invites[user.user_id] = unused_count

    return render_template('admin/admin_manage_invites.html', 
                         users=users, 
                         user_unused_invites=user_unused_invites)

@admin2_bp.route('/admin/edit_filters', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_filters():
    form = ReleaseGroupForm()
    if form.validate_on_submit():
        new_group = ReleaseGroup(rlsgroup=form.rlsgroup.data, rlsgroupcs=form.rlsgroupcs.data)
        db.session.add(new_group)
        db.session.commit()
        flash('New release group filter added.')
        return redirect(url_for('main.edit_filters'))
    groups = ReleaseGroup.query.order_by(ReleaseGroup.rlsgroup.asc()).all()
    return render_template('admin/admin_manage_filters.html', form=form, groups=groups)

@admin2_bp.route('/delete_filter/<int:id>', methods=['GET'])
@login_required
@admin_required
def delete_filter(id):
    group_to_delete = ReleaseGroup.query.get_or_404(id)
    db.session.delete(group_to_delete)
    db.session.commit()
    flash('Release group filter removed.')
    return redirect(url_for('main.edit_filters'))


@admin2_bp.route('/admin/extensions')
@login_required
@admin_required
def extensions():
    allowed_types = AllowedFileType.query.order_by(AllowedFileType.value.asc()).all()
    return render_template('admin/admin_manage_extensions.html', 
                         allowed_types=allowed_types)

@admin2_bp.route('/admin/discord_settings', methods=['GET', 'POST'])
@login_required
@admin_required
def discord_settings():
    settings = GlobalSettings.query.first()
    
    if request.method == 'POST':
        if not settings:
            settings = GlobalSettings()
            db.session.add(settings)
        
        settings.discord_webhook_url = request.form.get('discord_webhook_url', '')
        settings.discord_bot_name = request.form.get('discord_bot_name', '')
        settings.discord_bot_avatar_url = request.form.get('discord_bot_avatar_url', '')
        
        try:
            db.session.commit()
            flash('Discord settings updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating Discord settings: {str(e)}', 'error')
        
        return redirect(url_for('admin2.discord_settings'))

    # Set default values if no settings exist
    webhook_url = settings.discord_webhook_url if settings else 'insert_webhook_url_here'
    bot_name = settings.discord_bot_name if settings else 'SharewareZ Bot'
    bot_avatar_url = settings.discord_bot_avatar_url if settings else 'insert_bot_avatar_url_here'

    return render_template('admin/admin_manage_discord_settings.html',
                         webhook_url=webhook_url,
                         bot_name=bot_name,
                         bot_avatar_url=bot_avatar_url)

@admin2_bp.route('/admin/test_discord_webhook', methods=['POST'])
@login_required
@admin_required
def test_discord_webhook():
    data = request.json
    webhook_url = data.get('webhook_url')
    bot_name = data.get('bot_name')
    bot_avatar_url = data.get('bot_avatar_url')

    if not webhook_url:
        return jsonify({'success': False, 'message': 'Webhook URL is required'}), 400

    handler = DiscordWebhookHandler(webhook_url, bot_name, bot_avatar_url)
    
    try:
        embed = handler.create_embed(
            title="Discord Webhook Test",
            description="This is a test message from your SharewareZ instance.",
            color="03b2f8"
        )
        success = handler.send_webhook(embed)
        if success:
            return jsonify({'success': True, 'message': 'Test message sent successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to send test message'}), 500
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        error_message = f"Discord webhook error: {str(e)}"
        print(error_message)
        return jsonify({'success': False, 'message': error_message}), 500

@admin2_bp.route('/admin/themes', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_themes():
    form = ThemeUploadForm()
    theme_manager = ThemeManager(current_app)
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'themes')
    if not os.path.exists(upload_folder):
        try:
            # Safe check to avoid creating 'static' directly
            os.makedirs(upload_folder, exist_ok=True)
        except Exception as e:
            print(f"Error creating upload directory: {e}")
            flash("Error processing request. Please try again.", 'error')
            return redirect(url_for('main.manage_themes'))

    if form.validate_on_submit():
        theme_zip = form.theme_zip.data
        try:
            theme_data = theme_manager.upload_theme(theme_zip)
            if theme_data:
                flash(f"Theme '{theme_data['name']}' uploaded successfully!", 'success')
            else:
                flash("Theme upload failed. Please check the error messages.", 'error')
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash(f"An unexpected error occurred: {str(e)}", 'error')
        return redirect(url_for('main.manage_themes'))

    installed_themes = theme_manager.get_installed_themes()
    default_theme = theme_manager.get_default_theme()
    return render_template('admin/admin_manage_themes.html', form=form, themes=installed_themes, default_theme=default_theme)

@admin2_bp.route('/admin/themes/readme')
@login_required
@admin_required
def theme_readme():
    return render_template('admin/admin_manage_themes_readme.html')

@admin2_bp.route('/admin/themes/delete/<theme_name>', methods=['POST'])
@login_required
@admin_required
def delete_theme(theme_name):
    theme_manager = ThemeManager(current_app)
    try:
        theme_manager.delete_themefile(theme_name)
        flash(f"Theme '{theme_name}' deleted successfully!", 'success')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", 'error')
    return redirect(url_for('admin.manage_themes'))

@admin2_bp.route('/admin/library/add', methods=['GET', 'POST'])
@admin2_bp.route('/admin/library/edit/<library_uuid>', methods=['GET', 'POST'])
@login_required
@admin_required
def add_edit_library(library_uuid=None):
    if library_uuid:
        library = Library.query.filter_by(uuid=library_uuid).first_or_404()
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
            # Validate file size (< 5 MB)
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            if file_length > 5 * 1024 * 1024:  # 5MB limit
                flash('File size is too large. Maximum allowed is 5 MB.', 'error')
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

@admin2_bp.route('/admin/system_logs')
@login_required
@admin_required
def system_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Get filter parameters
    event_type = request.args.get('event_type')
    event_level = request.args.get('event_level')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = SystemEvents.query\
        .options(db.joinedload(SystemEvents.user))\
        .order_by(SystemEvents.timestamp.desc())
    
    # Apply filters if they exist
    if event_type:
        query = query.filter(SystemEvents.event_type == event_type)
    if event_level:
        query = query.filter(SystemEvents.event_level == event_level)
    
    logs = query.paginate(page=page, per_page=per_page)
    return render_template('admin/admin_server_logs.html', logs=logs)

@admin2_bp.route('/admin/discovery_sections')
@login_required
@admin_required
def discovery_sections():
    sections = DiscoverySection.query.order_by(DiscoverySection.display_order).all()
    return render_template('admin/admin_discovery_sections.html', sections=sections)

@admin2_bp.route('/admin/api/discovery_sections/order', methods=['POST'])
@login_required
@admin_required
def update_section_order():
    try:
        data = request.json
        for section_data in data['sections']:
            section = DiscoverySection.query.get(section_data['id'])
            if section:
                section.display_order = section_data['order']
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@admin2_bp.route('/admin/api/discovery_sections/visibility', methods=['POST'])
@login_required
@admin_required
def update_section_visibility():
    try:
        data = request.json
        section = DiscoverySection.query.get(data['section_id'])
        if section:
            section.is_visible = data['is_visible']
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Section not found'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@admin2_bp.route('/admin/themes/reset', methods=['POST'])
@login_required
@admin_required
def reset_default_themes():
    try:
        themes_zip = os.path.join('modules', 'setup', 'themes.zip')
        if not os.path.exists(themes_zip):
            flash('Error: themes.zip not found in modules/setup/', 'error')
            log_system_event(
                "Failed to reset default themes: themes.zip not found",
                event_type='themes',
                event_level='error'
            )
            return redirect(url_for('admin2.manage_themes'))

        library_path = os.path.join('modules', 'static', 'library')
        log_details = []
        
        print("Starting default themes reset...")
        with zipfile.ZipFile(themes_zip, 'r') as zip_ref:
            files_list = zip_ref.namelist()
            print(f"Found {len(files_list)} files in themes.zip")
            
            for file in files_list:
                try:
                    zip_ref.extract(file, library_path)
                    log_message = f"Successfully extracted: {file}"
                    print(log_message)
                    log_details.append(log_message)
                except Exception as e:
                    error_message = f"Failed to extract {file}: {str(e)}"
                    print(error_message)
                    log_details.append(error_message)

        successful_extracts = len([log for log in log_details if log.startswith("Successfully")])
        failed_extracts = len([log for log in log_details if log.startswith("Failed")])
        
        summary = f"Default themes reset: {successful_extracts} files extracted successfully, {failed_extracts} failed"
        full_log = "\n".join(log_details)
        log_system_event(
            f"{summary}\nDetails:\n{full_log}",
            event_type='themes',
            event_level='information' if failed_extracts == 0 else 'warning'
        )

        if failed_extracts == 0:
            flash('Default themes have been reset successfully!', 'success')
        else:
            flash(f'Default themes reset completed with {failed_extracts} errors. Check system logs for details.', 'warning')

    except Exception as e:
        error_message = f"Error resetting default themes: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
        log_system_event(error_message, event_type='themes', event_level='error')

    return redirect(url_for('admin2.manage_themes'))
