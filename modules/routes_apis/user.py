# /modules/routes_apis/user.py
from flask import jsonify, request
from flask_login import login_required, current_user
from modules import db
from modules.models import Game, User, user_game_status, get_status_info
from sqlalchemy import func, select, and_, delete
from datetime import datetime, timezone
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

@apis_bp.route('/get_game_status/<game_uuid>', methods=['GET'])
@login_required
def get_game_status(game_uuid):
    """Get the current user's completion status for a game"""
    game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalars().first()
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    # Query the status
    status_row = db.session.execute(
        select(user_game_status.c.status).where(
            and_(
                user_game_status.c.user_id == current_user.id,
                user_game_status.c.game_uuid == game_uuid
            )
        )
    ).first()

    status = status_row[0] if status_row else None
    status_info = get_status_info(status)

    return jsonify({
        'success': True,
        'status': status,
        'status_info': status_info
    })

@apis_bp.route('/set_game_status/<game_uuid>', methods=['POST'])
@login_required
def set_game_status(game_uuid):
    """Set or update the user's completion status for a game"""
    game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalars().first()
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    data = request.get_json()
    status = data.get('status', '').strip()

    # Validate status
    valid_statuses = ['unplayed', 'unfinished', 'beaten', 'completed', 'null', '']
    if status not in valid_statuses:
        return jsonify({'error': 'Invalid status value'}), 400

    # If status is empty, remove the status record
    if not status:
        db.session.execute(
            delete(user_game_status).where(
                and_(
                    user_game_status.c.user_id == current_user.id,
                    user_game_status.c.game_uuid == game_uuid
                )
            )
        )
        db.session.commit()
        return jsonify({
            'success': True,
            'status': None,
            'status_info': get_status_info(None),
            'message': 'Status cleared'
        })

    # Check if status already exists
    existing = db.session.execute(
        select(user_game_status).where(
            and_(
                user_game_status.c.user_id == current_user.id,
                user_game_status.c.game_uuid == game_uuid
            )
        )
    ).first()

    if existing:
        # Update existing status
        db.session.execute(
            user_game_status.update().where(
                and_(
                    user_game_status.c.user_id == current_user.id,
                    user_game_status.c.game_uuid == game_uuid
                )
            ).values(
                status=status,
                updated_at=datetime.now(timezone.utc)
            )
        )
    else:
        # Insert new status
        db.session.execute(
            user_game_status.insert().values(
                user_id=current_user.id,
                game_uuid=game_uuid,
                status=status,
                updated_at=datetime.now(timezone.utc)
            )
        )

    db.session.commit()
    status_info = get_status_info(status)

    return jsonify({
        'success': True,
        'status': status,
        'status_info': status_info,
        'message': f'Status updated to {status_info["label"]}'
    })
