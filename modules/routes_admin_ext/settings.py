# /modules/routes_admin_ext/settings.py
from flask import render_template, request, jsonify, abort
from flask_login import login_required, current_user
from modules.models import GlobalSettings
from modules import db, cache
from sqlalchemy import select
from datetime import datetime, timezone
from . import admin2_bp
from modules.utils_logging import log_system_event
from modules.utils_auth import admin_required
from modules.utils_igdb_api import make_igdb_api_request
import logging

# Configuration constants
MIN_SCAN_THREADS = 1
MAX_SCAN_THREADS = 4
MIN_DOWNLOAD_THREADS = 1
MAX_DOWNLOAD_THREADS = 20
MIN_BATCH_SIZE = 10
MAX_BATCH_SIZE = 1000
DEFAULT_BATCH_SIZE = 200
DEFAULT_DOWNLOAD_THREADS = 8

# Default settings configuration
DEFAULT_SETTINGS = {
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
    'discordNotifyManualTrigger': False,
    'updateFolderName': 'updates',
    'extrasFolderName': 'extras',
    'useTurboImageDownloads': True,
    'turboDownloadThreads': DEFAULT_DOWNLOAD_THREADS,
    'turboDownloadBatchSize': DEFAULT_BATCH_SIZE,
    'scanThreadCount': 1
}

# Field mappings for database columns
FIELD_MAPPINGS = {
    'enableDeleteGameOnDisk': 'enable_delete_game_on_disk',
    'discordNotifyNewGames': 'discord_notify_new_games',
    'discordNotifyGameUpdates': 'discord_notify_game_updates',
    'discordNotifyGameExtras': 'discord_notify_game_extras',
    'discordNotifyDownloads': 'discord_notify_downloads',
    'discordNotifyManualTrigger': 'discord_notify_manual_trigger',
    'enableGameUpdates': 'enable_game_updates',
    'updateFolderName': 'update_folder_name',
    'enableGameExtras': 'enable_game_extras',
    'extrasFolderName': 'extras_folder_name',
    'siteUrl': 'site_url',
    'useTurboImageDownloads': 'use_turbo_image_downloads',
    'turboDownloadThreads': 'turbo_download_threads',
    'turboDownloadBatchSize': 'turbo_download_batch_size',
    'scanThreadCount': 'scan_thread_count'
}


def validate_settings_data(settings_data):
    """Validate settings data and return errors if any."""
    errors = []
    
    if not isinstance(settings_data, dict):
        errors.append("Settings data must be a JSON object")
        return errors
    
    # Validate scan thread count
    scan_threads = settings_data.get('scanThreadCount')
    if scan_threads is not None:
        if not isinstance(scan_threads, int) or not (MIN_SCAN_THREADS <= scan_threads <= MAX_SCAN_THREADS):
            errors.append(f"Scan thread count must be between {MIN_SCAN_THREADS} and {MAX_SCAN_THREADS}")
    
    # Validate download threads
    download_threads = settings_data.get('turboDownloadThreads')
    if download_threads is not None:
        if not isinstance(download_threads, int) or not (MIN_DOWNLOAD_THREADS <= download_threads <= MAX_DOWNLOAD_THREADS):
            errors.append(f"Download threads must be between {MIN_DOWNLOAD_THREADS} and {MAX_DOWNLOAD_THREADS}")
    
    # Validate batch size
    batch_size = settings_data.get('turboDownloadBatchSize')
    if batch_size is not None:
        if not isinstance(batch_size, int) or not (MIN_BATCH_SIZE <= batch_size <= MAX_BATCH_SIZE):
            errors.append(f"Batch size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}")
    
    # Validate folder names
    for folder_field in ['updateFolderName', 'extrasFolderName']:
        folder_name = settings_data.get(folder_field)
        if folder_name is not None:
            if not isinstance(folder_name, str) or not folder_name.strip():
                errors.append(f"{folder_field} must be a non-empty string")
            elif len(folder_name) > 100:
                errors.append(f"{folder_field} must be less than 100 characters")
    
    # Validate site URL
    site_url = settings_data.get('siteUrl')
    if site_url is not None:
        if not isinstance(site_url, str) or not site_url.strip():
            errors.append("Site URL must be a non-empty string")
        elif len(site_url) > 500:
            errors.append("Site URL must be less than 500 characters")
    
    return errors


def get_or_create_settings_record():
    """Get existing settings record or create a new one."""
    settings_record = db.session.execute(select(GlobalSettings)).scalars().first()
    if not settings_record:
        settings_record = GlobalSettings(settings={})
        db.session.add(settings_record)
        db.session.flush()  # Ensure record has an ID
    return settings_record


def update_settings_fields(settings_record, new_settings):
    """Update individual database fields from settings data."""
    for json_field, db_field in FIELD_MAPPINGS.items():
        if json_field in new_settings:
            # Skip scanThreadCount here - it will be handled with validation below
            if json_field == 'scanThreadCount':
                continue
            setattr(settings_record, db_field, new_settings[json_field])
    
    # Apply validation for specific fields
    scan_threads = new_settings.get('scanThreadCount')
    if scan_threads is not None and MIN_SCAN_THREADS <= scan_threads <= MAX_SCAN_THREADS:
        settings_record.scan_thread_count = scan_threads
    
    # Update the settings JSON field and timestamp
    settings_record.settings = new_settings
    settings_record.last_updated = datetime.now(timezone.utc)


def build_current_settings(settings_record):
    """Build current settings dictionary from database record."""
    if not settings_record:
        return DEFAULT_SETTINGS.copy()
    
    # Start with stored JSON settings
    current_settings = settings_record.settings.copy() if settings_record.settings else {}
    
    # Merge with default settings for any missing keys
    for key, default_value in DEFAULT_SETTINGS.items():
        if key not in current_settings:
            current_settings[key] = default_value
    
    # Override with individual database field values
    for json_field, db_field in FIELD_MAPPINGS.items():
        db_value = getattr(settings_record, db_field, None)
        if db_value is not None:
            current_settings[json_field] = db_value
    
    return current_settings


@admin2_bp.route('/admin/settings', methods=['GET'])
@login_required
@admin_required
def get_settings():
    """Handle GET requests for settings page."""
    try:
        settings_record = db.session.execute(select(GlobalSettings)).scalars().first()
        current_settings = build_current_settings(settings_record)
        return render_template('admin/admin_manage_server_settings.html', current_settings=current_settings)
    except Exception as e:
        logging.error(f"Error retrieving settings: {str(e)}")
        abort(500)


@admin2_bp.route('/admin/settings', methods=['POST'])
@login_required
@admin_required
def update_settings():
    """Handle POST requests for updating settings."""
    try:
        # Validate request has JSON content
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        new_settings = request.get_json()
        if not new_settings:
            return jsonify({'error': 'No settings data provided'}), 400
        
        # Validate settings data
        validation_errors = validate_settings_data(new_settings)
        if validation_errors:
            return jsonify({'errors': validation_errors}), 400
        
        logging.info(f"Updating settings: {list(new_settings.keys())}")
        
        # Get or create settings record
        settings_record = get_or_create_settings_record()
        
        # Update settings fields
        update_settings_fields(settings_record, new_settings)
        
        # Commit changes
        db.session.commit()
        
        # Log and clear cache
        log_system_event(
            f"Global settings updated by {current_user.name}. Updated fields: {', '.join(new_settings.keys())}", 
            event_type='audit', 
            event_level='information'
        )
        cache.delete('global_settings')
        
        return jsonify({'message': 'Settings updated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating settings: {str(e)}")
        return jsonify({'error': 'Failed to update settings'}), 500


# Maintain backward compatibility with existing route
@admin2_bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_settings():
    """Legacy route handler that delegates to appropriate method."""
    if request.method == 'POST':
        return update_settings()
    else:
        return get_settings()


# New Settings Management Routes

@admin2_bp.route('/admin/new_server_settings', methods=['GET', 'POST'])
@login_required
@admin_required
def new_server_settings():
    """Handle new server settings page - same functionality as original."""
    if request.method == 'POST':
        return update_settings()
    else:
        try:
            settings_record = db.session.execute(select(GlobalSettings)).scalars().first()
            current_settings = build_current_settings(settings_record)
            return render_template('admin/new_server_settings.html', current_settings=current_settings)
        except Exception as e:
            logging.error(f"Error retrieving settings: {str(e)}")
            abort(500)


@admin2_bp.route('/admin/integrations', methods=['GET'])
@login_required
@admin_required
def integrations():
    """Handle integrations page with tabbed interface for email, IGDB, and discord settings."""
    try:
        # Get global settings for all integrations
        settings_record = db.session.execute(select(GlobalSettings)).scalars().first()

        return render_template('admin/integrations.html', settings=settings_record)
    except Exception as e:
        logging.error(f"Error retrieving integrations: {str(e)}")
        abort(500)


@admin2_bp.route('/admin/integrations/igdb/save', methods=['POST'])
@login_required
@admin_required
def integrations_igdb_save():
    """Handle IGDB settings save from integrations page."""
    try:
        data = request.json
        settings = db.session.execute(select(GlobalSettings)).scalars().first()

        if not settings:
            settings = GlobalSettings()
            db.session.add(settings)

        # Validate input
        client_id = data.get('igdb_client_id', '').strip()
        client_secret = data.get('igdb_client_secret', '').strip()

        if len(client_id) < 20 or len(client_secret) < 20:
            return jsonify({
                'status': 'error',
                'message': 'Client ID and Secret must be at least 20 characters long'
            }), 400

        settings.igdb_client_id = client_id
        settings.igdb_client_secret = client_secret

        db.session.commit()
        log_system_event("IGDB settings updated via integrations page")

        return jsonify({'status': 'success', 'message': 'IGDB settings saved successfully'})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving IGDB settings from integrations: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@admin2_bp.route('/admin/integrations/igdb/test', methods=['POST'])
@login_required
@admin_required
def integrations_igdb_test():
    """Handle IGDB settings test from integrations page."""
    try:
        logging.info("Testing IGDB connection from integrations page...")
        settings = db.session.execute(select(GlobalSettings)).scalars().first()

        if not settings or not settings.igdb_client_id or not settings.igdb_client_secret:
            return jsonify({
                'status': 'error',
                'message': 'IGDB settings not configured. Please save your settings first.'
            }), 400

        # Test the IGDB API with a simple query
        response = make_igdb_api_request('https://api.igdb.com/v4/games', 'fields name; limit 1;')

        if isinstance(response, list):
            logging.info("IGDB API test successful from integrations page")
            settings.igdb_last_tested = datetime.now(timezone.utc)
            db.session.commit()
            log_system_event("IGDB API test successful via integrations page")
            return jsonify({'status': 'success', 'message': 'IGDB API test successful'})
        else:
            logging.warning("IGDB API test failed - invalid response")
            return jsonify({'status': 'error', 'message': 'Invalid API response'}), 500

    except Exception as e:
        logging.error(f"Error testing IGDB from integrations: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500