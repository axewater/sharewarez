# /modules/routes_apis/filters.py
from flask import jsonify
from flask_login import login_required
from modules.models import Genre, Theme, GameMode, PlayerPerspective
from modules import db
from sqlalchemy import select
from . import apis_bp

@apis_bp.route('/genres')
@login_required
def get_genres():
    genres = db.session.execute(select(Genre)).scalars().all()
    genres_list = [{'id': genre.id, 'name': genre.name} for genre in genres]
    return jsonify(genres_list)

@apis_bp.route('/themes')
@login_required
def get_themes():
    themes = db.session.execute(select(Theme)).scalars().all()
    themes_list = [{'id': theme.id, 'name': theme.name} for theme in themes]
    return jsonify(themes_list)

@apis_bp.route('/game_modes')
@login_required
def get_game_modes():
    game_modes = db.session.execute(select(GameMode)).scalars().all()
    game_modes_list = [{'id': game_mode.id, 'name': game_mode.name} for game_mode in game_modes]
    return jsonify(game_modes_list)

@apis_bp.route('/player_perspectives')
@login_required
def get_player_perspectives():
    perspectives = db.session.execute(select(PlayerPerspective)).scalars().all()
    perspectives_list = [{'id': perspective.id, 'name': perspective.name} for perspective in perspectives]
    return jsonify(perspectives_list)
