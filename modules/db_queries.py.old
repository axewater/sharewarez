# File: /modules/db_queries.py
# This file contains database query functions extracted from routes.py

from modules.models import User, Whitelist, ReleaseGroup, Game, Image, DownloadRequest, ScanJob, UnmatchedFolder, Publisher, Developer, Genre, Theme, GameMode, PlayerPerspective, Category, UserPreference, GameURL, GlobalSettings, InviteToken, Library, LibraryPlatform
from sqlalchemy.orm import joinedload
from sqlalchemy import func

def get_user_by_username(username):
    return User.query.filter_by(name=username).first()

def get_whitelist_by_email(email):
    return Whitelist.query.filter_by(email=email).first()

def get_release_group_by_id(id):
    return ReleaseGroup.query.get(id)

def get_game_by_uuid(uuid):
    return Game.query.options(joinedload(Game.genres)).filter_by(uuid=uuid).first()

def get_image_by_game_uuid(game_uuid):
    return Image.query.filter_by(game_uuid=game_uuid, image_type='cover').first()

def get_download_request_by_id(id):
    return DownloadRequest.query.get(id)

def get_scan_job_by_id(id):
    return ScanJob.query.get(id)

def get_unmatched_folder_by_path(path):
    return UnmatchedFolder.query.filter_by(folder_path=path).first()

def get_publisher_by_name(name):
    return Publisher.query.filter_by(name=name).first()

def get_developer_by_name(name):
    return Developer.query.filter_by(name=name).first()

def get_genre_by_name(name):
    return Genre.query.filter_by(name=name).first()

def get_theme_by_name(name):
    return Theme.query.filter_by(name=name).first()

def get_game_mode_by_name(name):
    return GameMode.query.filter_by(name=name).first()

def get_player_perspective_by_name(name):
    return PlayerPerspective.query.filter_by(name=name).first()

def get_category_by_name(name):
    return Category.query.filter_by(name=name).first()

def get_user_preference_by_user_id(user_id):
    return UserPreference.query.filter_by(user_id=user_id).first()

def get_game_url_by_game_uuid(game_uuid):
    return GameURL.query.filter_by(game_uuid=game_uuid).first()

def get_global_settings():
    return GlobalSettings.query.first()

def get_invite_token_by_token(token):
    return InviteToken.query.filter_by(token=token, used=False).first()

def get_library_by_uuid(uuid):
    return Library.query.filter_by(uuid=uuid).first()

def get_library_platform_by_name(name):
    return LibraryPlatform.query.filter_by(name=name).first()