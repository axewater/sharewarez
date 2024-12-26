# /app.py
import time
from modules import create_app, db
import argparse
from modules.updateschema import DatabaseManager
import os
import zipfile
import shutil
from modules.models import User

# Add argument parser
parser = argparse.ArgumentParser(description='SharewareZ Application')
parser.add_argument('--force-setup', '-fs', action='store_true', 
                   help='Force the setup wizard to run')
args = parser.parse_args()

# Create the Flask app
app = create_app()

# If force-setup is enabled, drop and recreate all tables
if args.force_setup:
    with app.app_context():
        print("Force setup enabled - dropping all tables...")
        db.drop_all()
        print("Recreating all tables...")
        db.create_all()
        print("Database reset complete.")

def initialize_library_folders():
    """Initialize the required folders and theme files for the application."""
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

# Initialize library folders before creating the app
initialize_library_folders()

# Check if force-setup is enabled
if args.force_setup:
    with app.app_context():
        # Get all users and delete them individually to handle cascade deletion
        users = User.query.all()
        for user in users:
            db.session.delete(user)
        db.session.commit()
        print("Setup wizard will be forced on next startup")

# Initialize and run the database schema update
db_manager = DatabaseManager()
db_manager.add_column_if_not_exists()

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False, use_reloader=False, port=5001)
