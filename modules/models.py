# modules/models.py
from modules import db
from sqlalchemy import Table
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, TEXT
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid, json
from uuid import uuid4

class JSONEncodedDict(TypeDecorator):
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value



class Game(db.Model):
    __tablename__ = 'games'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    igdb_id = db.Column(db.Integer, nullable=True, unique=True)
    name = db.Column(db.String, nullable=False)
    summary = db.Column(db.Text, nullable=True)
    storyline = db.Column(db.Text, nullable=True)
    url = db.Column(db.String, nullable=True)
    full_disk_path = db.Column(db.String, nullable=True)
    release_date = db.Column(db.DateTime, nullable=True)
    video_urls = db.Column(JSONEncodedDict)
    images = relationship("Image", backref="game", lazy='dynamic')
    download_requests = db.relationship('DownloadRequest', back_populates='game', lazy='dynamic', cascade='delete')

    def __repr__(self):
        return f"<Game id={self.id}, name={self.name}>"
    
class Image(db.Model):
    __tablename__ = 'images'

    id = db.Column(db.Integer, primary_key=True)
    game_uuid = db.Column(db.String(36), db.ForeignKey('games.uuid'), nullable=False)  # Adjusted to String type
    image_type = db.Column(db.String, nullable=False)  # 'screenshot' or 'cover' or 'thumbnail'
    url = db.Column(db.String, nullable=False)  # igdb url
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Image id={self.id}, game_uuid={self.game_uuid}, image_type={self.image_type}, url={self.url}>"

class ReleaseGroup(db.Model):
    __tablename__ = 'filters'

    id = db.Column(db.Integer, primary_key=True)
    rlsgroup = db.Column(db.String, nullable=True)
    rlsgroupcs = db.Column(db.String, nullable=True)

    def __repr__(self):
        return f"<ReleaseGroup id={self.id}, rlsgroup={self.rlsgroup}, rlsgroupcs={self.rlsgroupcs}>"


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

class DownloadRequest(db.Model):
    __tablename__ = 'download_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    game_uuid = db.Column(db.String(36), db.ForeignKey('games.uuid', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(50), default='pending')
    zip_file_path = db.Column(db.String, nullable=True)
    request_time = db.Column(db.DateTime, default=datetime.utcnow)
    completion_time = db.Column(db.DateTime, nullable=True)

    # Relationship (optional, depending on your SQLAlchemy version and requirements)
    game = db.relationship('Game', foreign_keys=[game_uuid], back_populates='download_requests')


class Whitelist(db.Model):
    __tablename__ = 'whitelist'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)

