import sys
import os
from flask_mail import Mail, Message as MailMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, Markup
from flask_wtf.csrf import CSRFProtect
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
from flask_apscheduler import APScheduler

def create_app():
    global s
    app = Flask(__name__)
    app.config.from_object(Config)
    csrf = CSRFProtect(app)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/avatars_users')
    
    # app.jinja_env.filters['nl2br'] = nl2br
    # if not os.path.exists('logs'):
    #    os.mkdir('logs')
    #file_handler = RotatingFileHandler('logs/sharewarez2.log', maxBytes=10240, backupCount=10)
    #file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    #file_handler.setLevel(logging.INFO)
    #app.logger.addHandler(file_handler)

    #app.logger.setLevel(logging.INFO)
    #app.logger.info('Sharewarez startup')
    db.init_app(app)
    # migrate = Migrate(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    login_manager.login_view = 'main.index'

    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()


    with app.app_context():
        from . import routes, models
        db.create_all()
        insert_default_release_groups()



    app.register_blueprint(routes.bp)
    return app


@login_manager.user_loader
def load_user(user_id):
    from modules.models import User
    return User.query.get(int(user_id))

def insert_default_release_groups():
    from .models import ReleaseGroup
    default_release_groups = [
    {'rlsgroup': 'RAZOR', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'FLT', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'SKIDROW', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'CODEX', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'PLAZA', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'RELOADED', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'HOODLUM', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'CPY', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'FAIRLIGHT', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'HI2U', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'TiNYiSO', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'DARKSiDERS', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'Teke', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'Kw', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'PROPHET', 'rlsgroupcs': 'yes'},
    {'rlsgroup': 'GOG', 'rlsgroupcs': 'no'}, 
    {'rlsgroup': 'RUNE', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'Empress', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'Deviance', 'rlsgroupcs': 'no'},
        # Add more entries as needed
    ]

    existing_groups = ReleaseGroup.query.with_entities(ReleaseGroup.rlsgroup).all()
    existing_group_names = {group.rlsgroup for group in existing_groups}  # Set comprehension for faster lookup

    for group in default_release_groups:
        if group['rlsgroup'] not in existing_group_names:
            new_group = ReleaseGroup(rlsgroup=group['rlsgroup'], rlsgroupcs=group['rlsgroupcs'])
            db.session.add(new_group)
    db.session.commit()

# Make sure this is called after db.create_all() within app.app_context()
