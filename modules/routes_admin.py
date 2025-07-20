# modules/routes_admin.py
from flask import Blueprint, render_template, redirect, url_for, current_app, jsonify, request, flash
from flask_login import login_required, current_user
from flask_mail import Message as MailMessage
from modules.utils_auth import admin_required
from modules.utils_processors import get_global_settings
from modules import app_version
from config import Config
from modules.utils_igdb_api import make_igdb_api_request
from modules.models import Whitelist, User, Newsletter, GlobalSettings, Image, Game
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
    # Check if SMTP is configured and enabled
    if not settings_record or not settings_record.smtp_enabled:
        flash('SMTP is not configured or enabled. Please configure SMTP settings first.', 'warning')
        return redirect(url_for('site.admin_dashboard'))

    # Check if newsletter feature is enabled
    enable_newsletter = settings_record.settings.get('enableNewsletterFeature', False) if settings_record else False

    if not enable_newsletter:
        flash('Newsletter feature is disabled.', 'warning')
        return redirect(url_for('site.admin_dashboard'))

    # Verify SMTP sender is configured
    if not settings_record.smtp_default_sender:
        flash('SMTP default sender email is not configured.', 'warning')
        return redirect(url_for('site.admin_dashboard'))

    print("ADMIN NEWSLETTER: Processing", request.method, "request")
    form = NewsletterForm()
    users = User.query.all()
    if form.validate_on_submit():
        # First create the newsletter record
        recipients = form.recipients.data.split(',')        
        new_newsletter = Newsletter(
            subject=form.subject.data,
            content=form.content.data,
            sender_id=current_user.id,
            recipient_count=len(recipients),
            recipients=recipients,
            status='pending'
        )
        db.session.add(new_newsletter)
        db.session.commit()

        try:
            # Attempt to send the email
            msg = MailMessage(form.subject.data, sender=settings_record.smtp_default_sender)
            msg.html = form.content.data
            msg.recipients = recipients
            
            mail.send(msg)
            
            # Update status to sent
            new_newsletter.status = 'sent'
            db.session.commit()
            flash('Newsletter sent successfully!', 'success')
        except Exception as e:
            new_newsletter.status = 'failed'
            new_newsletter.error_message = str(e)
            db.session.commit()
            flash(str(e), 'error')
        return redirect(url_for('admin.newsletter'))
    
    # Get all sent newsletters for display
    newsletters = Newsletter.query.order_by(Newsletter.sent_date.desc()).all()
    return render_template('admin/admin_newsletter.html', 
                         title='Newsletter', 
                         form=form, 
                         users=users,
                         newsletters=newsletters)

@admin_bp.route('/admin/newsletter/<int:newsletter_id>')
@login_required
@admin_required
def view_newsletter(newsletter_id):
    newsletter = Newsletter.query.get_or_404(newsletter_id)
    return render_template('admin/view_newsletter.html', 
                         title='View Newsletter',
                         newsletter=newsletter)

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


@admin_bp.route('/admin/image_queue')
@login_required
@admin_required
def image_queue():
    """Display the image queue management interface."""
    return render_template('admin/admin_manage_image_queue.html')


@admin_bp.route('/admin/api/image_queue_stats')
@login_required
@admin_required
def image_queue_stats():
    """Get statistics about the image queue."""
    try:
        total_images = Image.query.count()
        pending_images = Image.query.filter_by(is_downloaded=False).count()
        downloaded_images = Image.query.filter_by(is_downloaded=True).count()
        
        # Get breakdown by image type
        pending_covers = Image.query.filter_by(is_downloaded=False, image_type='cover').count()
        pending_screenshots = Image.query.filter_by(is_downloaded=False, image_type='screenshot').count()
        
        # Get recent activity
        recent_downloads = Image.query.filter_by(is_downloaded=True).order_by(Image.created_at.desc()).limit(10).all()
        
        stats = {
            'total_images': total_images,
            'pending_images': pending_images,
            'downloaded_images': downloaded_images,
            'pending_covers': pending_covers,
            'pending_screenshots': pending_screenshots,
            'download_percentage': round((downloaded_images / total_images * 100) if total_images > 0 else 0, 1),
            'recent_downloads': [
                {
                    'id': img.id,
                    'game_name': img.game.name if img.game else 'Unknown',
                    'image_type': img.image_type,
                    'created_at': img.created_at.strftime('%Y-%m-%d %H:%M:%S')
                } for img in recent_downloads
            ]
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/api/image_queue_list')
@login_required
@admin_required
def image_queue_list():
    """Get paginated list of images in queue."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status', 'all')  # all, pending, downloaded
    type_filter = request.args.get('type', 'all')  # all, cover, screenshot
    
    query = Image.query.join(Game)
    
    # Apply filters
    if status_filter == 'pending':
        query = query.filter(Image.is_downloaded == False)
    elif status_filter == 'downloaded':
        query = query.filter(Image.is_downloaded == True)
    
    if type_filter != 'all':
        query = query.filter(Image.image_type == type_filter)
    
    # Order by creation date, pending first
    query = query.order_by(Image.is_downloaded.asc(), Image.created_at.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    images = pagination.items
    
    image_list = []
    for img in images:
        image_list.append({
            'id': img.id,
            'game_uuid': img.game_uuid,
            'game_name': img.game.name if img.game else 'Unknown',
            'image_type': img.image_type,
            'download_url': img.download_url,
            'is_downloaded': img.is_downloaded,
            'created_at': img.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'local_url': img.url if img.is_downloaded else None
        })
    
    return jsonify({
        'images': image_list,
        'pagination': {
            'page': page,
            'pages': pagination.pages,
            'per_page': per_page,
            'total': pagination.total,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })


@admin_bp.route('/admin/api/download_images', methods=['POST'])
@login_required
@admin_required
def download_images():
    """Trigger download of specific images or batch download."""
    data = request.json
    
    try:
        if 'image_ids' in data:
            # Download specific images
            from modules.utils_game_core import download_pending_images
            image_ids = data['image_ids']
            
            # Update the download function to accept specific IDs
            downloaded = 0
            for image_id in image_ids:
                image = Image.query.get(image_id)
                if image and not image.is_downloaded and image.download_url:
                    try:
                        import os
                        from modules.utils_functions import download_image
                        save_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], image.url)
                        download_image(image.download_url, save_path)
                        image.is_downloaded = True
                        downloaded += 1
                    except Exception as e:
                        print(f"Failed to download image {image_id}: {e}")
            
            db.session.commit()
            return jsonify({
                'success': True, 
                'downloaded': downloaded,
                'message': f'Downloaded {downloaded} images'
            })
            
        elif 'batch_size' in data:
            # Batch download
            from modules.utils_game_core import download_pending_images
            batch_size = data.get('batch_size', 10)
            downloaded = download_pending_images(batch_size=batch_size, delay_between_downloads=0.1, app=current_app)
            
            return jsonify({
                'success': True,
                'downloaded': downloaded,
                'message': f'Downloaded {downloaded} images'
            })
        
        else:
            return jsonify({'success': False, 'message': 'No valid parameters provided'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/admin/api/delete_image/<int:image_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_image(image_id):
    """Delete a specific image from queue."""
    try:
        image = Image.query.get_or_404(image_id)
        
        # Delete file if it exists
        if image.is_downloaded and image.url:
            import os
            file_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], image.url)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        db.session.delete(image)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Image deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/admin/api/retry_failed_images', methods=['POST'])
@login_required
@admin_required
def retry_failed_images():
    """Retry downloading images that failed."""
    try:
        # Find images that should be downloaded but aren't
        failed_images = Image.query.filter_by(is_downloaded=False).filter(Image.download_url.isnot(None)).all()
        
        retried = 0
        for image in failed_images:
            try:
                import os
                from modules.utils_functions import download_image
                save_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], image.url)
                download_image(image.download_url, save_path)
                image.is_downloaded = True
                retried += 1
            except Exception as e:
                print(f"Retry failed for image {image.id}: {e}")
                continue
        
        db.session.commit()
        return jsonify({
            'success': True,
            'retried': retried,
            'message': f'Retried {retried} failed images'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/admin/api/clear_downloaded_queue', methods=['POST'])
@login_required
@admin_required
def clear_downloaded_queue():
    """Remove all downloaded images from the queue view."""
    try:
        downloaded_count = Image.query.filter_by(is_downloaded=True).count()
        # Note: We don't actually delete them, just for display purposes
        # If you want to actually delete downloaded records, uncomment below:
        # Image.query.filter_by(is_downloaded=True).delete()
        # db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{downloaded_count} downloaded images cleared from view'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/admin/api/start_background_downloader', methods=['POST'])
@login_required
@admin_required
def start_background_downloader():
    """Start the background image downloader."""
    try:
        from modules.utils_game_core import start_background_image_downloader
        thread = start_background_image_downloader(interval_seconds=60)
        
        return jsonify({
            'success': True,
            'message': 'Background image downloader started successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/admin/api/turbo_download', methods=['POST'])
@login_required
@admin_required
def turbo_download():
    """TURBO MODE: Maximum speed parallel downloading with 5 threads."""
    try:
        data = request.json or {}
        batch_size = data.get('batch_size', 100)
        max_workers = data.get('max_workers', 5)
        
        from modules.utils_game_core import turbo_download_images
        result = turbo_download_images(batch_size=batch_size, max_workers=max_workers, app=current_app)
        
        return jsonify({
            'success': True,
            'downloaded': result['downloaded'],
            'failed': result['failed'],
            'message': result['message']
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/admin/api/start_turbo_downloader', methods=['POST'])
@login_required
@admin_required
def start_turbo_downloader():
    """Start the TURBO background downloader with parallel processing."""
    try:
        data = request.json or {}
        max_workers = data.get('max_workers', 4)
        batch_size = data.get('batch_size', 50)
        interval = data.get('interval', 30)
        
        from modules.utils_game_core import start_turbo_background_downloader
        thread = start_turbo_background_downloader(
            interval_seconds=interval, 
            max_workers=max_workers, 
            batch_size=batch_size
        )
        
        return jsonify({
            'success': True,
            'message': f'TURBO background downloader started! {max_workers} workers, {batch_size} batch size, {interval}s interval'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
