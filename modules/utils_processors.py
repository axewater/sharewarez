from modules import db
from modules.models import GlobalSettings
from sqlalchemy import select
from modules import app_version
import json

def get_loc(page):
    
    with open(f'modules/static/localization/en/{page}.json', 'r', encoding='utf8') as f:
            loc_data = json.load(f)    
    return loc_data

def get_global_settings():
    """Helper function to get global settings with defaults"""
    settings_record = db.session.execute(select(GlobalSettings)).scalars().first()
    default_settings = {
        'showSystemLogo': True,
        'showHelpButton': True,
        'allowUsersToInviteOthers': False,
        'enableGameUpdates': True,
        'updateFolderName': 'updates',
        'enableGameExtras': True,
        'extrasFolderName': 'extras',
        'discordNotifyNewGames': False,
        'discordNotifyGameUpdates': False,
        'discordNotifyGameExtras': False,
        'discordNotifyDownloads': False,
        'siteUrl': 'http://127.0.0.1',
        'showSystemLogo': True,
        'showHelpButton': True,
        'enableWebLinksOnDetailsPage': True,
        'enableServerStatusFeature': True,
        'enableNewsletterFeature': True,
        'showVersion': True,
        'enableDeleteGameOnDisk': True,
        'enableGameUpdates': True,
        'enableGameExtras': True,
        'siteUrl': 'http://127.0.0.1'
    }
    
    settings = default_settings.copy()
    
    if settings_record and settings_record.settings:
        settings.update(settings_record.settings)
        return {
            'show_logo': settings.get('showSystemLogo'),
            'show_help_button': settings.get('showHelpButton'),
            'enable_web_links': settings.get('enableWebLinksOnDetailsPage'),
            'enable_server_status': settings_record.settings.get('enableServerStatusFeature', False),
            'enable_newsletter': settings_record.settings.get('enableNewsletterFeature', False),
            'show_version': settings_record.settings.get('showVersion', False),
            'enable_delete_game_on_disk': settings_record.settings.get('enableDeleteGameOnDisk', True),
            'enable_game_updates': settings_record.settings.get('enableGameUpdates', True),
            'enable_game_extras': settings_record.settings.get('enableGameExtras', True),
            'discord_configured': bool(settings_record.discord_webhook_url),
            'discord_manual_trigger_enabled': settings_record.discord_notify_manual_trigger if settings_record else False,
            'app_version': app_version
        }
    
    # Return default values if no settings_record is found
    return {
        'show_logo': True,
        'show_help_button': True,
        'enable_web_links': True,
        'enable_server_status': True,
        'enable_newsletter': True,
        'show_version': True,
        'enable_delete_game_on_disk': True,
        'enable_game_updates': True,
        'enable_game_extras': True,
        'discord_configured': False,
        'discord_manual_trigger_enabled': False,
        'app_version': app_version
    }