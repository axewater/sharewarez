# modules/routes_site.py
from flask import Blueprint, render_template, redirect, url_for, current_app, jsonify, request, flash
from flask_login import login_required, current_user
from flask_mail import Message as MailMessage
from modules.utils_auth import admin_required
from modules.models import SystemEvents
from modules.utils_themes import ThemeManager
from modules.discord_handler import DiscordWebhookHandler
from modules.utils_processors import get_global_settings
from modules import app_version
from config import Config
from modules.utils_igdb_api import make_igdb_api_request
from modules.models import Whitelist, User, GlobalSettings, InviteToken, ReleaseGroup, AllowedFileType, LibraryPlatform, Library
from modules import db, mail, cache
from modules.forms import WhitelistForm, NewsletterForm, ReleaseGroupForm, ThemeUploadForm, LibraryForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from datetime import datetime
from PIL import Image as PILImage
from werkzeug.utils import secure_filename
from flask import flash
from uuid import uuid4
import os
from modules import app_start_time

admin_bp = Blueprint('admin', __name__)

@admin_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()

@admin_bp.context_processor
def inject_current_theme():
    if current_user.is_authenticated and current_user.preferences:
        current_theme = current_user.preferences.theme or 'default'
    else:
        current_theme = 'default'
    return dict(current_theme=current_theme)


@admin_bp.route('/admin/discord_help')
@login_required
@admin_required
def discord_help():
    return render_template('admin/discord_help.html')


@admin_bp.route('/admin/whitelist', methods=['GET', 'POST'])
@login_required
@admin_required
def whitelist():
    form = WhitelistForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        new_whitelist = Whitelist(email=email)
        db.session.add(new_whitelist)
        try:
            db.session.commit()
            flash('The email was successfully added to the whitelist!', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('The email is already in the whitelist!', 'danger')
        return redirect(url_for('admin.whitelist'))

    # Get whitelist entries and check registration status
    whitelist_entries = Whitelist.query.all()
    for entry in whitelist_entries:
        entry.is_registered = User.query.filter(func.lower(User.email) == entry.email.lower()).first() is not None

    return render_template('admin/admin_manage_whitelist.html', 
                         title='Whitelist', 
                         whitelist=whitelist_entries, 
                         form=form)
    

@admin_bp.route('/admin/newsletter', methods=['GET', 'POST'])
@login_required
@admin_required
def newsletter():
    settings_record = GlobalSettings.query.first()
    enable_newsletter = settings_record.settings.get('enableNewsletterFeature', False) if settings_record else False

    if not enable_newsletter:
        flash('Newsletter feature is disabled.', 'warning')
        print("ADMIN NEWSLETTER: Newsletter feature is disabled.")
        return redirect(url_for('site.admin_dashboard'))
    print("ADMIN NEWSLETTER: Request method:", request.method)
    form = NewsletterForm()
    users = User.query.all()
    if form.validate_on_submit():
        recipients = form.recipients.data.split(',')
        print(f"ADMIN NEWSLETTER: Recipient list : {recipients}")
        
        msg = MailMessage(form.subject.data, sender=current_app.config['MAIL_DEFAULT_SENDER'])
        msg.body = form.content.data
        
        msg.recipients = recipients
        try:
            print(f"ADMIN NEWSLETTER: Newsletter sent")
            mail.send(msg)
            flash('Newsletter sent successfully!', 'success')
        except Exception as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.newsletter'))
    return render_template('admin/admin_newsletter.html', title='Newsletter', form=form, users=users)

@admin_bp.route('/admin/whitelist/<int:whitelist_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_whitelist(whitelist_id):
    try:
        whitelist_entry = Whitelist.query.get_or_404(whitelist_id)
        db.session.delete(whitelist_entry)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Entry deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/admin/users', methods=['GET'])
@login_required
@admin_required
def manage_users():
    users = User.query.all()
    return render_template('admin/admin_manage_users.html', users=users)

@admin_bp.route('/admin/api/user/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@admin_required
def manage_user_api(user_id):
    if request.method == 'PUT' and user_id == 0:  # Special case for new user creation
        data = request.json
        try:
            new_user = User(
                name=data['username'],
                email=data['email'],
                role=data.get('role', 'user'),
                state=data.get('state', True),
                is_email_verified=data.get('is_email_verified', True),
                user_id=str(uuid4())
            )
            new_user.set_password(data['password'])
            db.session.add(new_user)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    user = User.query.get_or_404(user_id)
    
    if request.method == 'GET':
        return jsonify({
            'email': user.email,
            'role': user.role,
            'state': user.state,
            'about': user.about,
            'is_email_verified': user.is_email_verified
        })
    
    elif request.method == 'PUT':
        if user_id == 1 and current_user.id != 1:
            return jsonify({'success': False, 'message': 'Cannot modify admin account'}), 403
        
        data = request.json
        user.email = data.get('email', user.email)
        user.role = data.get('role', user.role)
        user.state = data.get('state', user.state)
        user.is_email_verified = data.get('is_email_verified', user.is_email_verified)
        user.about = data.get('about', user.about)
        
        if data.get('password'):
            user.set_password(data['password'])
        
        try:
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
    
    elif request.method == 'DELETE':
        if user_id == 1:
            return jsonify({'success': False, 'message': 'Cannot delete admin account'}), 403
        
        try:
            db.session.delete(user)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
        

@admin_bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_settings():
    if request.method == 'POST':
        new_settings = request.json
        print(f"Received settings update: {new_settings}")
        
        settings_record = GlobalSettings.query.first()
        if not settings_record:
            settings_record = GlobalSettings(settings={})
            db.session.add(settings_record)

        # Update specific boolean fields
        settings_record.enable_delete_game_on_disk = new_settings.get('enableDeleteGameOnDisk', True)
        settings_record.discord_notify_new_games = new_settings.get('discordNotifyNewGames', False)
        settings_record.discord_notify_game_updates = new_settings.get('discordNotifyGameUpdates', False)
        settings_record.discord_notify_game_extras = new_settings.get('discordNotifyGameExtras', False)
        settings_record.discord_notify_downloads = new_settings.get('discordNotifyDownloads', False)
        settings_record.enable_main_game_updates = new_settings.get('enableMainGameUpdates', False)
        settings_record.enable_game_updates = new_settings.get('enableGameUpdates', False)
        settings_record.update_folder_name = new_settings.get('updateFolderName', 'updates')
        settings_record.enable_game_extras = new_settings.get('enableGameExtras', False)
        settings_record.extras_folder_name = new_settings.get('extrasFolderName', 'extras')
        settings_record.site_url = new_settings.get('siteUrl', 'http://127.0.0.1')
        
        # Update the settings JSON field
        settings_record.settings = new_settings
        settings_record.last_updated = datetime.utcnow()
        
        # Update specific boolean fields
        settings_record.enable_delete_game_on_disk = new_settings.get('enableDeleteGameOnDisk', True)
        settings_record.discord_notify_new_games = new_settings.get('discordNotifyNewGames', False)
        settings_record.discord_notify_game_updates = new_settings.get('discordNotifyGameUpdates', False)
        settings_record.discord_notify_game_extras = new_settings.get('discordNotifyGameExtras', False)
        settings_record.discord_notify_downloads = new_settings.get('discordNotifyDownloads', False)
        settings_record.enable_main_game_updates = new_settings.get('enableMainGameUpdates', False)
        settings_record.enable_game_updates = new_settings.get('enableGameUpdates', False)
        settings_record.update_folder_name = new_settings.get('updateFolderName', 'updates')
        settings_record.enable_game_extras = new_settings.get('enableGameExtras', False)
        settings_record.extras_folder_name = new_settings.get('extrasFolderName', 'extras')
        settings_record.site_url = new_settings.get('siteUrl', 'http://127.0.0.1')
        settings_record.last_updated = datetime.utcnow()
        
        settings_record.settings = new_settings
        settings_record.enable_delete_game_on_disk = new_settings.get('enableDeleteGameOnDisk', True)
        settings_record.discord_notify_new_games = new_settings.get('discordNotifyNewGames', False)
        settings_record.discord_notify_game_updates = new_settings.get('discordNotifyGameUpdates', False)
        settings_record.discord_notify_game_extras = new_settings.get('discordNotifyGameExtras', False)
        settings_record.discord_notify_downloads = new_settings.get('discordNotifyDownloads', False)
        settings_record.enable_main_game_updates = new_settings.get('enableMainGameUpdates', False)
        settings_record.enable_game_updates = new_settings.get('enableGameUpdates', False)
        settings_record.update_folder_name = new_settings.get('updateFolderName', 'updates')
        settings_record.enable_game_extras = new_settings.get('enableGameExtras', False)
        settings_record.extras_folder_name = new_settings.get('extrasFolderName', 'extras')
        settings_record.site_url = new_settings.get('siteUrl', 'http://127.0.0.1')
        settings_record.last_updated = datetime.utcnow()
        db.session.commit()
        cache.delete('global_settings')
        return jsonify({'message': 'Settings updated successfully'}), 200

    else:  # GET request
        settings_record = GlobalSettings.query.first()
        if not settings_record:
            # Initialize default settings if no record exists
            current_settings = {
                'showSystemLogo': True,
                'showHelpButton': True,
                'enableWebLinksOnDetailsPage': True,
                'enableServerStatusFeature': True,
                'enableNewsletterFeature': True,
                'showVersion': True,
                'enableDeleteGameOnDisk': True,
                'enableGameUpdates': True,
                'enableGameExtras': True,
                'siteUrl': 'http://127.0.0.1',
                'discordNotifyNewGames': False,
                'discordNotifyGameUpdates': False,
                'discordNotifyGameExtras': False,
                'discordNotifyDownloads': False,
                'enableMainGameUpdates': True,
                'updateFolderName': 'updates',
                'extrasFolderName': 'extras'
            }
        else:
            current_settings = settings_record.settings or {}
            current_settings['enableDeleteGameOnDisk'] = settings_record.enable_delete_game_on_disk
        current_settings['discordNotifyNewGames'] = settings_record.discord_notify_new_games if settings_record else False
        current_settings['discordNotifyGameUpdates'] = settings_record.discord_notify_game_updates if settings_record else False
        current_settings['discordNotifyGameExtras'] = settings_record.discord_notify_game_extras if settings_record else False
        current_settings['discordNotifyDownloads'] = settings_record.discord_notify_downloads if settings_record else False
        current_settings['enableMainGameUpdates'] = settings_record.enable_main_game_updates if settings_record else True
        current_settings['enableGameUpdates'] = settings_record.enable_game_updates if settings_record else True
        current_settings['updateFolderName'] = settings_record.update_folder_name if settings_record else 'updates'
        current_settings['enableGameExtras'] = settings_record.enable_game_extras if settings_record else True
        current_settings['extrasFolderName'] = settings_record.extras_folder_name if settings_record else 'extras'
        return render_template('admin/admin_server_settings.html', current_settings=current_settings)

@admin_bp.route('/admin/igdb_settings', methods=['GET', 'POST'])
@login_required
@admin_required
def igdb_settings():
    settings = GlobalSettings.query.first()
    if request.method == 'POST':
        data = request.json
        if not settings:
            settings = GlobalSettings()
            db.session.add(settings)
        
        settings.igdb_client_id = data.get('igdb_client_id')
        settings.igdb_client_secret = data.get('igdb_client_secret')
        
        try:
            db.session.commit()
            return jsonify({'status': 'success', 'message': 'IGDB settings updated successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    return render_template('admin/admin_igdb_settings.html', settings=settings)

@admin_bp.route('/admin/test_igdb', methods=['POST'])
@login_required
@admin_required
def test_igdb():
    print("Testing IGDB connection...")
    settings = GlobalSettings.query.first()
    if not settings or not settings.igdb_client_id or not settings.igdb_client_secret:
        return jsonify({'status': 'error', 'message': 'IGDB settings not configured'}), 400

    try:
        # Test the IGDB API with a simple query
        response = make_igdb_api_request('https://api.igdb.com/v4/games', 'fields name; limit 1;')
        if isinstance(response, list):
            print("IGDB API test successful")
            settings.igdb_last_tested = datetime.utcnow()
            db.session.commit()
            return jsonify({'status': 'success', 'message': 'IGDB API test successful'})
        else:
            print("IGDB API test failed")
            return jsonify({'status': 'error', 'message': 'Invalid API response'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    

@admin_bp.route('/admin/manage_invites', methods=['GET', 'POST'])
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

@admin_bp.route('/admin/edit_filters', methods=['GET', 'POST'])
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

@admin_bp.route('/delete_filter/<int:id>', methods=['GET'])
@login_required
@admin_required
def delete_filter(id):
    group_to_delete = ReleaseGroup.query.get_or_404(id)
    db.session.delete(group_to_delete)
    db.session.commit()
    flash('Release group filter removed.')
    return redirect(url_for('main.edit_filters'))


@admin_bp.route('/admin/extensions')
@login_required
@admin_required
def extensions():
    allowed_types = AllowedFileType.query.order_by(AllowedFileType.value.asc()).all()
    return render_template('admin/admin_manage_extensions.html', 
                         allowed_types=allowed_types)

@admin_bp.route('/admin/discord_settings', methods=['GET', 'POST'])
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
        
        return redirect(url_for('admin.discord_settings'))

    # Get default values from config if no settings exist
    webhook_url = settings.discord_webhook_url if settings else Config.DISCORD_WEBHOOK_URL
    bot_name = settings.discord_bot_name if settings else Config.DISCORD_BOT_NAME
    bot_avatar_url = settings.discord_bot_avatar_url if settings else Config.DISCORD_BOT_AVATAR_URL

    return render_template('admin/admin_discord_settings.html',
                         webhook_url=webhook_url,
                         bot_name=bot_name,
                         bot_avatar_url=bot_avatar_url)

@admin_bp.route('/admin/test_discord_webhook', methods=['POST'])
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
        return jsonify({'success': success, 'message': 'Test message sent successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/admin/themes', methods=['GET', 'POST'])
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

@admin_bp.route('/admin/themes/readme')
@login_required
@admin_required
def theme_readme():
    return render_template('admin/readme_theme.html')

@admin_bp.route('/admin/themes/delete/<theme_name>', methods=['POST'])
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

@admin_bp.route('/admin/library/add', methods=['GET', 'POST'])
@admin_bp.route('/admin/library/edit/<library_uuid>', methods=['GET', 'POST'])
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
            flash('Library saved successfully!', 'success')
            return redirect(url_for('library.libraries'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to save library. Please try again.', 'error')
            print(f"Error saving library: {e}")

    return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)

@admin_bp.route('/admin/system_logs')
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
    
    query = SystemEvents.query.order_by(SystemEvents.timestamp.desc())
    
    # Apply filters if they exist
    if event_type:
        query = query.filter(SystemEvents.event_type == event_type)
    if event_level:
        query = query.filter(SystemEvents.event_level == event_level)
    
    logs = query.paginate(page=page, per_page=per_page)
    return render_template('admin/admin_system_logs.html', logs=logs)
