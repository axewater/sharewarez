from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from modules.models import DownloadRequest, Game, User, user_favorites, InviteToken
from modules import db
import shutil
import os

def get_download_statistics():
    """Gather various download statistics"""
    
    # Downloads per user
    downloads_per_user = db.session.query(
        User.name,
        func.count(DownloadRequest.id)
    ).join(DownloadRequest).group_by(User.id).all()

    # Top downloaded games
    top_games = db.session.query(
        Game.name,
        func.count(DownloadRequest.id)
    ).join(DownloadRequest).group_by(Game.id).order_by(
        func.count(DownloadRequest.id).desc()
    ).limit(10).all()

    # Download trends (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    download_trends = db.session.query(
        func.date(DownloadRequest.request_time),
        func.count(DownloadRequest.id)
    ).filter(
        DownloadRequest.request_time >= thirty_days_ago
    ).group_by(
        func.date(DownloadRequest.request_time)
    ).all()

    # Users with most downloads
    top_downloaders = db.session.query(
        User.name,
        func.count(DownloadRequest.id).label('download_count')
    ).join(DownloadRequest).group_by(User.id).order_by(
        func.count(DownloadRequest.id).desc()
    ).limit(10).all()

    # Users with most favorites
    top_collectors = db.session.query(
        User.name,
        func.count(user_favorites.c.game_uuid).label('favorite_count')
    ).join(user_favorites).group_by(User.id).order_by(
        func.count(user_favorites.c.game_uuid).desc()
    ).limit(10).all()

    # Users with invite tokens
    users_with_invites = db.session.query(
        User.name,
        func.count(InviteToken.id).label('invite_count')
    ).join(InviteToken, User.user_id == InviteToken.creator_user_id
    ).group_by(User.id
    ).order_by(func.count(InviteToken.id).desc()
    ).all()

    return {
        'users_with_invites': {
            'labels': [user[0] for user in users_with_invites],
            'data': [user[1] for user in users_with_invites]
        },
        'downloads_per_user': {
            'labels': [user[0] for user in downloads_per_user],
            'data': [user[1] for user in downloads_per_user]
        },
        'top_downloaders': {
            'labels': [user[0] for user in top_downloaders],
            'data': [user[1] for user in top_downloaders]
        },
        'top_collectors': {
            'labels': [user[0] for user in top_collectors],
            'data': [user[1] for user in top_collectors]
        },
        'top_games': {
            'labels': [game[0] for game in top_games],
            'data': [game[1] for game in top_games]
        },
        'download_trends': {
            'labels': [trend[0].strftime('%Y-%m-%d') for trend in download_trends],
            'data': [trend[1] for trend in download_trends]
        }
    }
