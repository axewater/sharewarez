# /modules/routes_apis/game.py
from flask import jsonify, request, url_for
from flask_login import login_required, current_user
from modules import db
from modules.models import Image, Game, Library, Genre, GameMode, PlayerPerspective, Theme
from modules.utils_logging import log_system_event
from sqlalchemy import func, select
from . import apis_bp

@apis_bp.route('/search')
@login_required
def search():
    query = request.args.get('query', '').strip()
    results = []
    if query:
        # Sanitize input - limit length and escape special characters
        if len(query) > 100:  # Reasonable search term length limit
            return jsonify({'error': 'Search term too long'}), 400

        # Build query with name search
        search_term = f'%{query}%'
        search_query = select(Game).filter(Game.name.ilike(search_term))

        # Apply active filters from request parameters
        library_uuid = request.args.get('library_uuid')
        genre = request.args.get('genre')
        rating = request.args.get('rating', type=int)
        game_mode = request.args.get('game_mode')
        player_perspective = request.args.get('player_perspective')
        theme = request.args.get('theme')

        # Apply filter logic matching routes_library.py:get_games()
        if library_uuid:
            search_query = search_query.filter(Game.library_uuid == library_uuid)
        if genre:
            search_query = search_query.filter(Game.genres.any(Genre.name == genre))
        if rating is not None:
            search_query = search_query.filter(Game.rating >= rating)
        if game_mode:
            search_query = search_query.filter(Game.game_modes.any(GameMode.name == game_mode))
        if player_perspective:
            search_query = search_query.filter(Game.player_perspectives.any(PlayerPerspective.name == player_perspective))
        if theme:
            search_query = search_query.filter(Game.themes.any(Theme.name == theme))

        # Execute query and build results
        games = db.session.execute(search_query).scalars().all()
        results = [{'id': game.id, 'uuid': game.uuid, 'name': game.name} for game in games]
    return jsonify(results)

@apis_bp.route('/game_screenshots/<game_uuid>')
@login_required
def game_screenshots(game_uuid):
    screenshots = db.session.execute(select(Image).filter_by(game_uuid=game_uuid, image_type='screenshot')).scalars().all()
    screenshot_urls = [url_for('static', filename=f'library/images/{screenshot.url}') for screenshot in screenshots]
    return jsonify(screenshot_urls)

@apis_bp.route('/move_game_to_library', methods=['POST'])
@login_required
def move_game_to_library():
    try:
        data = request.get_json()
        game_uuid = data.get('game_uuid')
        target_library_uuid = data.get('target_library_uuid')
        
        if not game_uuid or not target_library_uuid:
            return jsonify({
                'success': False,
                'message': 'Missing required parameters'
            }), 400
            
        game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalars().first()
        target_library = db.session.execute(select(Library).filter_by(uuid=target_library_uuid)).scalars().first()
        
        if not game or not target_library:
            return jsonify({
                'success': False,
                'message': 'Game or target library not found'
            }), 404
            
        # Update the game's library
        game.library_uuid = target_library_uuid
        db.session.commit()
        
        log_system_event(f"Game {game.name} moved to library {target_library.name} by user {current_user.name}", event_type='game', event_level='information')
        
        return jsonify({'success': True, 'message': f'Game moved to {target_library.name}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@apis_bp.route('/get_next_custom_igdb_id', methods=['GET'])
@login_required
def get_next_custom_igdb_id():
    """Return the next available custom IGDB ID (above 2000000420)"""
    try:
        # Find the highest custom IGDB ID currently in use
        base_custom_id = 2000000420
        highest_custom_id = db.session.execute(
            select(func.max(Game.igdb_id)).filter(Game.igdb_id >= base_custom_id)
        ).scalar()
        
        # If no custom IDs exist yet, return the base value, otherwise return the next available ID
        next_id = base_custom_id if highest_custom_id is None else highest_custom_id + 1
        return jsonify({'next_id': next_id})
    except Exception as e:
        print(f"Error getting next custom IGDB ID: {e}")
        return jsonify({'error': str(e)}), 500
