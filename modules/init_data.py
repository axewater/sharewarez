import os
import shutil
from modules import db
from modules.models import DiscoverySection
from sqlalchemy import select

# Default allowed file types
DEFAULT_ALLOWED_FILE_TYPES = ['zip', 'rar', '7z', 'iso', 'nfo', 'nes', 'sfc', 'smc', 'sms', '32x', 'gen', 'gg', 'gba', 'gb', 'gbc', 'ndc', 'prg', 'dat', 'tap', 'z64', 'd64', 'dsk', 'img', 'bin', 'st', 'stx', 'j64', 'jag', 'lnx', 'adf', 'ngc', 'gz', 'm2v', 'ogg', 'fpt', 'fpl', 'vec', 'pce', 'a78', 'rom']

from modules.models import ReleaseGroup, GlobalSettings
from modules.utils_logging import log_system_event

def initialize_default_settings():
    """Initialize default global settings if they don't exist."""
    print("Initializing default global settings...")
    settings_record = db.session.execute(select(GlobalSettings)).scalars().first()
    if not settings_record:
        try:
            default_settings = {
                'showSystemLogo': True,
                'showHelpButton': True,
                'allowUsersToInviteOthers': True,
                'enableWebLinksOnDetailsPage': True,
                'enableServerStatusFeature': True,
                'enableNewsletterFeature': True,
                'showVersion': True
            }
            settings_record = GlobalSettings(settings=default_settings)
            db.session.add(settings_record)
            db.session.commit()
            print("Created default global settings")
        except Exception as e:
            print(f"Error creating default settings: {e}")
            db.session.rollback()
    else:
        # Settings exist, update only if settings field is empty
        if not settings_record.settings:
            try:
                default_settings = {
                    'showSystemLogo': True,
                    'showHelpButton': True,
                    'allowUsersToInviteOthers': True,
                    'enableWebLinksOnDetailsPage': True,
                    'enableServerStatusFeature': True,
                    'enableNewsletterFeature': True,
                    'showVersion': True
                }
                settings_record.settings = default_settings
                db.session.commit()
                print("Updated existing global settings with default values")
            except Exception as e:
                print(f"Error updating default settings: {e}")
                db.session.rollback()
        else:
            print("Global settings already exist with values, preserving them")

def initialize_library_folders():
    """Initialize the required folders and theme files for the application."""
    print("Initializing library folders...")
    library_path = os.path.join('modules', 'static', 'library')
    themes_path = os.path.join(library_path, 'themes')
    images_path = os.path.join(library_path, 'images')
    zips_path = os.path.join(library_path, 'zips')
    
    # Check if default theme exists
    default_theme_target = os.path.join(themes_path, 'default')
    if not os.path.exists(os.path.join(default_theme_target, 'theme.json')):
        print(f"Default theme not found at {os.path.join(default_theme_target, 'theme.json')}")
        log_system_event(f"Default theme not found at {os.path.join(default_theme_target, 'theme.json')}", event_type='startup', event_level='warning', audit_user='system')
        # Copy default theme from source directory
        default_theme_source = os.path.join('modules', 'setup', 'default_theme')
        if os.path.exists(default_theme_source):
            try:
                # Create themes directory if it doesn't exist
                os.makedirs(themes_path, exist_ok=True)
                # Copy the entire default theme directory
                shutil.copytree(default_theme_source, default_theme_target)
                print("Default theme copied successfully")
                log_system_event("Default theme copied successfully from source directory", event_type='startup', event_level='info', audit_user='system')
            except Exception as e:
                print(f"Error copying default theme: {str(e)}")
                log_system_event(f"Error copying default theme: {str(e)}", event_type='startup', event_level='error', audit_user='system')
        else:
            print("Warning: default theme source not found in modules/setup/default_theme")
            log_system_event("Warning: default theme source not found in modules/setup/default_theme", event_type='startup', event_level='warning', audit_user='system')
    else:
        print("Default theme found, skipping copy")
    # Create images folder if it doesn't exist
    if not os.path.exists(images_path):
        os.makedirs(images_path)
        print("Created images folder")

    # Create zips folder if it doesn't exist
    if not os.path.exists(zips_path):
        os.makedirs(zips_path)
        print("Created zips folder")

def insert_default_scanning_filters():
    """Initialize default scanning filters in the database."""
    default_name_filters = [
        {'filter_pattern': 'Open Source', 'case_sensitive': 'no'},
        {'filter_pattern': 'Public Domain', 'case_sensitive': 'no'},
        {'filter_pattern': 'GOG', 'case_sensitive': 'no'},
    ]

    existing_groups = db.session.execute(select(ReleaseGroup.filter_pattern)).scalars().all()
    existing_group_names = set(existing_groups)

    for group in default_name_filters:
        if group['filter_pattern'] not in existing_group_names:
            new_group = ReleaseGroup(filter_pattern=group['filter_pattern'], case_sensitive=group['case_sensitive'])
            db.session.add(new_group)
    db.session.commit()

def initialize_allowed_file_types():
    """Initialize default allowed file types if they don't exist."""
    from modules.models import AllowedFileType
    
    print("Initializing default allowed file types...")
    existing_types = {ft.value for ft in db.session.execute(select(AllowedFileType)).scalars().all()}
    
    for file_type in DEFAULT_ALLOWED_FILE_TYPES:
        if file_type not in existing_types:
            try:
                new_type = AllowedFileType(value=file_type)
                db.session.add(new_type)
            except Exception as e:
                print(f"Error adding file type {file_type}: {e}")
                db.session.rollback()
                continue
    
    try:
        db.session.commit()
        print("Created default allowed file types")
    except Exception as e:
        print(f"Error committing default file types: {e}")
        db.session.rollback()


def initialize_discovery_sections():
    """Initialize default discovery sections if they don't exist."""
    print("Initializing default discovery sections...")
    
    default_sections = [
        {
            'name': 'Libraries',
            'identifier': 'libraries',
            'is_visible': True,
            'display_order': 0
        },
        {
            'name': 'Latest Games',
            'identifier': 'latest_games',
            'is_visible': True,
            'display_order': 1
        },
        {
            'name': 'Most Downloaded',
            'identifier': 'most_downloaded',
            'is_visible': True,
            'display_order': 2
        },
        {
            'name': 'Highest Rated',
            'identifier': 'highest_rated',
            'is_visible': True,
            'display_order': 3
        },
        {
            'name': 'Last Updated',
            'identifier': 'last_updated',
            'is_visible': True,
            'display_order': 4
        },
        {
            'name': 'Most Favorited',
            'identifier': 'most_favorited',
            'is_visible': True,
            'display_order': 5
        }
    ]

    # Get existing section identifiers
    existing_sections = {section.identifier for section in db.session.execute(select(DiscoverySection)).scalars().all()}

    # Add any missing sections
    for section in default_sections:
        if section['identifier'] not in existing_sections:
            try:
                new_section = DiscoverySection(
                    name=section['name'],
                    identifier=section['identifier'],
                    is_visible=section['is_visible'],
                    display_order=section['display_order']
                )
                db.session.add(new_section)
                print(f"Adding discovery section: {section['name']}")
            except Exception as e:
                print(f"Error adding discovery section {section['name']}: {e}")
                db.session.rollback()
                continue

    try:
        db.session.commit()
        print("Default discovery sections initialized")
    except Exception as e:
        print(f"Error committing discovery sections: {e}")
        db.session.rollback()
