from flask import Blueprint, render_template, url_for
from sqlalchemy import func
from modules.utils_functions import format_size
from modules.utils_processors import get_loc
from modules.models import Game, Library, user_favorites, DiscoverySection
from modules import db
from flask_login import login_required, current_user
from modules.models import Image
from modules.utils_processors import get_global_settings
from modules import cache

discover_bp = Blueprint('discover', __name__)

@discover_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()


@discover_bp.context_processor
def inject_current_theme():
    if current_user.is_authenticated and current_user.preferences:
        current_theme = current_user.preferences.theme or 'default'
    else:
        current_theme = 'default'
    return dict(current_theme=current_theme)

@discover_bp.route('/discover')
@login_required
def discover():
    page_loc = get_loc("discover")
    
    # Get visible sections in correct order
    sections = DiscoverySection.query.filter_by(is_visible=True).order_by(DiscoverySection.display_order).all()
    
    def fetch_game_details(games_query, limit=8):
        # Handle both query objects and lists
        if hasattr(games_query, 'limit'):
            games = games_query.limit(limit).all()
        else:
            games = games_query[:limit] if limit else games_query

        game_details = []
        for game in games:
            # If game is a tuple (from group by query), get the Game object
            if isinstance(game, tuple):
                game = game[0]
                
            cover_image = Image.query.filter_by(game_uuid=game.uuid, image_type='cover').first()
            cover_url = cover_image.url if cover_image else url_for('static', filename='newstyle/default_cover.jpg')
            game_details.append({
                'id': game.id,
                'uuid': game.uuid,
                'name': game.name,
                'cover_url': cover_url,
                'summary': game.summary,
                'url': game.url,
                'size': format_size(game.size),
                'genres': [genre.name for genre in game.genres],
                'first_release_date': game.first_release_date.strftime('%Y-%m-%d') if game.first_release_date else 'Not available',
                # Optionally include library information here
            })
        return game_details

    # Create a dictionary to store section data
    section_data = {}
    
    for section in sections:
        if section.identifier == 'libraries':
            section_data['libraries'] = fetch_game_details(Game.query.order_by(Game.date_created.desc()))
        elif section.identifier == 'latest_games':
            section_data['latest_games'] = fetch_game_details(Game.query.order_by(Game.date_created.desc()))
        elif section.identifier == 'most_downloaded':
            section_data['most_downloaded'] = fetch_game_details(Game.query.order_by(Game.times_downloaded.desc()))
        elif section.identifier == 'highest_rated':
            section_data['highest_rated'] = fetch_game_details(Game.query.filter(Game.rating != None).order_by(Game.rating.desc()))
        elif section.identifier == 'last_updated':
            section_data['last_updated'] = fetch_game_details(Game.query.filter(Game.last_updated != None).order_by(Game.last_updated.desc()))
        elif section.identifier == 'most_favorited':
            most_favorited = db.session.query(Game, func.count(user_favorites.c.user_id).label('favorite_count')).join(user_favorites).group_by(Game).order_by(func.count(user_favorites.c.user_id).desc())
            section_data['most_favorited'] = fetch_game_details([game[0] for game in most_favorited])

    return render_template('games/discover.html',
                           sections=sections,
                           section_data=section_data,
                           loc=page_loc)
