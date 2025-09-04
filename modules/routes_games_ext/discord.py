from flask import jsonify, request
from flask_login import login_required, current_user
from modules.models import GlobalSettings, Game, db
from modules.utils_discord import discord_webhook
from modules.utils_logging import log_system_event
from sqlalchemy import select
from . import games_bp


@games_bp.route('/trigger_discord_notification/<game_uuid>', methods=['POST'])
@login_required
def trigger_discord_notification(game_uuid):
    """
    Manually trigger a Discord notification for a specific game.
    Requires Discord to be configured and manual triggers to be enabled.
    Admin only feature.
    """
    # Check if user is admin
    if current_user.role != 'admin':
        return jsonify({
            'success': False,
            'message': 'Admin access required'
        }), 403
    
    try:
        # Get global settings
        settings = db.session.execute(select(GlobalSettings)).scalars().first()
        
        # Check if Discord is configured
        if not settings or not settings.discord_webhook_url:
            return jsonify({
                'success': False, 
                'message': 'Discord notifications are not configured'
            }), 400
        
        # Check if manual triggers are enabled
        if not settings.discord_notify_manual_trigger:
            return jsonify({
                'success': False,
                'message': 'Manual Discord notifications are not enabled'
            }), 403
        
        # Verify the game exists
        game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalars().first()
        if not game:
            return jsonify({
                'success': False,
                'message': 'Game not found'
            }), 404
        
        # Log the action
        log_system_event(
            f"User {current_user.name} manually triggered Discord notification for game: {game.name}",
            event_type='audit',
            event_level='information'
        )
        
        # Send the Discord notification with manual_trigger flag
        try:
            discord_webhook(game_uuid, manual_trigger=True)
            return jsonify({
                'success': True,
                'message': f'Discord notification sent for {game.name}'
            }), 200
        except Exception as e:
            log_system_event(
                f"Failed to send Discord notification for game {game.name}: {str(e)}",
                event_type='error',
                event_level='error'
            )
            return jsonify({
                'success': False,
                'message': 'Failed to send Discord notification'
            }), 500
            
    except Exception as e:
        log_system_event(
            f"Error in trigger_discord_notification: {str(e)}",
            event_type='error',
            event_level='error'
        )
        return jsonify({
            'success': False,
            'message': 'An error occurred while processing your request'
        }), 500