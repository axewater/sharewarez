# /modules/routes_admin_ext/access_management.py
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from modules.models import User, Whitelist, InviteToken
from modules import db
from sqlalchemy import select, func, and_
from . import admin2_bp
from modules.utils_logging import log_system_event
from modules.utils_auth import admin_required

@admin2_bp.route('/admin/access_management', methods=['GET'])
@login_required
@admin_required
def access_management():
    """Unified access management interface with master-detail view"""

    # Get all users with their related data in optimized queries
    users = db.session.execute(select(User)).scalars().all()

    # Get whitelist entries
    whitelist_entries = db.session.execute(select(Whitelist)).scalars().all()
    whitelist_emails = {entry.email.lower() for entry in whitelist_entries}

    # Get invite counts for all users in a single query
    user_invite_counts = db.session.execute(
        select(
            User.user_id,
            func.count(InviteToken.id).label('unused_count')
        )
        .select_from(User)
        .outerjoin(
            InviteToken,
            and_(
                InviteToken.creator_user_id == User.user_id,
                InviteToken.used == False
            )
        )
        .group_by(User.user_id)
    ).all()

    user_unused_invites = {row.user_id: row.unused_count for row in user_invite_counts}

    # Build unified user data structure
    unified_users = []
    for user in users:
        user_data = {
            'id': user.id,
            'user_id': user.user_id,
            'name': user.name,
            'email': user.email,
            'avatar': getattr(user, 'avatarpath', '/static/newstyle/default_avatar.png'),
            'role': user.role,
            'status': user.state,
            'email_verified': user.is_email_verified,
            'about': user.about,
            'whitelist_status': user.email.lower() in whitelist_emails,
            'invite_quota': user.invite_quota,
            'invites_used': user_unused_invites.get(user.user_id, 0),
            'last_login': getattr(user, 'lastlogin', None),
            'created_at': getattr(user, 'created', None)
        }
        unified_users.append(user_data)

    # Calculate stats
    stats = {
        'total_users': len(users),
        'active_users': sum(1 for user in users if user.state),
        'admin_users': sum(1 for user in users if user.role == 'admin'),
        'whitelist_count': len(whitelist_entries),
        'total_invites_available': sum(user.invite_quota for user in users),
        'total_invites_used': sum(user_unused_invites.values())
    }

    return render_template(
        'admin/admin_access_management.html',
        users=unified_users,
        stats=stats,
        whitelist_entries=whitelist_entries
    )

@admin2_bp.route('/admin/api/access_management/user/<int:user_id>/details', methods=['GET'])
@login_required
@admin_required
def get_user_details(user_id):
    """Get detailed user information for the detail panel"""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    # Get whitelist status
    whitelist_entry = db.session.execute(
        select(Whitelist).filter(func.lower(Whitelist.email) == user.email.lower())
    ).scalar_one_or_none()

    # Get invite information
    unused_invites = db.session.execute(
        select(func.count(InviteToken.id)).filter(
            and_(
                InviteToken.creator_user_id == user.user_id,
                InviteToken.used == False
            )
        )
    ).scalar()

    # Get recent invite tokens
    recent_invites = db.session.execute(
        select(InviteToken)
        .filter(InviteToken.creator_user_id == user.user_id)
        .order_by(InviteToken.created_at.desc())
        .limit(5)
    ).scalars().all()

    invite_data = []
    for invite in recent_invites:
        invite_data.append({
            'id': invite.id,
            'token': invite.token[:8] + '...',  # Partial token for security
            'created_at': invite.created_at.isoformat() if invite.created_at else None,
            'expires_at': invite.expires_at.isoformat() if invite.expires_at else None,
            'used': invite.used,
            'recipient_email': invite.recipient_email
        })

    user_details = {
        'id': user.id,
        'user_id': user.user_id,
        'name': user.name,
        'email': user.email,
        'avatar': getattr(user, 'avatarpath', '/static/newstyle/default_avatar.png'),
        'role': user.role,
        'status': user.state,
        'email_verified': user.is_email_verified,
        'about': user.about,
        'whitelist_status': whitelist_entry is not None,
        'whitelist_id': whitelist_entry.id if whitelist_entry else None,
        'invite_quota': user.invite_quota,
        'invites_available': user.invite_quota - unused_invites,
        'invites_used': unused_invites,
        'recent_invites': invite_data,
        'last_login': getattr(user, 'lastlogin', None),
        'created_at': getattr(user, 'created', None)
    }

    return jsonify({'success': True, 'user': user_details})

@admin2_bp.route('/admin/api/access_management/user/<int:user_id>/whitelist', methods=['POST'])
@login_required
@admin_required
def toggle_user_whitelist(user_id):
    """Toggle user's whitelist status"""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    try:
        # Check if user is already whitelisted
        whitelist_entry = db.session.execute(
            select(Whitelist).filter(func.lower(Whitelist.email) == user.email.lower())
        ).scalar_one_or_none()

        if whitelist_entry:
            # Remove from whitelist
            db.session.delete(whitelist_entry)
            db.session.commit()
            log_system_event(f"Admin {current_user.name} removed {user.email} from whitelist",
                           event_type='audit', event_level='information')
            return jsonify({'success': True, 'whitelisted': False, 'message': 'Removed from whitelist'})
        else:
            # Add to whitelist
            new_whitelist = Whitelist(email=user.email.lower())
            db.session.add(new_whitelist)
            db.session.commit()
            log_system_event(f"Admin {current_user.name} added {user.email} to whitelist",
                           event_type='audit', event_level='information')
            return jsonify({'success': True, 'whitelisted': True, 'message': 'Added to whitelist'})

    except Exception as e:
        db.session.rollback()
        log_system_event(f"Error toggling whitelist for {user.email}: {str(e)}",
                        event_type='error', event_level='error')
        return jsonify({'success': False, 'message': 'Failed to update whitelist status'}), 500

@admin2_bp.route('/admin/api/access_management/user/<int:user_id>/invites', methods=['POST'])
@login_required
@admin_required
def update_user_invites(user_id):
    """Update user's invite quota"""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    data = request.json
    if not data or 'quota' not in data:
        return jsonify({'success': False, 'message': 'Quota value required'}), 400

    try:
        new_quota = int(data['quota'])
        if new_quota < 0 or new_quota > 1000:
            return jsonify({'success': False, 'message': 'Quota must be between 0 and 1000'}), 400

        old_quota = user.invite_quota
        user.invite_quota = new_quota
        db.session.commit()

        log_system_event(f"Admin {current_user.name} updated invite quota for {user.name} from {old_quota} to {new_quota}",
                        event_type='audit', event_level='information')

        return jsonify({'success': True, 'message': f'Invite quota updated to {new_quota}'})

    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid quota value'}), 400
    except Exception as e:
        db.session.rollback()
        log_system_event(f"Error updating invite quota for {user.name}: {str(e)}",
                        event_type='error', event_level='error')
        return jsonify({'success': False, 'message': 'Failed to update invite quota'}), 500

@admin2_bp.route('/admin/api/access_management/user/<int:user_id>/update', methods=['POST'])
@login_required
@admin_required
def update_user_details(user_id):
    """Update user account details via the inline edit form"""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    try:
        # Import validation functions from the existing users module
        from .users import (validate_username, validate_email, validate_role, validate_about,
                          check_email_unique, check_username_unique, check_admin_protection)

        changes = []

        # Validate and update username
        if 'name' in data and data['name'] != user.name:
            new_name = data['name'].strip()
            valid, error = validate_username(new_name)
            if not valid:
                return jsonify({'success': False, 'message': error}), 400

            valid, error = check_username_unique(new_name, exclude_user_id=user_id)
            if not valid:
                return jsonify({'success': False, 'message': error}), 400

            changes.append(f"username from '{user.name}' to '{new_name}'")
            user.name = new_name

        # Validate and update email
        if 'email' in data and data['email'] != user.email:
            new_email = data['email'].strip().lower()
            valid, error = validate_email(new_email)
            if not valid:
                return jsonify({'success': False, 'message': error}), 400

            valid, error = check_email_unique(new_email, exclude_user_id=user_id)
            if not valid:
                return jsonify({'success': False, 'message': error}), 400

            changes.append(f"email from '{user.email}' to '{new_email}'")
            user.email = new_email

        # Validate and update role
        if 'role' in data and data['role'] != user.role:
            new_role = data['role']
            valid, error = validate_role(new_role)
            if not valid:
                return jsonify({'success': False, 'message': error}), 400

            valid, error = check_admin_protection(user_id, new_role=new_role)
            if not valid:
                return jsonify({'success': False, 'message': error}), 403

            changes.append(f"role from '{user.role}' to '{new_role}'")
            user.role = new_role

        # Validate and update status
        if 'status' in data:
            new_status = data['status'] == 'true' or data['status'] is True
            if new_status != user.state:
                valid, error = check_admin_protection(user_id, new_state=new_status)
                if not valid:
                    return jsonify({'success': False, 'message': error}), 403

                status_text = "active" if new_status else "inactive"
                changes.append(f"status to {status_text}")
                user.state = new_status

        # Validate and update about
        if 'about' in data and data['about'] != user.about:
            new_about = data['about']
            valid, error = validate_about(new_about)
            if not valid:
                return jsonify({'success': False, 'message': error}), 400

            changes.append("about field")
            user.about = new_about if new_about else None

        db.session.commit()

        # Log changes
        if changes:
            changes_str = ", ".join(changes)
            log_system_event(f"Admin {current_user.name} modified user {user.name}: {changes_str}",
                           event_type='audit', event_level='information')

        return jsonify({'success': True, 'message': 'User updated successfully'})

    except Exception as e:
        db.session.rollback()
        log_system_event(f"Error updating user {user.name}: {str(e)}",
                        event_type='error', event_level='error')
        return jsonify({'success': False, 'message': 'Failed to update user'}), 500

@admin2_bp.route('/admin/api/access_management/users/search', methods=['GET'])
@login_required
@admin_required
def search_users():
    """Search users for the master panel"""
    query = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '')
    status_filter = request.args.get('status', '')

    # Build query
    base_query = select(User)

    if query:
        base_query = base_query.filter(
            db.or_(
                User.name.ilike(f'%{query}%'),
                User.email.ilike(f'%{query}%')
            )
        )

    if role_filter and role_filter in ['admin', 'user']:
        base_query = base_query.filter(User.role == role_filter)

    if status_filter:
        if status_filter == 'active':
            base_query = base_query.filter(User.state == True)
        elif status_filter == 'inactive':
            base_query = base_query.filter(User.state == False)

    users = db.session.execute(base_query).scalars().all()

    # Get whitelist emails for filtering
    whitelist_entries = db.session.execute(select(Whitelist)).scalars().all()
    whitelist_emails = {entry.email.lower() for entry in whitelist_entries}

    # Get invite counts
    user_invite_counts = db.session.execute(
        select(
            User.user_id,
            func.count(InviteToken.id).label('unused_count')
        )
        .select_from(User)
        .outerjoin(
            InviteToken,
            and_(
                InviteToken.creator_user_id == User.user_id,
                InviteToken.used == False
            )
        )
        .group_by(User.user_id)
    ).all()

    user_unused_invites = {row.user_id: row.unused_count for row in user_invite_counts}

    # Format response
    user_list = []
    for user in users:
        user_data = {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'avatar': getattr(user, 'avatarpath', '/static/newstyle/default_avatar.png'),
            'role': user.role,
            'status': user.state,
            'email_verified': user.is_email_verified,
            'whitelist_status': user.email.lower() in whitelist_emails,
            'invite_quota': user.invite_quota,
            'invites_used': user_unused_invites.get(user.user_id, 0)
        }
        user_list.append(user_data)

    return jsonify({'success': True, 'users': user_list})