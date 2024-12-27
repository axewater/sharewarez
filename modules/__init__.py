#/modules/__init__.py
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask_mail import Mail
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
from modules.routes_site import site_bp
from urllib.parse import urlparse
from flask_caching import Cache
from modules.utils_db import check_postgres_port_open


db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
cache = Cache(config={'CACHE_TYPE': 'simple'})

def create_app():
    global s    
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
    login_manager.login_view = 'main.login'
    cache.init_app(app)

    with app.app_context():
        from . import routes, models
        from modules.init_data import insert_default_filters
        db.create_all()
        insert_default_filters()
    app.register_blueprint(routes.bp)
    app.register_blueprint(site_bp)

    return app


@login_manager.user_loader
def load_user(user_id):
    from modules.models import User
    return User.query.get(int(user_id))
