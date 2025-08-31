#/modules/__init__.py
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask_mail import Mail
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from config import Config
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from flask_caching import Cache
from modules.utils_db import check_postgres_port_open

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
app_start_time = datetime.now()
app_version = '2.6.0'

def create_app():
    global s    
    app = Flask(__name__)
    app.config.from_object(Config)
    csrf = CSRFProtect(app)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/library')

    # --- BEGIN: Print masked PostgreSQL connection string ---
    raw_db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    parsed_uri = urlparse(raw_db_uri)
    if parsed_uri.password:
        # Create a new netloc with the masked password
        netloc_parts = parsed_uri.netloc.split('@')
        auth_part = netloc_parts[0].replace(parsed_uri.password, '********')
        masked_netloc = f"{auth_part}@{netloc_parts[1]}" if len(netloc_parts) > 1 else auth_part
        masked_uri = urlunparse(parsed_uri._replace(netloc=masked_netloc))
        print(f"Attempting to connect to PostgreSQL with URI: {masked_uri}")
    else:
        print(f"Attempting to connect to PostgreSQL with URI: {raw_db_uri}")
    # --- END: Print masked PostgreSQL connection string ---

    parsed_url = urlparse(app.config['SQLALCHEMY_DATABASE_URI'])
    check_postgres_port_open(parsed_url.hostname, 5432, 60, 2)
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    login_manager.login_view = 'login.login'
    cache.init_app(app)

    @app.context_processor
    def inject_current_theme():
        """Injects the current user's theme into all templates."""
        if current_user.is_authenticated and hasattr(current_user, 'preferences') and current_user.preferences:
            current_theme = current_user.preferences.theme or 'default'
        else:
            current_theme = 'default'
        return dict(current_theme=current_theme)

    with app.app_context():
        # Initialize library folders
        from modules.utils_logging import log_system_event
        from . import routes, models
        from modules.routes_site import site_bp
        from modules.routes_library import library_bp
        from modules.routes_setup import setup_bp
        from modules.routes_settings import settings_bp
        from modules.routes_login import login_bp
        from modules.routes_discover import discover_bp
        from modules.routes_downloads_ext import download_bp
        from modules.routes_games_ext import games_bp
        from modules.routes_smtp import smtp_bp
        from modules.routes_info import info_bp
        from modules.routes_admin_ext import admin2_bp
        from modules.routes_apis import apis_bp
        from modules.init_data import initialize_library_folders, insert_default_filters, initialize_default_settings, initialize_allowed_file_types, initialize_discovery_sections


        db.create_all()
        
        # Run database schema updates before initialization
        try:
            from modules.updateschema import DatabaseManager
            db_manager = DatabaseManager()
            db_manager.add_column_if_not_exists()
        except Exception as e:
            print(f"Warning: Database schema update failed: {e}")
        
        log_system_event(f"SharewareZ v{app_version} initializing database", event_type='system', event_level='startup', audit_user='system')
        initialize_library_folders()
        initialize_discovery_sections()
        insert_default_filters()
        initialize_default_settings()
        initialize_allowed_file_types()
    app.register_blueprint(routes.bp)
    app.register_blueprint(site_bp)
    app.register_blueprint(admin2_bp)
    app.register_blueprint(library_bp)
    app.register_blueprint(setup_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(discover_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(games_bp)
    app.register_blueprint(smtp_bp)
    app.register_blueprint(info_bp)
    app.register_blueprint(apis_bp)

    return app
