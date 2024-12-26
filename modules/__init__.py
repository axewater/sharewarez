# modules/__init__.py
import sys, os, socket, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, Markup
from flask_wtf.csrf import CSRFProtect
from urllib.parse import urlparse
from modules.extensions import db, mail, login_manager, cache
from modules.initialization import insert_default_release_groups
from config import Config

def check_postgres_port_open(host, port, retries=5, delay=2):
    """
    Checks if the PostgreSQL port is open by attempting to create a socket connection.
    If the connection attempt fails, it waits for 'delay' seconds and retries.
    
    :param host: The hostname or IP address of the PostgreSQL server.
    :param port: The port number of the PostgreSQL server.
    :param retries: Maximum number of retries.
    :param delay: Delay in seconds between retries.
    :return: True if the port is open, False otherwise.
    """
    for attempt in range(retries):
        try:
            with socket.create_connection((host, port), timeout=10):
                print(f"Connection to PostgreSQL on port {port} successful.")
                return True
        except (socket.timeout, ConnectionRefusedError):
            print(f"Connection to PostgreSQL on port {port} failed. Attempt {attempt + 1} of {retries}.")
            time.sleep(delay)
    return False

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    csrf = CSRFProtect(app)
    app.config['WTF_CSRF_HEADERS'] = ['X-CSRFToken', 'X-CSRF-Token']
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/library')

    parsed_url = urlparse(app.config['SQLALCHEMY_DATABASE_URI'])
    check_postgres_port_open(parsed_url.hostname, 5432, 60, 2)
    
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    cache.init_app(app)

    with app.app_context():
        from . import routes, models
        from .routes_site import site_bp  # Move the import here
        db.create_all()
        insert_default_release_groups()
        
    app.register_blueprint(routes.bp)
    app.register_blueprint(site_bp)
    return app
