"""
ASGI config for SharewareZ production deployment.
This file wraps the Flask app to be compatible with ASGI servers like uvicorn.
"""

import sys
from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from modules import create_app, db
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
            
            # Reset setup state in database
            from modules.utils_setup import reset_setup_state
            reset_setup_state()
            print("Setup state reset - setup wizard will be forced on next startup")

# Proper ASGI application with lifespan protocol support
class LazyASGIApp:
    def __init__(self):
        self._app = None
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            # Handle ASGI lifespan protocol
            await self._handle_lifespan(receive, send)
        else:
            # Handle HTTP requests
            if self._app is None:
                # Create Flask app only on first HTTP request, not during module import
                app = create_app()
                
                # Handle database setup - check if force-setup was passed to original script
                force_setup = '--force-setup' in sys.argv or '-fs' in sys.argv
                setup_database(app, force_setup)
                
                # Wrap with ASGI adapter
                self._app = WsgiToAsgi(app)
            
            await self._app(scope, receive, send)
    
    async def _handle_lifespan(self, receive, send):
        """Handle ASGI lifespan events (startup/shutdown)"""
        message = await receive()
        
        if message["type"] == "lifespan.startup":
            # Application is starting up
            try:
                # Could add startup initialization here if needed
                await send({"type": "lifespan.startup.complete"})
            except Exception:
                await send({"type": "lifespan.startup.failed", "message": "Startup failed"})
        
        elif message["type"] == "lifespan.shutdown":
            # Application is shutting down
            try:
                # Could add cleanup code here if needed
                await send({"type": "lifespan.shutdown.complete"})
            except Exception:
                await send({"type": "lifespan.shutdown.failed", "message": "Shutdown failed"})

# Create lazy ASGI app (won't call create_app() until first HTTP request)
asgi_app = LazyASGIApp()