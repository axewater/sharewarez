# /app.py
from modules import create_app, db
import argparse
import os
from modules.updateschema import DatabaseManager
from modules.models import User
from modules.init_migrations import run_database_migrations, should_run_migrations, mark_migrations_complete
from sqlalchemy import select
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def handle_setup_args():
    """Handle command line arguments for setup"""
    parser = argparse.ArgumentParser(description='SharewareZ Application')
    parser.add_argument('--force-setup', '-fs', action='store_true', 
                       help='Force the setup wizard to run')
    args = parser.parse_args()
    return args

def setup_database(app, force_setup=False):
    """Setup database with optional force reset"""
    if force_setup:
        with app.app_context():
            print("Force setup enabled - dropping all tables...")
            db.drop_all()
            print("Recreating all tables...")
            db.create_all()
            print("Database reset complete.")
            
            # Get all users and delete them individually to handle cascade deletion
            users = db.session.execute(select(User)).scalars().all()
            for user in users:
                db.session.delete(user)
            db.session.commit()
            print("Setup wizard will be forced on next startup")

# Run migrations and initialization once before creating app (only in main process)
if __name__ == "__main__":
    from modules.init_migrations import (
        should_run_migrations, should_run_initialization, 
        mark_initialization_complete, cleanup_orphaned_scan_jobs,
        run_database_initialization
    )
    
    if should_run_migrations():
        # Run migrations before creating app to ensure they only run once
        if run_database_migrations():
            mark_migrations_complete()
    
    # Check if initialization is needed before marking it complete
    need_initialization = should_run_initialization()
    if need_initialization:
        # Mark initialization complete BEFORE create_app so it skips initialization
        mark_initialization_complete()

# Create the Flask app (will skip both migrations and initialization due to flags)
app = create_app()

# Run initialization manually if it was needed (only in main process)
if __name__ == "__main__":
    if need_initialization:
        with app.app_context():
            # Run initialization manually since create_app() skipped it
            run_database_initialization()
            cleanup_orphaned_scan_jobs()

# Handle setup if running directly
if __name__ == "__main__":
    args = handle_setup_args()
    
    # Handle --force-setup flag when running app.py directly
    setup_database(app, args.force_setup)
    
    print("Note: For normal operation, use './startweb.sh' instead")
    print("app.py is primarily for CLI operations like --force-setup")
