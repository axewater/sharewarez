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
app_version = '2.9.0'


def create_app():
    global s    
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # SAFETY CHECK: Prevent production database access during tests
    import sys
    if 'pytest' in sys.modules or 'PYTEST_CURRENT_TEST' in os.environ:
        # We are running in pytest - ensure we're using test database
        test_db_url = os.getenv('TEST_DATABASE_URL')
        production_db_url = os.getenv('DATABASE_URL')
        
        # If DATABASE_URL was not properly overridden in conftest.py
        if production_db_url and test_db_url and production_db_url != test_db_url:
            if 'sharewarez' in production_db_url and 'test' not in production_db_url:
                print(f"🚨 CRITICAL: Tests attempting to use production database: {production_db_url}")
                print(f"🛡️  BLOCKING: Forcing test database: {test_db_url}")
                app.config['SQLALCHEMY_DATABASE_URI'] = test_db_url
        
        print(f"🧪 PYTEST MODE: Using database: {app.config.get('SQLALCHEMY_DATABASE_URI', 'NOT SET')}")
    
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

    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle file upload size limit exceeded errors."""
        from flask import flash, redirect, request
        flash('The file you tried to upload is too large. Maximum file size is 10MB.', 'error')
        return redirect(request.url)

    @app.context_processor
    def inject_current_theme():
        """Injects the current user's theme into all templates."""
        if current_user.is_authenticated and hasattr(current_user, 'preferences') and current_user.preferences:
            current_theme = current_user.preferences.theme or 'default'
        else:
            current_theme = 'default'
        return dict(current_theme=current_theme)

    @app.before_request
    def check_setup_status():
        """Check if setup is required and redirect accordingly."""
        from flask import request, redirect, url_for
        from modules.utils_setup import should_redirect_to_setup, get_setup_redirect_url
        
        # Skip setup checks for certain endpoints
        exempt_endpoints = {
            'setup.setup', 'setup.setup_submit', 'setup.setup_smtp', 'setup.setup_igdb',
            'static', 'favicon', 'site.favicon'
        }
        
        # Skip setup checks for API endpoints (they should handle their own authentication)
        if request.endpoint and (
            request.endpoint in exempt_endpoints or
            request.endpoint.startswith('apis.') or
            request.path.startswith('/api/')
        ):
            return
        
        # Check if we need to redirect to setup
        if should_redirect_to_setup():
            setup_url = get_setup_redirect_url()
            if request.endpoint and request.path != setup_url:
                return redirect(setup_url)

    # Import models and routes
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

    # Register all blueprints
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

    with app.app_context():
        # Database initialization is handled by the InitializationManager before workers start
        # Worker processes skip initialization entirely since it's already done
        if ('pytest' not in sys.modules and 'PYTEST_CURRENT_TEST' not in os.environ and
            os.getenv('SHAREWAREZ_INITIALIZATION_COMPLETE') != 'true'):
            # This should only happen in development or if initialization wasn't run
            print("⚠️  Initialization not completed - this may cause issues")

    return app
