"""
Standalone database initialization for SharewareZ startup.
This module handles all database operations using pure SQLAlchemy,
completely separate from Flask app creation.
"""

import os
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker
from config import Config


def run_complete_startup_initialization():
    """
    Run all startup initialization tasks using pure SQLAlchemy.
    No Flask app creation involved.
    """
    print("Running database migrations and initialization...")
    
    try:
        # Step 1: Run database migrations
        print("Running database migrations...")
        from modules.updateschema import DatabaseManager
        db_manager = DatabaseManager()
        db_manager.add_column_if_not_exists()
        print("Database migrations completed successfully.")
        
        # Step 2: Initialize database with pure SQLAlchemy
        print("🔧 Initializing database with default data")
        _initialize_with_sqlalchemy()
        
        print("Initialization completed successfully")
        return True
        
    except Exception as e:
        print(f"Error during startup initialization: {e}")
        import traceback
        traceback.print_exc()
        return False


def _initialize_with_sqlalchemy():
    """Initialize database using pure SQLAlchemy without Flask."""
    # Create SQLAlchemy engine and session
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # Import models to register them
        from modules import models
        
        # Create all tables
        models.db.metadata.create_all(engine)
        
        # Initialize data
        _initialize_library_folders(session)
        _initialize_discovery_sections(session)
        _initialize_release_groups(session)
        _initialize_default_settings(session)
        _initialize_allowed_file_types(session)
        _cleanup_orphaned_scan_jobs(session)
        
        # Log system event
        _log_system_event(session)
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def _initialize_library_folders(session):
    """Initialize library folders and themes (filesystem operations)."""
    print("Initializing library folders...")
    
    # This mirrors the original init_data.initialize_library_folders() function
    library_path = os.path.join('modules', 'static', 'library')
    themes_path = os.path.join(library_path, 'themes')
    images_path = os.path.join(library_path, 'images')
    zips_path = os.path.join(library_path, 'zips')
    
    # Check if default theme exists
    if not os.path.exists(os.path.join(themes_path, 'default', 'theme.json')):
        # Extract themes.zip
        themes_zip = os.path.join('modules', 'setup', 'themes.zip')
        if os.path.exists(themes_zip):
            import zipfile
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


def _initialize_discovery_sections(session):
    """Initialize default discovery sections."""
    print("Initializing default discovery sections...")
    from modules.models import DiscoverySection
    
    existing_sections = session.execute(select(DiscoverySection)).scalars().first()
    if not existing_sections:
        default_sections = [
            DiscoverySection(name='Latest Additions', filter_type='latest', is_enabled=True, sort_order=1),
            DiscoverySection(name='Random Selection', filter_type='random', is_enabled=True, sort_order=2),
            DiscoverySection(name='Most Downloaded', filter_type='popular', is_enabled=True, sort_order=3)
        ]
        for section in default_sections:
            session.add(section)
        print("Default discovery sections initialized")
    else:
        print("Discovery sections already exist")


def _initialize_release_groups(session):
    """Initialize default release groups."""
    from modules.models import ReleaseGroup
    
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

    existing_groups = session.execute(select(ReleaseGroup.rlsgroup)).scalars().all()
    existing_group_names = set(existing_groups)

    for group in default_name_filters:
        if group['rlsgroup'] not in existing_group_names:
            new_group = ReleaseGroup(rlsgroup=group['rlsgroup'], rlsgroupcs=group['rlsgroupcs'])
            session.add(new_group)


def _initialize_default_settings(session):
    """Initialize default global settings."""
    print("Initializing default global settings...")
    from modules.models import GlobalSettings
    
    settings_record = session.execute(select(GlobalSettings)).scalars().first()
    if not settings_record:
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
        session.add(settings_record)
        print("Created default global settings")
    else:
        print("Global settings already exist with values, preserving them")


def _initialize_allowed_file_types(session):
    """Initialize default allowed file types."""
    print("Initializing default allowed file types...")
    from modules.models import AllowedFileType
    
    existing_types = session.execute(select(AllowedFileType)).scalars().first()
    if not existing_types:
        default_types = ['zip', 'rar', '7z', 'iso', 'nfo', 'nes', 'sfc', 'smc', 'sms', '32x', 'gen', 'gg', 'gba', 'gb', 'gbc', 'ndc', 'prg', 'dat', 'tap', 'z64', 'd64', 'dsk', 'img', 'bin', 'st', 'stx', 'j64', 'jag', 'lnx', 'adf', 'ngc', 'gz', 'm2v', 'ogg', 'fpt', 'fpl', 'vec', 'pce', 'a78', 'rom']
        
        for file_type in default_types:
            allowed_type = AllowedFileType(extension=file_type)
            session.add(allowed_type)
        print("Created default allowed file types")
    else:
        print("Allowed file types already exist")


def _cleanup_orphaned_scan_jobs(session):
    """Clean up scan jobs that were left in 'Running' state after server restart."""
    try:
        from modules.models import ScanJob
        
        # Find all jobs that are still marked as 'Running'
        running_jobs = session.execute(select(ScanJob).filter_by(status='Running')).scalars().all()
        
        if running_jobs:
            print(f"Found {len(running_jobs)} orphaned scan job(s) from previous server session")
            
            # Mark all running jobs as failed since they were interrupted by server restart
            for job in running_jobs:
                job.status = 'Failed'
                job.error_message = 'Scan job interrupted by server restart'
                job.is_enabled = False
                
            print(f"Marked {len(running_jobs)} orphaned scan job(s) as failed")
        else:
            print("No orphaned scan jobs found")
            
    except Exception as e:
        print(f"Error during orphaned scan job cleanup: {e}")


def _log_system_event(session):
    """Log system startup event."""
    try:
        from modules.models import SystemEvents
        from modules import app_version
        from datetime import datetime
        
        event = SystemEvents(
            event_message=f"SharewareZ v{app_version} initializing database",
            event_type='system',
            event_level='startup',
            audit_user='system',
            created_at=datetime.utcnow()
        )
        session.add(event)
    except Exception as e:
        print(f"Warning: Could not log system event: {e}")