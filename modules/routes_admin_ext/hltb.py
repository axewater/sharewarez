# /modules/routes_admin_ext/hltb.py
from flask import jsonify, request
from flask_login import login_required
from modules.models import GlobalSettings, Game
from modules import db
from sqlalchemy import select
from . import admin2_bp
from modules.utils_auth import admin_required
from modules.utils_hltb import update_game_hltb_sync, get_games_without_hltb, get_hltb_stats
import logging

logger = logging.getLogger(__name__)


@admin2_bp.route('/api/hltb/stats', methods=['GET'])
@login_required
@admin_required
def get_hltb_statistics():
    """Get statistics about HLTB data coverage."""
    try:
        stats = get_hltb_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting HLTB stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin2_bp.route('/api/hltb/refresh/<game_uuid>', methods=['POST'])
@login_required
@admin_required
def refresh_game_hltb(game_uuid):
    """Refresh HLTB data for a single game."""
    try:
        # Check if HLTB integration is enabled
        settings = db.session.execute(select(GlobalSettings)).scalars().first()
        if not settings or not settings.enable_hltb_integration:
            return jsonify({
                'success': False,
                'error': 'HLTB integration is not enabled'
            }), 400

        # Get game
        game = db.session.execute(
            select(Game).where(Game.uuid == game_uuid)
        ).scalars().first()

        if not game:
            return jsonify({
                'success': False,
                'error': 'Game not found'
            }), 404

        # Fetch and update HLTB data
        success = update_game_hltb_sync(game_uuid, game.name)

        if success:
            # Refresh the game object to get updated data
            db.session.refresh(game)
            return jsonify({
                'success': True,
                'message': f'HLTB data updated for {game.name}',
                'data': {
                    'hltb_id': game.hltb_id,
                    'hltb_main_story': game.hltb_main_story,
                    'hltb_main_extra': game.hltb_main_extra,
                    'hltb_completionist': game.hltb_completionist,
                    'hltb_all_styles': game.hltb_all_styles,
                    'hltb_last_updated': game.hltb_last_updated.isoformat() if game.hltb_last_updated else None
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch HLTB data. Game may not be found on HowLongToBeat.'
            }), 404

    except Exception as e:
        logger.error(f"Error refreshing HLTB data for game {game_uuid}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin2_bp.route('/api/hltb/bulk-refresh', methods=['POST'])
@login_required
@admin_required
def bulk_refresh_hltb():
    """Bulk refresh HLTB data for games without it."""
    try:
        # Check if HLTB integration is enabled
        settings = db.session.execute(select(GlobalSettings)).scalars().first()
        if not settings or not settings.enable_hltb_integration:
            return jsonify({
                'success': False,
                'error': 'HLTB integration is not enabled'
            }), 400

        # Get limit from request (default 50, max 200)
        limit = request.json.get('limit', 50) if request.json else 50
        limit = min(max(limit, 1), 200)  # Clamp between 1 and 200

        # Get games without HLTB data
        games_to_update = get_games_without_hltb(limit=limit)

        if not games_to_update:
            return jsonify({
                'success': True,
                'message': 'No games need HLTB data update',
                'processed': 0,
                'successful': 0,
                'failed': 0
            })

        # Process games
        processed = 0
        successful = 0
        failed = 0
        errors = []

        for game in games_to_update:
            processed += 1
            try:
                success = update_game_hltb_sync(game.uuid, game.name)
                if success:
                    successful += 1
                else:
                    failed += 1
                    errors.append(f'{game.name}: Not found on HLTB')
            except Exception as e:
                failed += 1
                errors.append(f'{game.name}: {str(e)}')
                logger.error(f"Error updating HLTB for {game.name}: {e}")

        return jsonify({
            'success': True,
            'message': f'Processed {processed} games: {successful} successful, {failed} failed',
            'processed': processed,
            'successful': successful,
            'failed': failed,
            'errors': errors[:10]  # Return first 10 errors only
        })

    except Exception as e:
        logger.error(f"Error in bulk HLTB refresh: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
