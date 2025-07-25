# modules/routes_site.py
from flask import Blueprint, render_template, redirect, url_for, current_app, send_from_directory, jsonify, request
from flask_login import login_required, logout_user, current_user

from sqlalchemy import func
from flask import flash
import os
from modules.models import User, Image
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
    # Check if setup is required
    if not User.query.first():
        return redirect(url_for('setup.setup'))
        
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
        cover_image = Image.query.filter_by(game_uuid=game.uuid, image_type='cover').first()
        cover_url = cover_image.url if cover_image else 'newstyle/default_cover.jpg'
        genres = [genre.name for genre in game.genres]
        game_size_formatted = format_size(game.size)
        favorite_count = len(game.favorited_by)
        game_data.append({'uuid': game.uuid, 'name': game.name, 'cover_url': cover_url, 
                         'size': game_size_formatted, 'genres': genres, 
                         'favorite_count': favorite_count})
    
    return render_template('games/favorites.html', favorites=game_data)

@site_bp.route('/favicon.ico')
def favicon():
    favidir = "icons"
    full_dir = os.path.join(current_app.static_folder, favidir)
    # print(f"Full dir: {full_dir}" if os.path.isdir(full_dir) else f"Dir not found: {full_dir}")
    return send_from_directory(full_dir, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
