#/modules/__init__.py
import sys, os, re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask_mail import Mail, Message as MailMessage
from flask import Flask, Markup
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
from flask_migrate import Migrate
from modules.routes_site import site_bp
from modules.filters import setup_filters
# import logging
# from logging.handlers import RotatingFileHandler


db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
from flask_apscheduler import APScheduler

def create_app():
    global s
    app = Flask(__name__)
    app.config.from_object(Config)
    csrf = CSRFProtect(app)
    app.config['WTF_CSRF_HEADERS'] = ['X-CSRFToken', 'X-CSRF-Token']
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/avatars_users')
    db.init_app(app)
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
    app.register_blueprint(site_bp)
    setup_filters(app)
    return app



def insert_default_release_groups():
    from modules.models import ReleaseGroup
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
    {'rlsgroup': 'AlcoholClone', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'DARKZER0', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'EMPRESS+Mr_Goldberg', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'ENGLISH-TL', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'ENLIGHT', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'FANiSO', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'FitGirl.Repack', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'FitGirl', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'I_KnoW', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'PROPER-CLONECD', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'Razor1911', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'TENOKE', 'rlsgroupcs': 'no'},
    {'rlsgroup': 'ZER0', 'rlsgroupcs': 'no'},
       
    ]

    existing_groups = ReleaseGroup.query.with_entities(ReleaseGroup.rlsgroup).all()
    existing_group_names = {group.rlsgroup for group in existing_groups}

    for group in default_release_groups:
        if group['rlsgroup'] not in existing_group_names:
            new_group = ReleaseGroup(rlsgroup=group['rlsgroup'], rlsgroupcs=group['rlsgroupcs'])
            db.session.add(new_group)
    db.session.commit()


@login_manager.user_loader
def load_user(user_id):
    from modules.models import User
    return User.query.get(int(user_id))



