#/modules/__init__.py
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask_mail import Mail
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
from datetime import datetime
from urllib.parse import urlparse
from flask_caching import Cache
from modules.utils_db import check_postgres_port_open

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
cache = Cache(config={'CACHE_TYPE': 'simple'})
app_start_time = datetime.now()
app_version = '2.1.1'

def create_app():
    global s    
    app = Flask(__name__)
    app.config.from_object(Config)
    csrf = CSRFProtect(app)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/library')
    parsed_url = urlparse(app.config['SQLALCHEMY_DATABASE_URI'])
    check_postgres_port_open(parsed_url.hostname, 5432, 60, 2)
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    login_manager.login_view = 'login.login'
    cache.init_app(app)

    with app.app_context():
        from . import routes, models
        from modules.utils_auth import load_user
        from modules.init_data import insert_default_filters, initialize_default_settings
        from modules.routes_site import site_bp
        from modules.routes_admin import admin_bp
        from modules.routes_library import library_bp
        from modules.routes_setup import setup_bp
        from modules.routes_settings import settings_bp
        from modules.routes_login import login_bp
        from modules.routes_discover import discover_bp
        from modules.routes_apis_filters import apis_filters_bp
        from modules.routes_apis_other import apis_other_bp
        from modules.routes_downloads import download_bp
        from modules.routes_games import games_bp
        db.create_all()
        insert_default_filters()
        initialize_default_settings()
    app.register_blueprint(routes.bp)
    app.register_blueprint(site_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(library_bp)
    app.register_blueprint(setup_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(discover_bp)
    app.register_blueprint(apis_filters_bp)
    app.register_blueprint(apis_other_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(games_bp)

    return app
