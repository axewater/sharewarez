"""
Centralized Initialization Manager for SharewareZ.
This module consolidates all initialization logic into a single, coordinated system
that ensures proper startup order and eliminates duplication.
"""

import os
import shutil
from datetime import datetime, timezone
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv


class InitializationManager:
    """Central coordinator for all SharewareZ initialization tasks."""

    def __init__(self):
        self._environment_loaded = False
        self._initialization_complete = False

    def run_complete_initialization(self):
        """
        Master orchestrator for all initialization phases.
        Returns True on success, False on failure.
        """
        try:
            print("🚀 Starting SharewareZ initialization...")

            # Phase 1: Environment setup (load once)
            if not self._phase1_environment():
                return False

            # Phase 2: Database structure (tables and migrations)
            if not self._phase2_database_structure():
                return False

            # Phase 3: Default data initialization
            if not self._phase3_default_data():
                return False

            # Phase 4: Filesystem setup (folders and themes)
            if not self._phase4_filesystem():
                return False

            # Phase 5: Cleanup and finalization
            if not self._phase5_cleanup():
                return False

            self._initialization_complete = True
            print("✅ SharewareZ initialization completed successfully")
            return True

        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _phase1_environment(self):
        """Load environment variables exactly once."""
        if self._environment_loaded:
            print("🔧 Environment variables already loaded")
            return True

        try:
            # Use explicit path to ensure .env is found
            from pathlib import Path
            import os
            env_path = Path(__file__).parent.parent / '.env'

            load_dotenv(dotenv_path=env_path)
            self._environment_loaded = True

            # Debug: Verify critical environment variables are loaded
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                # Mask password for security
                masked_url = database_url.split('@')[0].split(':')[0:2]
                masked_url = ':'.join(masked_url) + ':***@' + database_url.split('@')[1] if '@' in database_url else database_url
                print(f"🔧 Environment variables loaded successfully")
                print(f"📊 DATABASE_URL found: {masked_url}")
            else:
                print("⚠️  DATABASE_URL not found in environment - using config fallback")

            return True
        except Exception as e:
            print(f"❌ Failed to load environment: {e}")
            return False

    def _phase2_database_structure(self):
        """Create database tables and run migrations."""
        print("🗄️  Phase 2: Database structure setup")

        try:
            # Import config after environment is loaded
            from config import Config

            # Create tables using pure SQLAlchemy
            engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)

            try:
                # Import models to register them with SQLAlchemy
                from modules import models

                # Create all tables (idempotent operation)
                models.db.metadata.create_all(engine)
                print("✅ Database tables created")

                # Run schema migrations
                from modules.updateschema import DatabaseManager
                db_manager = DatabaseManager()
                db_manager.add_column_if_not_exists()
                print("✅ Database migrations completed")

            finally:
                engine.dispose()

            return True

        except Exception as e:
            print(f"❌ Database structure setup failed: {e}")
            return False

    def _phase3_default_data(self):
        """Initialize all default data in the database."""
        print("📊 Phase 3: Default data initialization")

        try:
            # Import config to get database URI
            from config import Config

            # Create engine and session for data operations
            engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()

            try:
                # Initialize default data components
                self._init_default_settings(session)
                self._init_scanning_filters(session)
                self._init_allowed_file_types(session)
                self._init_discovery_sections(session)

                # Commit all changes
                session.commit()
                print("✅ Default data initialization completed")
                return True

            except Exception as e:
                session.rollback()
                print(f"❌ Default data initialization failed: {e}")
                return False
            finally:
                session.close()
                engine.dispose()

        except Exception as e:
            print(f"❌ Phase 3 setup failed: {e}")
            return False

    def _phase4_filesystem(self):
        """Setup filesystem folders and theme files."""
        print("📁 Phase 4: Filesystem setup")

        try:
            # Import config after environment is loaded
            from config import Config

            # Create required directories
            library_path = os.path.join('modules', 'static', 'library')
            themes_path = os.path.join(library_path, 'themes')
            images_path = os.path.join(library_path, 'images')
            zips_path = os.path.join(library_path, 'zips')

            # Get DEV_MODE with fallback for robustness
            try:
                dev_mode = Config.DEV_MODE
            except AttributeError:
                print("⚠️  Config.DEV_MODE not found, using environment fallback")
                dev_mode = os.getenv('DEV_MODE', 'false').lower() == 'true'

            # Handle theme installation
            self._setup_default_theme(themes_path, dev_mode)

            # Create other required directories
            for path, name in [(images_path, 'images'), (zips_path, 'zips')]:
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                    print(f"✅ Created {name} directory")

            print("✅ Filesystem setup completed")
            return True

        except Exception as e:
            print(f"❌ Filesystem setup failed: {e}")
            return False

    def _phase5_cleanup(self):
        """Cleanup operations and system event logging."""
        print("🧹 Phase 5: Cleanup and finalization")

        try:
            # Import config to get database URI
            from config import Config

            # Create engine and session for cleanup
            engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()

            try:
                # Clean up orphaned scan jobs
                self._cleanup_orphaned_scan_jobs(session)

                # Log system startup event
                self._log_system_event(session)

                session.commit()
                print("✅ Cleanup and finalization completed")
                return True

            except Exception as e:
                session.rollback()
                print(f"❌ Cleanup failed: {e}")
                return False
            finally:
                session.close()
                engine.dispose()

        except Exception as e:
            print(f"❌ Phase 5 failed: {e}")
            return False

    def _init_default_settings(self, session):
        """Initialize default global settings."""
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
            print("✅ Created default global settings")
        else:
            print("ℹ️  Global settings already exist")

    def _init_scanning_filters(self, session):
        """Initialize default scanning filters."""
        from modules.models import ReleaseGroup

        default_filters = [
            {'filter_pattern': 'Open Source', 'case_sensitive': 'no'},
            {'filter_pattern': 'Public Domain', 'case_sensitive': 'no'},
            {'filter_pattern': 'GOG', 'case_sensitive': 'no'},
        ]

        existing_groups = session.execute(select(ReleaseGroup.filter_pattern)).scalars().all()
        existing_group_names = set(existing_groups)

        added_count = 0
        for group in default_filters:
            if group['filter_pattern'] not in existing_group_names:
                new_group = ReleaseGroup(
                    filter_pattern=group['filter_pattern'],
                    case_sensitive=group['case_sensitive']
                )
                session.add(new_group)
                added_count += 1

        if added_count > 0:
            print(f"✅ Added {added_count} default scanning filters")
        else:
            print("ℹ️  Scanning filters already exist")

    def _init_allowed_file_types(self, session):
        """Initialize default allowed file types."""
        from modules.models import AllowedFileType

        default_types = [
            'zip', 'rar', '7z', 'iso', 'nfo', 'nes', 'sfc', 'smc', 'sms', '32x',
            'gen', 'gg', 'gba', 'gb', 'gbc', 'ndc', 'prg', 'dat', 'tap', 'z64',
            'd64', 'dsk', 'img', 'bin', 'st', 'stx', 'j64', 'jag', 'lnx', 'adf',
            'ngc', 'gz', 'm2v', 'ogg', 'fpt', 'fpl', 'vec', 'pce', 'a78', 'rom'
        ]

        existing_types = {ft.value for ft in session.execute(select(AllowedFileType)).scalars().all()}

        added_count = 0
        for file_type in default_types:
            if file_type not in existing_types:
                new_type = AllowedFileType(value=file_type)
                session.add(new_type)
                added_count += 1

        if added_count > 0:
            print(f"✅ Added {added_count} default file types")
        else:
            print("ℹ️  File types already exist")

    def _init_discovery_sections(self, session):
        """Initialize default discovery sections."""
        from modules.models import DiscoverySection

        default_sections = [
            {'name': 'Libraries', 'identifier': 'libraries', 'is_visible': True, 'display_order': 0},
            {'name': 'Latest Games', 'identifier': 'latest_games', 'is_visible': True, 'display_order': 1},
            {'name': 'Most Downloaded', 'identifier': 'most_downloaded', 'is_visible': True, 'display_order': 2},
            {'name': 'Highest Rated', 'identifier': 'highest_rated', 'is_visible': True, 'display_order': 3},
            {'name': 'Last Updated', 'identifier': 'last_updated', 'is_visible': True, 'display_order': 4},
            {'name': 'Most Favorited', 'identifier': 'most_favorited', 'is_visible': True, 'display_order': 5}
        ]

        existing_sections = {section.identifier for section in session.execute(select(DiscoverySection)).scalars().all()}

        added_count = 0
        for section in default_sections:
            if section['identifier'] not in existing_sections:
                new_section = DiscoverySection(
                    name=section['name'],
                    identifier=section['identifier'],
                    is_visible=section['is_visible'],
                    display_order=section['display_order']
                )
                session.add(new_section)
                added_count += 1

        if added_count > 0:
            print(f"✅ Added {added_count} discovery sections")
        else:
            print("ℹ️  Discovery sections already exist")

    def _setup_default_theme(self, themes_path, dev_mode):
        """Setup default theme files with DEV_MODE support."""
        default_theme_target = os.path.join(themes_path, 'default')
        theme_json_path = os.path.join(default_theme_target, 'theme.json')
        theme_exists = os.path.exists(theme_json_path)

        should_copy_theme = not theme_exists or dev_mode

        if should_copy_theme:
            default_theme_source = os.path.join('modules', 'setup', 'default_theme')

            if os.path.exists(default_theme_source):
                try:
                    # Create themes directory
                    os.makedirs(themes_path, exist_ok=True)

                    # Remove existing theme in dev mode
                    if dev_mode and os.path.exists(default_theme_target):
                        shutil.rmtree(default_theme_target)

                    # Copy theme files
                    shutil.copytree(default_theme_source, default_theme_target, dirs_exist_ok=True)

                    if dev_mode:
                        print("🔄 DEV_MODE: Theme files refreshed")
                    else:
                        print("✅ Default theme installed")

                except Exception as e:
                    print(f"❌ Theme setup failed: {e}")
            else:
                print("⚠️  Theme source not found")
        else:
            print("ℹ️  Theme already exists")

    def _cleanup_orphaned_scan_jobs(self, session):
        """Clean up scan jobs left in 'Running' state after server restart."""
        from modules.models import ScanJob

        running_jobs = session.execute(select(ScanJob).filter_by(status='Running')).scalars().all()

        if running_jobs:
            for job in running_jobs:
                job.status = 'Failed'
                job.error_message = 'Scan job interrupted by server restart'
                job.is_enabled = False

            print(f"🧹 Cleaned up {len(running_jobs)} orphaned scan jobs")
        else:
            print("ℹ️  No orphaned scan jobs found")

    def _log_system_event(self, session):
        """Log system startup event."""
        try:
            from modules.models import SystemEvents
            from modules import app_version

            event = SystemEvents(
                event_text=f"SharewareZ v{app_version} initialization completed",
                event_type='system',
                event_level='startup',
                audit_user=None
            )
            session.add(event)
            print("✅ System startup event logged")
        except Exception as e:
            print(f"⚠️  Could not log system event: {e}")


# Global instance for easy access
_init_manager = None

def get_initialization_manager():
    """Get the global initialization manager instance."""
    global _init_manager
    if _init_manager is None:
        _init_manager = InitializationManager()
    return _init_manager


def run_complete_initialization():
    """Convenience function for running complete initialization."""
    manager = get_initialization_manager()
    return manager.run_complete_initialization()


def is_initialization_complete():
    """Check if initialization has been completed."""
    # First check environment variable (set after successful init)
    if os.getenv('SHAREWAREZ_INITIALIZATION_COMPLETE') == 'true':
        return True

    # Check manager state if available
    global _init_manager
    if _init_manager is not None:
        return _init_manager._initialization_complete

    return False


def mark_initialization_complete():
    """Mark initialization as complete in environment."""
    os.environ['SHAREWAREZ_INITIALIZATION_COMPLETE'] = 'true'
    os.environ['SHAREWAREZ_MIGRATIONS_COMPLETE'] = 'true'