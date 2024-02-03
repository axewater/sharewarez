import sys
import os
from flask_mail import Mail, Message as MailMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, Markup
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
import re
from flask_migrate import Migrate
import logging
from logging.handlers import RotatingFileHandler


db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()

def create_app():
    global s
    app = Flask(__name__)
    app.config.from_object(Config)
    
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/avatars_users')
    
    app.jinja_env.filters['nl2br'] = nl2br
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/sharewarez2.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    app.logger.setLevel(logging.INFO)
    app.logger.info('Sharewarez startup')
    db.init_app(app)
    # migrate = Migrate(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    login_manager.login_view = 'main.index'




    with app.app_context():
        from . import routes, models
        db.create_all()

    app.register_blueprint(routes.bp)
    return app

def nl2br(value):
    if not isinstance(value, str):
        return value

    try:
        result = value.replace('\n', '<br>\n')
        result = Markup(result)
        return result
    except Exception as e:
        error_message = f'Error in nl2br filter: {str(e)}'
        print(error_message)
        return Markup(f'Error: Failed to process the input. Please try again later. ({str(e)})')

@login_manager.user_loader
def load_user(user_id):
    from modules.models import User
    return User.query.get(int(user_id))