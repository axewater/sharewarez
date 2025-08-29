# /modules/routes_admin_ext/settings.py
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from modules.models import GlobalSettings
from modules import db, cache
from datetime import datetime
from . import admin2_bp
from modules.utils_logging import log_system_event
from modules.utils_auth import admin_required

@admin2_bp.route('/admin/settings', methods=['GET', 'POST'])
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
        # Image Download Settings  
        settings_record.use_turbo_image_downloads = new_settings.get('useTurboImageDownloads', True)
        settings_record.turbo_download_threads = new_settings.get('turboDownloadThreads', 8)
        settings_record.turbo_download_batch_size = new_settings.get('turboDownloadBatchSize', 200)
        # Scan Thread Settings
        scan_thread_count = new_settings.get('scanThreadCount', 1)
        if 1 <= scan_thread_count <= 4:
            settings_record.scan_thread_count = scan_thread_count
        else:
            settings_record.scan_thread_count = 1
        
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
        current_settings['siteUrl'] = settings_record.site_url if settings_record else 'http://127.0.0.1'
        # Image Download Settings
        current_settings['useTurboImageDownloads'] = settings_record.use_turbo_image_downloads if settings_record else True
        current_settings['turboDownloadThreads'] = settings_record.turbo_download_threads if settings_record else 8
        current_settings['turboDownloadBatchSize'] = settings_record.turbo_download_batch_size if settings_record else 200
        # Scan Thread Settings
        current_settings['scanThreadCount'] = settings_record.scan_thread_count if settings_record else 1
        return render_template('admin/admin_manage_server_settings.html', current_settings=current_settings)
