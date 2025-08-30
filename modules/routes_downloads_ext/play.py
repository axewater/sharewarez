import os
from flask import redirect, url_for, flash, jsonify, send_file, render_template
from flask_login import login_required
from modules import db
from modules.models import Game
from sqlalchemy import select
from modules.utils_logging import log_system_event
from . import download_bp

@download_bp.route('/play_game/<game_uuid>', methods=['GET'])
@login_required
def play_game(game_uuid):
    """Placeholder route for the play game functionality"""
    flash("Play game functionality coming soon!", "info")
    return redirect(url_for('games.game_details', game_uuid=game_uuid))

@download_bp.route('/playromtest', methods=['GET'])
@login_required
def playromtest():
    """Placeholder route for the play game functionality"""
    flash("Play game functionality coming soon!", "info")
    return render_template('games/playrom.html')

# This API route is used by WebRetro to download ROM files
@download_bp.route('/api/downloadrom/<string:guid>', methods=['GET'])
def downloadrom(guid):
    """
    Download a ROM file for WebRetro emulator.
    Only serves individual files, not folders.
    """
    game = db.session.execute(select(Game).filter_by(uuid=guid)).scalars().first()
    
    if game is None:
        return jsonify({"error": "Game not found"}), 404
    
    # Check if the game path exists
    if not os.path.exists(game.full_disk_path):
        return jsonify({"error": "ROM file not found on disk"}), 404
    
    # Check if the game is a folder (not supported by WebRetro)
    if os.path.isdir(game.full_disk_path):
        return jsonify({
            "error": "This game is a folder and cannot be played directly. Please download it instead."
        }), 400
    
    # Log the ROM download attempt
    log_system_event(f"ROM file downloaded for WebRetro: {game.name}", event_type='game', event_level='information')
    
    # Serve the file
    return send_file(game.full_disk_path, as_attachment=True)
