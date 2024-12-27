import os
import zipfile
from modules import db
from modules.models import ReleaseGroup

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
        
        # Extract themes.zip
        themes_zip = os.path.join('modules', 'setup', 'themes.zip')
        if os.path.exists(themes_zip):
            with zipfile.ZipFile(themes_zip, 'r') as zip_ref:
                zip_ref.extractall(library_path)
            print("Themes extracted successfully")
        else:
            print("Warning: themes.zip not found in modules/setup/")

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
