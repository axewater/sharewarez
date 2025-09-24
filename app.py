# /app.py
from modules import create_app, db
import argparse
import os

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

            # Reset setup state in database
            from modules.utils_setup import reset_setup_state
            reset_setup_state()
            print("Setup state reset - setup wizard will be forced on next startup")

# Create the Flask app (initialization is handled by InitializationManager before workers start)
app = create_app()

# Handle setup if running directly
if __name__ == "__main__":
    args = handle_setup_args()
    
    # Handle --force-setup flag when running app.py directly
    setup_database(app, args.force_setup)
    
    print("Note: For normal operation, use './startweb.sh' instead")
    print("app.py is primarily for CLI operations like --force-setup")
