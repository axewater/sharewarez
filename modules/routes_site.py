# modules/routes_site.py
from flask import Blueprint, render_template, redirect, url_for, current_app, send_from_directory, jsonify, request
from flask_login import login_required, logout_user, current_user

from sqlalchemy import func, select
from modules import db
from flask import flash
import os
import random
import re
from modules.models import User, Image, Game
from modules.utils_processors import get_global_settings
from modules.utils_auth import admin_required
from modules.utils_functions import format_size
from modules import cache

site_bp = Blueprint('site', __name__)

@site_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()

@site_bp.route('/restricted')
@login_required
def restricted():
    print("Route: /restricted")
    return render_template('site/restricted_area.html', title='Restricted Area')


@site_bp.route('/help')
def helpfaq():
    print("Route: /help")
    return render_template('site/site_help.html')

@site_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login.login'))


@site_bp.route('/', methods=['GET', 'POST'])
@site_bp.route('/index', methods=['GET', 'POST'])
def index():
    from modules.utils_setup import is_setup_required, is_setup_in_progress, get_setup_redirect_url
    
    # Check if setup is required or in progress
    if is_setup_required() or is_setup_in_progress():
        setup_url = get_setup_redirect_url()
        return redirect(setup_url)
        
    # If not authenticated, redirect to login
    if not current_user.is_authenticated:
        return redirect(url_for('login.login'))
        
    # If authenticated, redirect to discover page
    return redirect(url_for('discover.discover'))

@site_bp.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    print(f"Route: /admin/dashboard - {current_user.name} - {current_user.role} method: {request.method}")
    return render_template('admin/admin_dashboard.html')


@site_bp.route('/favorites')
@login_required
def favorites():
    favorites = current_user.favorites
    game_data = []
    for game in favorites:
        cover_image = db.session.execute(select(Image).filter_by(game_uuid=game.uuid, image_type='cover')).scalars().first()
        cover_url = cover_image.url if cover_image else 'newstyle/default_cover.jpg'
        genres = [genre.name for genre in game.genres]
        game_size_formatted = format_size(game.size)
        favorite_count = len(game.favorited_by)
        game_data.append({'uuid': game.uuid, 'name': game.name, 'cover_url': cover_url, 
                         'size': game_size_formatted, 'genres': genres, 
                         'favorite_count': favorite_count, 'is_favorite': True})
    
    return render_template('games/favorites.html', favorites=game_data)

@site_bp.route('/favicon.ico')
def favicon():
    favidir = "icons"
    full_dir = os.path.join(current_app.static_folder, favidir)
    # print(f"Full dir: {full_dir}" if os.path.isdir(full_dir) else f"Dir not found: {full_dir}")
    return send_from_directory(full_dir, 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@site_bp.route('/trailers')
@login_required
def random_trailers():
    """Main page for watching random game trailers"""
    return render_template('site/random_trailers.html')


@site_bp.route('/api/trailers/random')
@login_required
def get_random_trailer():
    """API endpoint to get a random game with trailer"""
    try:
        # Query all games that have video URLs
        games_with_videos = db.session.execute(
            select(Game).filter(
                Game.video_urls.isnot(None),
                Game.video_urls != ''
            )
        ).scalars().all()

        if not games_with_videos:
            return jsonify({
                'has_videos': False,
                'message': 'No games with trailers found in the database'
            }), 404

        # Select a random game
        random_game = random.choice(games_with_videos)

        # Parse video URLs (comma-separated)
        video_urls = [url.strip() for url in random_game.video_urls.split(',') if url.strip()]

        if not video_urls:
            # If somehow we got empty URLs, try another game
            return jsonify({
                'has_videos': False,
                'message': 'No valid video URLs found'
            }), 404

        # Pick a random video if multiple exist
        selected_video = random.choice(video_urls)

        # Convert YouTube watch URL to embed URL if needed
        embed_url = convert_to_embed_url(selected_video)

        # Return game data and video
        return jsonify({
            'has_videos': True,
            'game_uuid': random_game.uuid,
            'game_name': random_game.name,
            'video_url': embed_url
        })

    except Exception as e:
        print(f"Error fetching random trailer: {e}")
        return jsonify({
            'has_videos': False,
            'message': 'Error fetching trailer'
        }), 500


def convert_to_embed_url(video_url):
    """Convert YouTube URL to embed format with autoplay"""
    # Extract video ID from various YouTube URL formats
    youtube_patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        r'youtube\.com/embed/([a-zA-Z0-9_-]+)',
        r'youtu\.be/([a-zA-Z0-9_-]+)'
    ]

    for pattern in youtube_patterns:
        match = re.search(pattern, video_url)
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0"

    # If already in embed format or unknown format, add autoplay parameter
    if 'autoplay' not in video_url:
        separator = '&' if '?' in video_url else '?'
        return f"{video_url}{separator}autoplay=1&rel=0"

    return video_url
