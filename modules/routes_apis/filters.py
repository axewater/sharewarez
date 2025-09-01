# /modules/routes_apis/filters.py
from typing import Tuple, List, Dict, Any, Type
from flask import jsonify, Response
from flask_login import login_required
from modules.models import Genre, Theme, GameMode, PlayerPerspective
from modules import db
from modules.utils_logging import log_system_event
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from . import apis_bp

def _get_filter_data(model_class: Type[db.Model], filter_type: str) -> Tuple[Response, int]:
    """
    Generic helper function to fetch and format filter data.
    
    Args:
        model_class: SQLAlchemy model class to query
        filter_type: String identifier for logging purposes
        
    Returns:
        Tuple of JSON response and HTTP status code
    """
    try:
        log_system_event('filters_api', f'Fetching {filter_type} data', 'info')
        
        results = db.session.execute(select(model_class)).scalars().all()
        data_list = [{'id': item.id, 'name': item.name} for item in results]
        
        log_system_event('filters_api', f'Successfully retrieved {len(data_list)} {filter_type} items', 'info')
        return jsonify(data_list), 200
        
    except SQLAlchemyError as e:
        log_system_event('filters_api', f'Database error fetching {filter_type}: {str(e)}', 'error')
        return jsonify({
            'status': 'error',
            'message': f'Database error retrieving {filter_type}'
        }), 500
        
    except Exception as e:
        log_system_event('filters_api', f'Unexpected error fetching {filter_type}: {str(e)}', 'error')
        return jsonify({
            'status': 'error',
            'message': f'Error retrieving {filter_type}'
        }), 500


@apis_bp.route('/genres')
@login_required
def get_genres() -> Tuple[Response, int]:
    """
    Get all available game genres.
    
    Returns:
        JSON response containing list of genres with id and name fields.
        On success: List of genre objects with 200 status
        On error: Error object with appropriate status code
    """
    return _get_filter_data(Genre, 'genres')


@apis_bp.route('/themes')
@login_required
def get_themes() -> Tuple[Response, int]:
    """
    Get all available game themes.
    
    Returns:
        JSON response containing list of themes with id and name fields.
        On success: List of theme objects with 200 status
        On error: Error object with appropriate status code
    """
    return _get_filter_data(Theme, 'themes')


@apis_bp.route('/game_modes')
@login_required
def get_game_modes() -> Tuple[Response, int]:
    """
    Get all available game modes.
    
    Returns:
        JSON response containing list of game modes with id and name fields.
        On success: List of game mode objects with 200 status
        On error: Error object with appropriate status code
    """
    return _get_filter_data(GameMode, 'game_modes')


@apis_bp.route('/player_perspectives')
@login_required
def get_player_perspectives() -> Tuple[Response, int]:
    """
    Get all available player perspectives.
    
    Returns:
        JSON response containing list of player perspectives with id and name fields.
        On success: List of perspective objects with 200 status
        On error: Error object with appropriate status code
    """
    return _get_filter_data(PlayerPerspective, 'player_perspectives')
