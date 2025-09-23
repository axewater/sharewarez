"""
Standalone database initialization for SharewareZ startup.
This module handles all database operations using pure SQLAlchemy,
completely separate from Flask app creation.
"""

import os
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker
from config import Config

# Environment variables are loaded in config.py before the Config class is evaluated


def run_complete_startup_initialization():
    """
    Run all startup initialization tasks using pure SQLAlchemy.
    No Flask app creation involved.
    """
    print("Running database migrations and initialization...")
    
    try:
        # Step 1: Create basic table structure with pure SQLAlchemy
        print("🔧 Creating database tables")
        _create_tables_only()
        print("✅ Database tables created successfully")

        # Step 2: Run database migrations (including column renames)
        print("🔄 Running database migrations...")
        try:
            from modules.updateschema import DatabaseManager
            db_manager = DatabaseManager()
            db_manager.add_column_if_not_exists()
            print("✅ Database migrations completed successfully.")
        except Exception as migration_error:
            print(f"⚠️  Database migration warning: {migration_error}")
            print("Continuing with existing schema...")

        # Step 3: Initialize default data (after migrations are complete)
        print("📊 Initializing default data")
        _initialize_default_data()
        print("✅ Default data initialization completed successfully")

        print("✅ Initialization completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error during startup initialization: {e}")
        import traceback
        traceback.print_exc()
        return False


def _create_tables_only():
    """Create database tables without initializing data."""
    # Create SQLAlchemy engine
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)

    try:
        # Import models to register them
        from modules import models

        # Create all tables (this is idempotent - safe to run multiple times)
        models.db.metadata.create_all(engine)

    finally:
        engine.dispose()


def _initialize_default_data():
    """Initialize default data after migrations are complete."""
    # Create SQLAlchemy engine and session
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Initialize data (after migrations have been applied)
        _initialize_library_folders(session)
        _initialize_discovery_sections(session)
        _initialize_scanning_filters(session)
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


def _initialize_with_sqlalchemy():
    """Legacy function - kept for backward compatibility but not used in new flow."""
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
        _initialize_scanning_filters(session)
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

    # Import config to check DEV_MODE early
    from config import Config
    dev_mode = Config.DEV_MODE

    # Add debug logging for DEV_MODE and theme paths
    print(f"📁 Initializing library folders and theme system")
    print(f"🔧 DEV_MODE is {'ENABLED' if dev_mode else 'DISABLED'} (value: {dev_mode})")

    # This mirrors the original init_data.initialize_library_folders() function
    library_path = os.path.join('modules', 'static', 'library')
    themes_path = os.path.join(library_path, 'themes')
    images_path = os.path.join(library_path, 'images')
    zips_path = os.path.join(library_path, 'zips')

    # Check if default theme exists or if we're in dev mode
    default_theme_target = os.path.join(themes_path, 'default')
    theme_json_path = os.path.join(default_theme_target, 'theme.json')
    theme_json_exists = os.path.exists(theme_json_path)

    print(f"📂 Theme target directory: {default_theme_target}")
    print(f"📄 Theme JSON file: {theme_json_path}")
    print(f"🔍 Theme JSON exists: {theme_json_exists}")

    should_copy_theme = not theme_json_exists or dev_mode

    if dev_mode:
        print("🔄 DEV_MODE is enabled - theme files will be refreshed regardless of existence")
    elif not theme_json_exists:
        print("➕ Theme doesn't exist - will copy from source")
    else:
        print("✅ Theme exists and DEV_MODE is disabled - will skip copy")

    print(f"🎯 Decision: {'WILL COPY' if should_copy_theme else 'WILL SKIP'} theme files")

    if should_copy_theme:
        # Copy default theme from source directory
        default_theme_source = os.path.join('modules', 'setup', 'default_theme')
        print(f"📁 Theme source directory: {default_theme_source}")
        print(f"🔍 Source directory exists: {os.path.exists(default_theme_source)}")

        if os.path.exists(default_theme_source):
            try:
                import shutil
                # Create themes directory if it doesn't exist
                os.makedirs(themes_path, exist_ok=True)
                print(f"📁 Created themes directory: {themes_path}")

                # If theme directory exists and we're in dev mode, remove it first
                if dev_mode and os.path.exists(default_theme_target):
                    print("🗑️  DEV_MODE: Removing existing theme directory for fresh copy")
                    shutil.rmtree(default_theme_target)
                    print("🗑️  DEV_MODE: Theme directory removed successfully")

                # Copy the entire default theme directory
                print(f"📋 Copying theme files from {default_theme_source} to {default_theme_target}")
                shutil.copytree(default_theme_source, default_theme_target, dirs_exist_ok=True)

                if dev_mode:
                    print("🔄 DEV_MODE: Default theme files refreshed successfully!")
                else:
                    print("✅ Default theme copied successfully!")

                # Verify the copy worked
                if os.path.exists(theme_json_path):
                    print("✅ Theme installation verified - theme.json found")
                else:
                    print("⚠️  Warning: theme.json not found after copy")

            except Exception as e:
                print(f"❌ Error copying default theme: {str(e)}")
                import traceback
                traceback.print_exc()
        else:
            print("⚠️  Warning: default theme source not found in modules/setup/default_theme")
    else:
        if dev_mode:
            print("🚫 CRITICAL ERROR: DEV_MODE is enabled but theme copy was skipped!")
        print("ℹ️  Theme copy skipped - using existing theme files")
        
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
            DiscoverySection(name='Latest Additions', identifier='latest', is_visible=True, display_order=1),
            DiscoverySection(name='Random Selection', identifier='random', is_visible=True, display_order=2),
            DiscoverySection(name='Most Downloaded', identifier='popular', is_visible=True, display_order=3)
        ]
        for section in default_sections:
            session.add(section)
        print("Default discovery sections initialized")
    else:
        print("Discovery sections already exist")


def _initialize_scanning_filters(session):
    """Initialize default scanning filters."""
    from modules.models import ReleaseGroup
    
    default_name_filters = [
        {'filter_pattern': 'Open Source', 'case_sensitive': 'no'},
        {'filter_pattern': 'Public Domain', 'case_sensitive': 'no'},
        {'filter_pattern': 'GOG', 'case_sensitive': 'no'},
    ]

    existing_groups = session.execute(select(ReleaseGroup.filter_pattern)).scalars().all()
    existing_group_names = set(existing_groups)

    for group in default_name_filters:
        if group['filter_pattern'] not in existing_group_names:
            new_group = ReleaseGroup(filter_pattern=group['filter_pattern'], case_sensitive=group['case_sensitive'])
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
            allowed_type = AllowedFileType(value=file_type)
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
        
        event = SystemEvents(
            event_text=f"SharewareZ v{app_version} initializing database",
            event_type='system',
            event_level='startup',
            audit_user=None
        )
        session.add(event)
    except Exception as e:
        print(f"Warning: Could not log system event: {e}")