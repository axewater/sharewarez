from flask import jsonify, request, current_app
from flask_login import login_required
from modules.models import Genre, Theme, GameMode, PlayerPerspective
from modules.utils_processors import get_global_settings
from flask import Blueprint
from modules import cache

apis_filters_bp = Blueprint('apis_filters', __name__)

@apis_filters_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()

@apis_filters_bp.route('/api/genres')
@login_required
def get_genres():
    genres = Genre.query.all()
    genres_list = [{'id': genre.id, 'name': genre.name} for genre in genres]
    return jsonify(genres_list)

@apis_filters_bp.route('/api/themes')
@login_required
def get_themes():
    themes = Theme.query.all()
    themes_list = [{'id': theme.id, 'name': theme.name} for theme in themes]
    return jsonify(themes_list)

@apis_filters_bp.route('/api/game_modes')
@login_required
def get_game_modes():
    game_modes = GameMode.query.all()
    game_modes_list = [{'id': game_mode.id, 'name': game_mode.name} for game_mode in game_modes]
    return jsonify(game_modes_list)

@apis_filters_bp.route('/api/player_perspectives')
@login_required
def get_player_perspectives():
    perspectives = PlayerPerspective.query.all()
    perspectives_list = [{'id': perspective.id, 'name': perspective.name} for perspective in perspectives]
    return jsonify(perspectives_list)

