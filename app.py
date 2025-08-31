# /app.py
from modules import create_app, db
import argparse
import os
from modules.updateschema import DatabaseManager
from modules.models import User
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

# Create the Flask app
app = create_app()

# Handle setup if running directly
if __name__ == "__main__":
    args = handle_setup_args()
    setup_database(app, args.force_setup)
    
    # Run with uvicorn for production or flask dev server for development
    if os.getenv('PRODUCTION', 'false').lower() == 'true':
        import uvicorn
        from asgiref.wsgi import WsgiToAsgi
        asgi_app = WsgiToAsgi(app)
        uvicorn.run(asgi_app, host="0.0.0.0", port=5006, workers=1)
    else:
        app.run(host="0.0.0.0", debug=False, use_reloader=False, port=5006)
