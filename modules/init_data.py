import os
import zipfile
from modules import db
from modules.models import DiscoverySection

# Default allowed file types
DEFAULT_ALLOWED_FILE_TYPES = ['zip', 'rar', '7z', 'iso', 'nfo', 'nes', 'sfc', 'smc', 'sms', '32x', 'gen', 'gg', 'gba', 'gb', 'gbc', 'ndc', 'prg', 'dat', 'tap', 'z64', 'd64', 'dsk', 'img', 'bin', 'st', 'stx', 'j64', 'jag', 'lnx', 'adf', 'ngc', 'gz', 'm2v', 'ogg', 'fpt', 'fpl', 'vec', 'pce', 'a78', 'rom']

from modules.models import ReleaseGroup, GlobalSettings
from modules.utils_logging import log_system_event

def initialize_default_settings():
    """Initialize default global settings if they don't exist."""
    print("Initializing default global settings...")
    settings_record = GlobalSettings.query.first()
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

def initialize_library_folders():
    """Initialize the required folders and theme files for the application."""
    print("Initializing library folders...")
    library_path = os.path.join('modules', 'static', 'library')
    themes_path = os.path.join(library_path, 'themes')
    images_path = os.path.join(library_path, 'images')
    zips_path = os.path.join(library_path, 'zips')
    
    # Check if default theme exists
    if not os.path.exists(os.path.join(themes_path, 'default', 'theme.json')):
        print(f"Default theme not found at {os.path.join(themes_path, 'default', 'theme.json')}")
        log_system_event(f"Default theme not found at {os.path.join(themes_path, 'default', 'theme.json')}", event_type='startup', event_level='warning', audit_user='system')
        # Extract themes.zip
        themes_zip = os.path.join('modules', 'setup', 'themes.zip')
        if os.path.exists(themes_zip):
            with zipfile.ZipFile(themes_zip, 'r') as zip_ref:
                zip_ref.extractall(library_path)
            print("Themes extracted successfully")
        else:
            print("Warning: themes.zip not found in modules/setup/")
    else:
        print("Default theme found, skipping themes.zip extraction")
    # Create images folder if it doesn't exist
    if not os.path.exists(images_path):
        os.makedirs(images_path)
        print("Created images folder")

    # Create zips folder if it doesn't exist
    if not os.path.exists(zips_path):
        os.makedirs(zips_path)
        print("Created zips folder")

def insert_default_filters():
    """Initialize default release groups in the database."""
    default_name_filters = [
        {'rlsgroup': 'RAZOR', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'FLT', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'SKIDROW', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'CODEX', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'PLAZA', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'RELOADED', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'HOODLUM', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'CPY', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'FAIRLIGHT', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'HI2U', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'TiNYiSO', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'DARKSiDERS', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'Teke', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'Kw', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'PROPHET', 'rlsgroupcs': 'yes'},
        {'rlsgroup': 'GOG', 'rlsgroupcs': 'no'}, 
        {'rlsgroup': 'RUNE', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'Empress', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'AlcoholClone', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'DARKZER0', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'EMPRESS+Mr_Goldberg', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'ENGLISH-TL', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'ENLIGHT', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'FANiSO', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'FitGirl.Repack', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'FitGirl', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'I_KnoW', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'PROPER-CLONECD', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'Razor1911', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'TENOKE', 'rlsgroupcs': 'no'},
        {'rlsgroup': 'ZER0', 'rlsgroupcs': 'no'},
    ]

    existing_groups = ReleaseGroup.query.with_entities(ReleaseGroup.rlsgroup).all()
    existing_group_names = {group.rlsgroup for group in existing_groups}

    for group in default_name_filters:
        if group['rlsgroup'] not in existing_group_names:
            new_group = ReleaseGroup(rlsgroup=group['rlsgroup'], rlsgroupcs=group['rlsgroupcs'])
            db.session.add(new_group)
    db.session.commit()

def initialize_allowed_file_types():
    """Initialize default allowed file types if they don't exist."""
    from modules.models import AllowedFileType
    
    print("Initializing default allowed file types...")
    existing_types = {ft.value for ft in AllowedFileType.query.all()}
    
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
    existing_sections = {section.identifier for section in DiscoverySection.query.all()}

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
