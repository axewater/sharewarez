# /modules/routes_apis/user.py
from flask import jsonify, request
from flask_login import login_required, current_user
from modules import db
from modules.models import Game, User
from sqlalchemy import func, select
from . import apis_bp

@apis_bp.route('/current_user_role', methods=['GET'])
@login_required
def get_current_user_role():
    return jsonify({'role': current_user.role}), 200

@apis_bp.route('/check_username', methods=['POST'])
@login_required
def check_username():
    print(F"Route: /api/check_username - {current_user.name} - {current_user.role}")    
    data = request.get_json()
    username = data.get('username')
    if not username:
        print(f"Check username: Missing username")
        return jsonify({"error": "Missing username parameter"}), 400
    print(f"Checking username: {username}")
    existing_user = db.session.execute(select(User).filter(func.lower(User.name) == func.lower(username))).scalars().first()
    return jsonify({"exists": existing_user is not None})

@apis_bp.route('/check_favorite/<game_uuid>')
@login_required
def check_favorite(game_uuid):
    game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalars().first()
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    is_favorite = game in current_user.favorites
    return jsonify({'is_favorite': is_favorite})

@apis_bp.route('/toggle_favorite/<game_uuid>', methods=['POST'])
@login_required
def toggle_favorite(game_uuid):
    game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalars().first()
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    if game in current_user.favorites:
        current_user.favorites.remove(game)
        is_favorite = False
    else:
        current_user.favorites.append(game)
        is_favorite = True
    
    db.session.commit()
    return jsonify({'success': True, 'is_favorite': is_favorite})
