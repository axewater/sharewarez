from flask import Flask
from flask_wtf.csrf import CSRFProtect
from .database import db
from .extensions import mail, login_manager, cache
from .initialization import insert_default_release_groups
from config import Config
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize CSRF protection
    csrf = CSRFProtect(app)
    app.config['WTF_CSRF_HEADERS'] = ['X-CSRFToken', 'X-CSRF-Token']
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/library')

    # Initialize database
    db.init_app(app)  # Changed from init_db(app) to db.init_app(app)
    
    # Initialize other extensions
    login_manager.init_app(app)
    mail.init_app(app)
    cache.init_app(app)

    with app.app_context():
        from . import routes, models
        from .routes_site import site_bp
        db.create_all()
        insert_default_release_groups()
        
    # Register blueprints
    app.register_blueprint(routes.bp)
    app.register_blueprint(site_bp)
    
    return app
