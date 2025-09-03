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
        mark_initialization_complete, cleanup_orphaned_scan_jobs
    )
    
    if should_run_migrations():
        # Run migrations before creating app to ensure they only run once
        if run_database_migrations():
            mark_migrations_complete()
    
    # Let create_app() handle initialization, then mark it complete so subsequent calls skip it
    if should_run_initialization():
        # Create app for initialization (this will run initialization in create_app())
        temp_app = create_app()
        with temp_app.app_context():
            # Clean up orphaned scan jobs (the only thing not handled by create_app())
            cleanup_orphaned_scan_jobs()
            # Mark initialization complete so subsequent create_app() calls skip it
            mark_initialization_complete()

# Create the Flask app (will skip initialization since flag is now set)
app = create_app()

# Handle setup if running directly
if __name__ == "__main__":
    args = handle_setup_args()
    
    # For development mode, run setup here since asgi.py won't be used
    # For production mode, setup is handled in asgi.py
    if os.getenv('PRODUCTION', 'false').lower() != 'true':
        setup_database(app, args.force_setup)
    
    # Run with uvicorn for production or flask dev server for development
    if os.getenv('PRODUCTION', 'false').lower() == 'true':
        import uvicorn
        # Pass force_setup flag through sys.argv for asgi.py to pick up
        if args.force_setup:
            import sys
            if '--force-setup' not in sys.argv:
                sys.argv.append('--force-setup')
        uvicorn.run("asgi:asgi_app", host="0.0.0.0", port=5006, workers=4)
    else:
        app.run(host="0.0.0.0", debug=False, use_reloader=False, port=5006, threaded=True)
