"""
ASGI config for SharewareZ production deployment.
This file wraps the Flask app to be compatible with ASGI servers like uvicorn.
"""

import argparse
import sys
import os
from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from modules import create_app, db
from modules.updateschema import DatabaseManager
from modules.init_migrations import run_database_migrations, should_run_migrations, mark_migrations_complete
from modules.models import User
from sqlalchemy import select

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

# Run migrations and initialization once if not already done (only when starting directly, not as worker)
from modules.init_migrations import (
    should_run_initialization, run_database_initialization, 
    mark_initialization_complete, cleanup_orphaned_scan_jobs
)

if should_run_migrations():
    # Check if we're the main uvicorn process (not a worker)
    # When uvicorn spawns workers, it doesn't run this file directly
    if run_database_migrations():
        mark_migrations_complete()

# Create the Flask app
app = create_app()

# Run initialization after app is created (only if not already done)
if should_run_initialization():
    with app.app_context():
        if run_database_initialization():
            mark_initialization_complete()
            # Clean up orphaned scan jobs
            cleanup_orphaned_scan_jobs()

# Handle database setup - check if force-setup was passed to original script
force_setup = '--force-setup' in sys.argv or '-fs' in sys.argv
setup_database(app, force_setup)

# Wrap with ASGI adapter
asgi_app = WsgiToAsgi(app)