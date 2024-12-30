# modules/routes_admin.py
from flask import Blueprint, render_template, redirect, url_for, current_app, jsonify, request, flash
from flask_login import login_required, current_user
from flask_mail import Message as MailMessage
from modules.utils_auth import admin_required
from modules.utils_processors import get_global_settings
from modules import app_version
from config import Config
from modules.utils_igdb_api import make_igdb_api_request
from modules.models import Whitelist, User, GlobalSettings
from modules import db, mail, cache
from modules.forms import WhitelistForm, NewsletterForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import flash
from uuid import uuid4
from modules import app_start_time
from modules.utils_logging import log_system_event

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
    return render_template('admin/admin_manage_discord_readme.html')


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
        log_system_event(f"Admin {current_user.name} deleted whitelist entry: {whitelist_entry.email}", event_type='audit', event_level='information')
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
            log_system_event(f"Admin {current_user.name} created new user: {data['username']}", event_type='audit', event_level='information')
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
        
        db.session.commit()
        log_system_event(f"Global settings updated by {current_user.name}", event_type='audit', event_level='information')
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
        return render_template('admin/admin_manage_server_settings.html', current_settings=current_settings)

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
    
    return render_template('admin/admin_manage_igdb_settings.html', settings=settings)

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
