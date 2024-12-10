# modules/models.py
from modules import db
from sqlalchemy import Table, Column, Integer, String, ForeignKey, Float, DateTime, Enum
from sqlalchemy.dialects.sqlite import TEXT as SQLite_TEXT
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, TEXT
from sqlalchemy.types import Enum as SQLEnum
from werkzeug.security import generate_password_hash, check_password_hash
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from datetime import datetime
import uuid, json
from uuid import uuid4
from datetime import datetime, timedelta
from enum import Enum as PyEnum


ph = PasswordHasher()

class JSONEncodedDict(TypeDecorator):
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            try:
                return json.dumps(value)
            except (TypeError, ValueError) as e:
                print(f"Error serializing JSON: {e}")
                # Optionally, return None or some default value
                return None
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            try:
                return json.loads(value)
            except (TypeError, ValueError) as e:
                print(f"Error deserializing JSON: {e}")
                # Return a default value to ensure the application can continue
                return {}
        return value



game_genre_association = db.Table('game_genre_association',
    db.Column('game_id', db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id'), primary_key=True)
)

game_game_mode_association = db.Table('game_game_mode_association',
    db.Column('game_id', db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('game_mode_id', db.Integer, db.ForeignKey('game_modes.id'), primary_key=True)
)

game_theme_association = db.Table(
    'game_theme_association',
    db.Column('game_id', db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('theme_id', db.Integer, db.ForeignKey('themes.id'), primary_key=True)
)


game_platform_association = db.Table(
    'game_platform_association',
    db.Column('game_id', db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('platform_id', db.Integer, db.ForeignKey('platforms.id'), primary_key=True)
)


game_multiplayer_mode_association = db.Table(
    'game_multiplayer_mode_association',
    db.Column('game_id', db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('multiplayer_mode_id', db.Integer, db.ForeignKey('multiplayer_modes.id'), primary_key=True)
)

game_player_perspective_association = db.Table(
    'game_player_perspective_association',
    db.Column('game_id', db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('player_perspective_id', db.Integer, db.ForeignKey('player_perspectives.id'), primary_key=True)
)

game_developer_association = db.Table(
    'game_developer_association',
    db.Column('game_id', db.Integer, db.ForeignKey('games.id'), primary_key=True),
    db.Column('developer_id', db.Integer, db.ForeignKey('developers.id'), primary_key=True)
)



class Category(PyEnum):
    MAIN_GAME = "Main Game"
    DLC_ADDON = "DLC/Add-on"
    EXPANSION = "Expansion"
    BUNDLE = "Bundle"
    STANDALONE_EXPANSION = "Standalone Expansion"
    MOD = "Mod"
    EPISODE = "Episode"
    SEASON = "Season"
    REMAKE = "Remake"
    REMASTER = "Remaster"
    EXPANDED_GAME = "Expanded Game"
    PORT = "Port"
    PACK = "Pack"
    UPDATE = "Update"
    
# this has to go away
class LibraryPlatform(PyEnum):
    OTHER = "Other"
    PCWIN = "PC Windows"
    PCDOS = "PC DOS"
    MAC = "Mac"
    NES = "Nintendo Entertainment System (NES)"
    SNES = "Super Nintendo Entertainment System (SNES)"
    NGC = "Nintendo GameCube"
    N64 = "Nintendo 64"
    GB = "Nintendo GameBoy"
    GBA = "Nintendo GameBoy Advance"
    NDS = "Nintendo DS"
    VB = "Nintendo Virtual Boy"
    XBOX = "Xbox"
    X360 = "Xbox 360"
    XONE = "Xbox One"
    XSX = "Xbox Series X"
    PSX = "Sony Playstation (PSX)"
    PS2 = "Sony PS2"
    PS3 = "Sony PS3"
    PS4 = "Sony PS4"
    PS5 = "Sony PS5"
    SEGA_MD = "Sega Mega Drive/Genesis (MD)"
    SEGA_MS = "Sega Master System (MS)"
    SEGA_CD = "Sega CD"
    LYNX = "Atari Lynx"
    SEGA_32X = "Sega 32X"
    JAGUAR = "Atari Jaguar"
    SEGA_GG = "Sega Game Gear (GG)"
    SEGA_SATURN = "Sega Saturn"
    ATARI_7800 = "Atari 7800"
    ATARI_2600 = "Atari 2600"
    PCE = "PC Engine"
    PCFX = "PC-FX"
    NGP = "Neo Geo Pocket"
    WS = "WonderSwan"
    COLECO = "ColecoVision"
    VICE_X64SC = "Commodore 64 (VIC-20)"
    VICE_X128 = "Commodore 128"
    VICE_XVIC = "Commodore VIC-20"
    VICE_XPLUS4 = "Commodore Plus/4"
    VICE_XPET = "Commodore PET"



class Library(db.Model):
    __tablename__ = 'libraries'
    
    uuid = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    name = db.Column(db.String(255), nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    platform = db.Column(db.Enum(LibraryPlatform), nullable=False)
    display_order = db.Column(db.Integer, default=0)
    games = db.relationship('Game', backref='library', lazy=True)
    unmatched_folders = relationship("UnmatchedFolder", backref='library', cascade="all, delete-orphan")



category_mapping = {
    0: Category.MAIN_GAME,
    1: Category.DLC_ADDON,
    2: Category.EXPANSION,
    3: Category.BUNDLE,
    4: Category.STANDALONE_EXPANSION,
    5: Category.MOD,
    6: Category.EPISODE,
    7: Category.SEASON,
    8: Category.REMAKE,
    9: Category.REMASTER,
    10: Category.EXPANDED_GAME,
    11: Category.PORT,
    12: Category.PACK,
    13: Category.UPDATE
}




class Status(PyEnum):
    RELEASED = "Released"
    ALPHA = "Alpha"
    BETA = "Beta"
    EARLY_ACCESS = "Early Access"
    OFFLINE = "Offline"
    CANCELLED = "Cancelled"
    
    
status_mapping = {
    1: Status.RELEASED,
    2: Status.ALPHA,
    3: Status.BETA,
    4: Status.EARLY_ACCESS,
    6: Status.OFFLINE,
    7: Status.CANCELLED
}    

class PlayerPerspective(PyEnum):
    FIRST_PERSON = "First Person"
    THIRD_PERSON = "Third Person"
    FIRST_THIRD = "First Person/Third Person"

player_perspective_mapping = {
    1: PlayerPerspective.FIRST_PERSON,
    2: PlayerPerspective.THIRD_PERSON,
    3: PlayerPerspective.FIRST_THIRD
}

user_favorites = db.Table('user_favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('game_uuid', db.String(36), db.ForeignKey('games.uuid'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

class Game(db.Model):
    __tablename__ = 'games'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), default=lambda: str(uuid4()), unique=True, nullable=False)
    igdb_id = db.Column(db.Integer, unique=True, nullable=True)
    favorited_by = db.relationship('User', secondary='user_favorites', back_populates='favorites')
    name = db.Column(db.String, nullable=False)
    summary = db.Column(db.Text, nullable=True)
    storyline = db.Column(db.Text, nullable=True)
    updates = db.relationship('GameUpdate', back_populates='game', cascade='all, delete-orphan')
    aggregated_rating = db.Column(db.Float)
    aggregated_rating_count = db.Column(db.Integer)
    cover = db.Column(db.String)
    first_release_date = db.Column(db.DateTime)
    rating = db.Column(db.Float)
    rating_count = db.Column(db.Integer)
    slug = db.Column(db.String, unique=True)
    status = db.Column(db.Enum(Status))
    category = db.Column(db.Enum(Category))
    total_rating = db.Column(db.Float, default=1.0)
    total_rating_count = db.Column(db.Integer, default=1)
    url_igdb = db.Column(db.String)
    url = db.Column(db.String)
    video_urls = db.Column(db.String, nullable=True)
    full_disk_path = db.Column(db.String, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    date_identified = db.Column(db.DateTime, nullable=True)
    steam_url = db.Column(db.String, nullable=True)
    times_downloaded = db.Column(db.Integer, default=0)
    nfo_content = db.Column(db.Text, nullable=True)
    images = db.relationship("Image", backref="game", lazy='dynamic')
    genres = db.relationship('Genre', secondary=game_genre_association, back_populates='games')
    game_modes = db.relationship("GameMode", secondary=game_game_mode_association, back_populates="games")
    themes = db.relationship("Theme", secondary=game_theme_association, back_populates="games")
    platforms = db.relationship("Platform", secondary=game_platform_association, back_populates="games")
    player_perspectives = db.relationship("PlayerPerspective", secondary=game_player_perspective_association, back_populates="games")
    developer_id = db.Column(db.Integer, db.ForeignKey('developers.id'), nullable=True)
    developer = db.relationship("Developer", back_populates="games")
    publisher = db.relationship("Publisher", back_populates="games")
    publisher_id = db.Column(db.Integer, db.ForeignKey('publishers.id'), nullable=True)
    download_requests = db.relationship('DownloadRequest', back_populates='game', lazy='dynamic', cascade='delete')
    multiplayer_modes = db.relationship("MultiplayerMode", secondary=game_multiplayer_mode_association, back_populates="games")    
    urls = db.relationship('GameURL', cascade='all, delete-orphan')
    file_type = db.Column(db.String, nullable=True) 
    library_name = db.Column(db.String(512), nullable=True)
    library_uuid = db.Column(db.String(36), db.ForeignKey('libraries.uuid'), nullable=False)
    size = db.Column(db.BigInteger, nullable=False, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Game id={self.id}, name={self.name}>"

class GameUpdate(db.Model):
    __tablename__ = 'game_updates'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), default=lambda: str(uuid4()), unique=True, nullable=False)
    game_uuid = db.Column(db.String(36), db.ForeignKey('games.uuid'), nullable=False)
    times_downloaded = db.Column(db.Integer, default=0)
    nfo_content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    game = db.relationship('Game', back_populates='updates')

    def __repr__(self):
        return f"<GameUpdate id={self.id}, uuid={self.uuid}, game_uuid={self.game_uuid}>"
    



class GameURL(db.Model):
    __tablename__ = 'game_urls'

    id = db.Column(db.Integer, primary_key=True)
    game_uuid = db.Column(db.String(36), db.ForeignKey('games.uuid'), nullable=False)
    url_type = db.Column(db.String, nullable=False)
    url = db.Column(db.String, nullable=False)

    game = db.relationship('Game', back_populates='urls')

    def __repr__(self):
        return f"<GameURL id={self.id}, game_uuid={self.game_uuid}, url_type={self.url_type}, url={self.url}>"


class Image(db.Model):
    __tablename__ = 'images'

    id = db.Column(db.Integer, primary_key=True)
    game_uuid = db.Column(db.String(36), db.ForeignKey('games.uuid'), nullable=False)
    image_type = db.Column(db.String, nullable=False)
    url = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Image id={self.id}, game_uuid={self.game_uuid}, image_type={self.image_type}, url={self.url}>"


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    favorites = db.relationship('Game', secondary='user_favorites', back_populates='favorited_by')
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(64), nullable=False)
    state = db.Column(db.Boolean, default=True)
    about = db.Column(db.String(256), unique=True, nullable=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    lastlogin = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String(36), unique=True, nullable=False, default=str(uuid4()))
    avatarpath = db.Column(db.String(256), default='newstyle/avatar_default.jpg')
    is_email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(256), nullable=True)
    password_reset_token = db.Column(db.String(256), nullable=True)
    
    preferences = db.relationship(
        'UserPreference',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan'
    )
    token_creation_time = db.Column(db.DateTime, nullable=True)
    invite_quota = db.Column(db.Integer, default=0) 
    
    def set_password(self, password):
        # Now using Argon2 to hash new passwords
        self.password_hash = ph.hash(password)

    def check_password(self, password):
        # Checking if the password hash starts with Argon2's identifier
        if self.password_hash.startswith('$argon2'):
            try:
                return ph.verify(self.password_hash, password)
            except VerifyMismatchError:
                return False
        else:
            # Fallback to the old bcrypt checking
            return check_password_hash(self.password_hash, password)
        
    def rehash_password(self, password):
        # Only rehash if the current hash is not using Argon2
        if not self.password_hash.startswith('$argon2'):
            self.password_hash = ph.hash(password)

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
    download_size = db.Column(db.Float, nullable=False, default=0.0)
    game = db.relationship('Game', foreign_keys=[game_uuid], back_populates='download_requests')
    file_location = db.Column(db.String, nullable=True)


class Whitelist(db.Model):
    __tablename__ = 'whitelist'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)

class ReleaseGroup(db.Model):
    __tablename__ = 'filters'

    id = db.Column(db.Integer, primary_key=True)
    rlsgroup = db.Column(db.String, nullable=True)
    rlsgroupcs = db.Column(db.String, nullable=True)

    def __repr__(self):
        return f"<ReleaseGroup id={self.id}, rlsgroup={self.rlsgroup}, rlsgroupcs={self.rlsgroupcs}>"



class GameMode(db.Model):
    __tablename__ = 'game_modes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    games = db.relationship("Game", secondary="game_game_mode_association", back_populates="game_modes")

class Theme(db.Model):
    __tablename__ = 'themes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    games = db.relationship("Game", secondary="game_theme_association", back_populates="themes")

class Genre(db.Model):
    __tablename__ = 'genres'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    games = db.relationship("Game", secondary="game_genre_association", back_populates="genres")

class Developer(db.Model):
    __tablename__ = 'developers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True)
    games = db.relationship("Game", back_populates="developer")

class Publisher(db.Model):
    __tablename__ = 'publishers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True)
    games = db.relationship("Game", back_populates="publisher")

class Platform(db.Model):
    __tablename__ = 'platforms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    games = db.relationship("Game", secondary="game_platform_association", back_populates="platforms")

class PlayerPerspective(db.Model):
    __tablename__ = 'player_perspectives'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    games = db.relationship("Game", secondary="game_player_perspective_association", back_populates="player_perspectives")

class MultiplayerMode(db.Model):
    __tablename__ = 'multiplayer_modes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    games = db.relationship("Game", secondary="game_multiplayer_mode_association", back_populates="multiplayer_modes")


def genre_choices():
    return Genre.query.all()

def game_mode_choices():
    return GameMode.query.all()

def theme_choices():
    return Theme.query.all()

def platform_choices():
    return Platform.query.all()

def player_perspective_choices():
    return PlayerPerspective.query.all()

def developer_choices():
    return Developer.query.all()

def publisher_choices():
    return Publisher.query.all()




class ScanJob(db.Model):
    __tablename__ = 'scan_jobs'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    folders = db.Column(JSONEncodedDict)
    content_type = db.Column(db.Enum('Games', name='content_type_enum'))
    schedule = db.Column(db.Enum('8_hours', '24_hours', '48_hours', name='schedule_enum'))
    is_enabled = db.Column(db.Boolean, default=True)
    status = db.Column(db.Enum('Scheduled', 'Running', 'Completed', 'Failed', name='status_enum'))
    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.String(512))
    total_folders = db.Column(db.Integer, default=0)
    folders_success = db.Column(db.Integer, default=0)
    folders_failed = db.Column(db.Integer, default=0)
    library_uuid = db.Column(db.String(36), db.ForeignKey('libraries.uuid'), nullable=True)
    library = db.relationship('Library', backref=db.backref('scan_jobs', lazy=True))


class UnmatchedFolder(db.Model):
    __tablename__ = 'unmatched_folders'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    library_uuid = db.Column(db.String(36), ForeignKey('libraries.uuid', ondelete="CASCADE"), nullable=True)
    scan_job_id = db.Column(db.String(36), db.ForeignKey('scan_jobs.id'))
    folder_path = db.Column(db.String)
    failed_time = db.Column(db.DateTime)
    content_type = db.Column(db.Enum('Games', name='unmatched_folder_content_type_enum'))
    status = db.Column(db.Enum('Pending', 'Ignore', 'Duplicate', 'Unmatched', name='unmatched_folder_status_enum'))

    

class UserPreference(db.Model):
    __tablename__ = 'user_preferences'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False
    )
    items_per_page = db.Column(db.Integer, default=20)
    default_sort = db.Column(db.String(50), default='name')
    default_sort_order = db.Column(db.String(4), default='asc')
    theme = db.Column(db.String(50), default='default')
    
    user = db.relationship('User', back_populates='preferences')

class GlobalSettings(db.Model):
    __tablename__ = 'global_settings'

    id = db.Column(db.Integer, primary_key=True)
    settings = db.Column(JSONEncodedDict)  # Store all settings in a single JSON-encoded column
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    discord_webhook_url = db.Column(db.String(255), nullable=True)
    discord_bot_name = db.Column(db.String(100), nullable=True)
    discord_bot_avatar_url = db.Column(db.String(255), nullable=True)
    enable_delete_game_on_disk = db.Column(db.Boolean, default=True)
    enable_main_game_updates = db.Column(db.Boolean, default=False)
    enable_game_updates = db.Column(db.Boolean, default=False)
    update_folder_name = db.Column(db.String(255), default='updates')
    enable_game_extras = db.Column(db.Boolean, default=False)
    extras_folder_name = db.Column(db.String(255), default='extras')
    discord_notify_new_games = db.Column(db.Boolean, default=False)
    discord_notify_game_updates = db.Column(db.Boolean, default=False)
    discord_notify_game_extras = db.Column(db.Boolean, default=False)
    discord_notify_downloads = db.Column(db.Boolean, default=False)
    site_url = db.Column(db.String(255), default='http://127.0.0.1')

    def __repr__(self):
        return f'<GlobalSettings id={self.id}, last_updated={self.last_updated}>'    
    
class InviteToken(db.Model):
    __tablename__ = 'invite_tokens'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(256), nullable=False, unique=True)
    creator_user_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=2), nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    recipient_email = db.Column(db.String(120), nullable=True)
    used_by = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)

    creator = db.relationship('User', foreign_keys=[creator_user_id], backref='created_invites')
    used_by_user = db.relationship('User', foreign_keys=[used_by], backref='used_invites')

    def __repr__(self):
        return f'<InviteToken {self.token}, Creator: {self.creator_user_id}, Expires: {self.expires_at}, Used: {self.used}>'