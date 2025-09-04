"""
Database migration module for SharewareZ.
This module handles one-time database migrations and initialization that should only run once
before worker processes are spawned.
"""

import os
from sqlalchemy import create_engine
from modules.updateschema import DatabaseManager
from config import Config


def run_database_migrations():
    """
    Run database migrations and schema updates.
    This should only be called once before worker processes start.
    """
    print("Running database migrations...")
    
    try:
        # Run schema updates using DatabaseManager
        db_manager = DatabaseManager()
        db_manager.add_column_if_not_exists()
        print("Database migrations completed successfully.")
        return True
    except Exception as e:
        print(f"Error during database migration: {e}")
        return False


def run_database_initialization():
    """
    Run one-time database initialization (default data, settings, etc.)
    This should only be called once before worker processes start.
    """
    print("Running database initialization...")
    
    try:
        # Import these here to avoid circular imports
        from modules.init_data import (
            initialize_library_folders, 
            insert_default_filters, 
            initialize_default_settings, 
            initialize_allowed_file_types, 
            initialize_discovery_sections
        )
        from modules.utils_logging import log_system_event
        from modules import app_version
        
        print("🔧 Initializing database with default data")
        log_system_event(f"SharewareZ v{app_version} initializing database", 
                         event_type='system', event_level='startup', audit_user='system')
        
        initialize_library_folders()
        initialize_discovery_sections()
        insert_default_filters()
        initialize_default_settings()
        initialize_allowed_file_types()
        
        print("Database initialization completed successfully.")
        return True
    except Exception as e:
        print(f"Error during database initialization: {e}")
        return False


def cleanup_orphaned_scan_jobs():
    """Clean up scan jobs that were left in 'Running' state after server restart."""
    try:
        from modules.models import ScanJob
        from modules import db
        from sqlalchemy import select
        from datetime import datetime, timezone
        
        # Find all jobs that are still marked as 'Running'
        running_jobs = db.session.execute(select(ScanJob).filter_by(status='Running')).scalars().all()
        
        if running_jobs:
            print(f"Found {len(running_jobs)} orphaned scan job(s) from previous server session")
            
            # Mark all running jobs as failed since they were interrupted by server restart
            for job in running_jobs:
                job.status = 'Failed'
                job.error_message = 'Scan job interrupted by server restart'
                job.is_enabled = False
                
            db.session.commit()
            print(f"Marked {len(running_jobs)} orphaned scan job(s) as failed")
        else:
            print("No orphaned scan jobs found")
            
        return True
    except Exception as e:
        print(f"Error during orphaned scan job cleanup: {e}")
        return False


def should_run_migrations():
    """
    Check if migrations should be run based on environment variables.
    Returns True if migrations should run, False if they should be skipped.
    """
    # Check if we're in a worker process (migrations already done)
    if os.getenv('SHAREWAREZ_MIGRATIONS_COMPLETE') == 'true':
        return False
    
    # Check if we're in pytest (tests handle their own migrations)
    import sys
    if 'pytest' in sys.modules or 'PYTEST_CURRENT_TEST' in os.environ:
        return False
    
    return True


def should_run_initialization():
    """
    Check if initialization should be run based on environment variables.
    Returns True if initialization should run, False if it should be skipped.
    """
    # Check if we're in a worker process (initialization already done)
    if os.getenv('SHAREWAREZ_INITIALIZATION_COMPLETE') == 'true':
        return False
    
    # Check if we're in pytest (tests handle their own data)
    import sys
    if 'pytest' in sys.modules or 'PYTEST_CURRENT_TEST' in os.environ:
        return False
    
    return True


def mark_migrations_complete():
    """
    Set environment variable to indicate migrations are complete.
    This signals to worker processes that they should skip migrations.
    """
    os.environ['SHAREWAREZ_MIGRATIONS_COMPLETE'] = 'true'


def mark_initialization_complete():
    """
    Set environment variable to indicate initialization is complete.
    This signals to worker processes that they should skip initialization.
    """
    os.environ['SHAREWAREZ_INITIALIZATION_COMPLETE'] = 'true'