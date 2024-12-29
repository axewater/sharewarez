# /app.py
from modules import create_app, db
import argparse
from modules.updateschema import DatabaseManager
from modules.models import User
from modules.init_data import initialize_library_folders

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
