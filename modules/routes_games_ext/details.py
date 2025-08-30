import uuid
from flask import render_template, jsonify, abort
from flask_login import login_required
from modules.forms import CsrfForm
from modules.models import GameUpdate, GameExtra
from modules import db
from sqlalchemy import select
from modules.utils_functions import format_size
from modules.utils_game_core import get_game_by_uuid

from . import games_bp


@games_bp.route('/game_details/<string:game_uuid>')
@login_required
def game_details(game_uuid):
    print(f"Fetching game details for UUID: {game_uuid}")
    csrf_form = CsrfForm()
    try:
        valid_uuid = uuid.UUID(game_uuid, version=4)
    except ValueError:
        print(f"Invalid UUID format: {game_uuid}")
        abort(404)

    game = get_game_by_uuid(str(valid_uuid))

    if game:
        # Explicitly load updates and extras
        updates = db.session.execute(select(GameUpdate).filter_by(game_uuid=game.uuid)).scalars().all()
        extras = db.session.execute(select(GameExtra).filter_by(game_uuid=game.uuid)).scalars().all()
        print(f"Found {len(updates)} updates and {len(extras)} extras for game {game.name}")
        
        game_data = {
            "id": game.id,
            "uuid": game.uuid,
            "igdb_id": game.igdb_id,
            "name": game.name,
            "summary": game.summary,
            "storyline": game.storyline,
            "aggregated_rating": game.aggregated_rating,
            "aggregated_rating_count": game.aggregated_rating_count,
            "updates": [{
                "id": update.id,
                "file_path": update.file_path,
                "times_downloaded": update.times_downloaded,
                "created_at": update.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "nfo_content": update.nfo_content
            } for update in game.updates],
            "extras": [{
                "id": extra.id,
                "file_path": extra.file_path,
                "times_downloaded": extra.times_downloaded,
                "created_at": extra.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "nfo_content": extra.nfo_content
            } for extra in game.extras],
            "cover": game.cover,
            "first_release_date": game.first_release_date.strftime('%Y-%m-%d') if game.first_release_date else 'Not available',
            "rating": game.rating,
            "rating_count": game.rating_count,
            "slug": game.slug,
            "status": game.status.value if game.status else 'Not available',
            "category": game.category.value if game.category else 'Not available',
            "total_rating": game.total_rating,
            "total_rating_count": game.total_rating_count,
            "url_igdb": game.url_igdb,
            "url": game.url,
            "video_urls": game.video_urls,
            "full_disk_path": game.full_disk_path,
            "images": [{"id": img.id, "type": img.image_type, "url": img.url} for img in game.images.all()],
            "genres": [genre.name for genre in game.genres],
            "game_modes": [mode.name for mode in game.game_modes],
            "themes": [theme.name for theme in game.themes],
            "platforms": [platform.name for platform in game.platforms],
            "player_perspectives": [perspective.name for perspective in game.player_perspectives],
            "developer": game.developer.name if game.developer else 'Not available',
            "publisher": game.publisher.name if game.publisher else 'Not available',
            "multiplayer_modes": [mode.name for mode in game.multiplayer_modes],
            "nfo_content": game.nfo_content if game.nfo_content else 'none',
            "size": format_size(game.size),
            "date_identified": game.date_identified.strftime('%Y-%m-%d %H:%M:%S') if game.date_identified else 'Not available',
            "steam_url": game.steam_url if game.steam_url else 'Not available',
            "times_downloaded": game.times_downloaded,
            "last_updated": game.last_updated.strftime('%Y-%m-%d') if game.last_updated else 'N/A',
            "updates": [{
                "id": update.id,
                "file_path": update.file_path,
                "times_downloaded": update.times_downloaded,
                "created_at": update.created_at.strftime('%Y-%m-%d %H:%M:%S')
            } for update in game.updates]
        }
        
        # URL Icons Mapping
        url_icons = {
            "official": "fa-solid fa-globe",
            "wikia": "fa-brands fa-wikimedia",
            "wikipedia": "fa-brands fa-wikipedia-w",
            "facebook": "fa-brands fa-facebook",
            "twitter": "fa-brands fa-twitter",
            "twitch": "fa-brands fa-twitch",
            "instagram": "fa-brands fa-instagram",
            "youtube": "fa-brands fa-youtube",
            "steam": "fa-brands fa-steam",
            "reddit": "fa-brands fa-reddit",
            "itch": "fa-brands fa-itch-io",
            "epicgames": "fa-brands fa-epic-games",
            "gog": "fa-brands fa-gog",
            "discord": "fa-brands fa-discord",
        }
        # Augment game_data with URLs
        game_data['urls'] = [{
            "type": url.url_type,
            "url": url.url,
            "icon": url_icons.get(url.url_type, "fa-link")
        } for url in game.urls]
        
        library_uuid = game.library_uuid
        
        return render_template('games/game_details.html', game=game_data, form=csrf_form, library_uuid=library_uuid)
    else:
        return jsonify({"error": "Game not found"}), 404
