"""
ASGI config for SharewareZ production deployment.
This file wraps the Flask app to be compatible with ASGI servers like uvicorn.
"""

from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from modules import create_app

# Create the Flask app
app = create_app()

# Wrap with ASGI adapter
asgi_app = WsgiToAsgi(app)