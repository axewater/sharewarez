# modules/models.py
import json, uuid
from modules import db
from sqlalchemy import Table
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, TEXT
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from uuid import uuid4

class ReleaseGroup(db.Model):
    __tablename__ = 'filters'

    id = db.Column(db.Integer, primary_key=True)
    rlsgroup = db.Column(db.String, nullable=True)
    rlsgroupcs = db.Column(db.String, nullable=True)

    def __repr__(self):
        return f"<ReleaseGroup id={self.id}, rlsgroup={self.rlsgroup}, rlsgroupcs={self.rlsgroupcs}>"

class JSONEncodedDict(TypeDecorator):
    """Enables JSON storage by encoding and decoding on the fly."""
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(64), nullable=False)
    state = db.Column(db.Boolean, default=True)
    about = db.Column(db.String(64), unique=True, nullable=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    lastlogin = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String(36), unique=True, nullable=False, default=str(uuid4()))
    avatarpath = db.Column(db.String(256), default='avatars_users/default.jpg')
    is_email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(256), nullable=True)
    password_reset_token = db.Column(db.String(256), nullable=True)
    token_creation_time = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<User id={self.id}, name={self.name}, email={self.email}>"


class Whitelist(db.Model):
    __tablename__ = 'whitelist'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)


class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    banned_name = db.Column(db.String, unique=True, nullable=False)
    
class Game(db.Model):
    __tablename__ = 'games'

    id = db.Column(db.Integer, primary_key=True)
    igdb_id = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String, nullable=False)
    summary = db.Column(db.Text, nullable=True)
    storyline = db.Column(db.Text, nullable=True)
    url = db.Column(db.String, nullable=True)
    game_engine = db.Column(db.String, nullable=True)
    release_date = db.Column(db.DateTime, nullable=True)
    video_urls = db.Column(JSONEncodedDict)
    screenshots = db.Column(JSONEncodedDict)
    covers = db.Column(JSONEncodedDict)

    def __repr__(self):
        return f"<Game id={self.id}, name={self.name}>"
