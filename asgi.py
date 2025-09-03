"""
ASGI config for SharewareZ production deployment.
This file wraps the Flask app to be compatible with ASGI servers like uvicorn.
"""

import argparse
import sys
from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from modules import create_app, db
from modules.updateschema import DatabaseManager
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

# Create the Flask app
app = create_app()

# Handle database setup - check if force-setup was passed to original script
force_setup = '--force-setup' in sys.argv or '-fs' in sys.argv
setup_database(app, force_setup)

# Wrap with ASGI adapter
asgi_app = WsgiToAsgi(app)