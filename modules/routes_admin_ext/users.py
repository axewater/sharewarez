# /modules/routes_admin_ext/users.py
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from modules.models import User
from modules import db
from sqlalchemy import select, func
from . import admin2_bp
from uuid import uuid4
from modules.utils_logging import log_system_event
from modules.utils_auth import admin_required
import re
from sqlalchemy.exc import IntegrityError

# Validation constants and functions
VALID_ROLES = ['admin', 'user']
RESERVED_USERNAMES = ['system']

def validate_username(username):
    """Validate username according to business rules"""
    if not username or not isinstance(username, str):
        return False, "Username is required"
    
    if username.lower() in RESERVED_USERNAMES:
        return False, f"'{username}' is a reserved username and cannot be used"
    
    if not re.match(r'^[\w.]+$', username):
        return False, "Username can only contain letters, numbers, dots and underscores"
    
    if len(username) < 3 or len(username) > 64:
        return False, "Username must be between 3 and 64 characters long"
    
    return True, ""

def validate_email(email):
    """Validate email format and requirements"""
    if not email or not isinstance(email, str):
        return False, "Email is required"
    
    # Basic email regex validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "Invalid email format"
    
    if len(email) > 120:
        return False, "Email address too long"
    
    return True, ""

def validate_role(role):
    """Validate role is allowed"""
    if not role or not isinstance(role, str):
        return False, "Role is required"
    
    if role not in VALID_ROLES:
        return False, f"Role must be one of: {', '.join(VALID_ROLES)}"
    
    return True, ""

def validate_about(about):
    """Validate about field constraints"""
    if about is not None:
        if not isinstance(about, str):
            return False, "About field must be a string"
        if len(about) > 256:
            return False, "About field cannot exceed 256 characters"
    
    return True, ""

def check_email_unique(email, exclude_user_id=None):
    """Check if email is unique in the system"""
    query = db.session.execute(
        select(User).where(func.lower(User.email) == email.lower())
    ).scalars()
    
    existing_user = query.first()
    if existing_user and existing_user.id != exclude_user_id:
        return False, "Email address is already in use"
    return True, ""

def check_username_unique(username, exclude_user_id=None):
    """Check if username is unique in the system"""
    query = db.session.execute(
        select(User).where(func.lower(User.name) == username.lower())
    ).scalars()
    
    existing_user = query.first()
    if existing_user and existing_user.id != exclude_user_id:
        return False, "Username is already taken"
    return True, ""

def check_admin_protection(user_id, new_role=None, new_state=None):
    """Check if operation would leave system without active admin"""
    # Count current active admins
    current_admin_count = db.session.execute(
        select(func.count(User.id)).where(
            User.role == 'admin',
            User.state == True
        )
    ).scalar()
    
    user = db.session.get(User, user_id)
    if not user:
        return False, "User not found"
    
    # If this is the only active admin and we're trying to demote or deactivate
    if (user.role == 'admin' and user.state and current_admin_count <= 1):
        if (new_role and new_role != 'admin') or (new_state is not None and not new_state):
            return False, "Cannot modify the last active admin account"
    
    return True, ""

@admin2_bp.route('/admin/users', methods=['GET'])
@login_required
@admin_required
def manage_users():
    users = db.session.execute(select(User)).scalars().all()
    return render_template('admin/admin_manage_users.html', users=users)

@admin2_bp.route('/admin/api/user/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@admin_required
def manage_user_api(user_id):
    if request.method == 'PUT' and user_id == 0:  # Special case for new user creation
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Validate required fields
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        role = data.get('role', 'user')
        state = data.get('state', True)
        is_email_verified = data.get('is_email_verified', True)
        about = data.get('about', '')
        
        # Input validation
        valid, error = validate_username(username)
        if not valid:
            return jsonify({'success': False, 'message': error}), 400
            
        valid, error = validate_email(email)
        if not valid:
            return jsonify({'success': False, 'message': error}), 400
            
        valid, error = validate_role(role)
        if not valid:
            return jsonify({'success': False, 'message': error}), 400
            
        valid, error = validate_about(about)
        if not valid:
            return jsonify({'success': False, 'message': error}), 400
        
        if not password:
            return jsonify({'success': False, 'message': 'Password is required'}), 400
        
        # Type validation
        if not isinstance(state, bool):
            return jsonify({'success': False, 'message': 'State must be true or false'}), 400
            
        if not isinstance(is_email_verified, bool):
            return jsonify({'success': False, 'message': 'Email verification status must be true or false'}), 400
        
        # Uniqueness checks
        valid, error = check_username_unique(username)
        if not valid:
            return jsonify({'success': False, 'message': error}), 400
            
        valid, error = check_email_unique(email)
        if not valid:
            return jsonify({'success': False, 'message': error}), 400
        
        try:
            new_user = User(
                name=username,
                email=email,
                role=role,
                state=state,
                is_email_verified=is_email_verified,
                about=about if about else None,
                user_id=str(uuid4())
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            log_system_event(f"Admin {current_user.name} created new user: {username} (email: {email}, role: {role})", event_type='audit', event_level='information')
            return jsonify({'success': True})
        except IntegrityError as e:
            db.session.rollback()
            log_system_event(f"Admin {current_user.name} failed to create user {username}: Database integrity error", event_type='audit', event_level='error')
            return jsonify({'success': False, 'message': 'Username or email already exists'}), 400
        except Exception as e:
            db.session.rollback()
            log_system_event(f"Admin {current_user.name} failed to create user {username}: {str(e)}", event_type='audit', event_level='error')
            return jsonify({'success': False, 'message': 'Failed to create user'}), 500

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    if request.method == 'GET':
        return jsonify({
            'email': user.email,
            'role': user.role,
            'state': user.state,
            'about': user.about,
            'is_email_verified': user.is_email_verified
        })
    
    elif request.method == 'PUT':
        # Enhanced permission checks
        if user_id == 1 and current_user.id != 1:
            return jsonify({'success': False, 'message': 'Cannot modify primary admin account'}), 403
        
        # Prevent users from modifying their own role
        if current_user.id == user_id:
            data = request.json or {}
            if data.get('role') and data['role'] != user.role:
                return jsonify({'success': False, 'message': 'Cannot modify your own role'}), 403
        
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Track changes for audit logging
        changes = []
        old_values = {'email': user.email, 'role': user.role, 'state': user.state, 'is_email_verified': user.is_email_verified, 'about': user.about}
        
        # Validate and update email if provided
        if 'email' in data:
            new_email = data['email'].strip().lower()
            if new_email != user.email.lower():
                valid, error = validate_email(new_email)
                if not valid:
                    return jsonify({'success': False, 'message': error}), 400
                    
                valid, error = check_email_unique(new_email, exclude_user_id=user_id)
                if not valid:
                    return jsonify({'success': False, 'message': error}), 400
                
                changes.append(f"email from '{user.email}' to '{new_email}'")
                user.email = new_email
        
        # Validate and update role if provided
        if 'role' in data:
            new_role = data['role']
            if new_role != user.role:
                valid, error = validate_role(new_role)
                if not valid:
                    return jsonify({'success': False, 'message': error}), 400
                
                # Check admin protection before role change
                valid, error = check_admin_protection(user_id, new_role=new_role)
                if not valid:
                    return jsonify({'success': False, 'message': error}), 403
                
                changes.append(f"role from '{user.role}' to '{new_role}'")
                user.role = new_role
        
        # Validate and update state if provided
        if 'state' in data:
            new_state = data['state']
            if not isinstance(new_state, bool):
                return jsonify({'success': False, 'message': 'State must be true or false'}), 400
            
            if new_state != user.state:
                # Check admin protection before state change
                valid, error = check_admin_protection(user_id, new_state=new_state)
                if not valid:
                    return jsonify({'success': False, 'message': error}), 403
                
                status = "active" if new_state else "inactive"
                changes.append(f"state to {status}")
                user.state = new_state
        
        # Validate and update email verification status if provided
        if 'is_email_verified' in data:
            new_verification = data['is_email_verified']
            if not isinstance(new_verification, bool):
                return jsonify({'success': False, 'message': 'Email verification status must be true or false'}), 400
            
            if new_verification != user.is_email_verified:
                status = "verified" if new_verification else "unverified"
                changes.append(f"email verification to {status}")
                user.is_email_verified = new_verification
        
        # Validate and update about field if provided
        if 'about' in data:
            new_about = data['about']
            valid, error = validate_about(new_about)
            if not valid:
                return jsonify({'success': False, 'message': error}), 400
            
            if new_about != user.about:
                changes.append("about field")
                user.about = new_about
        
        # Handle password change
        if data.get('password'):
            password = data['password']
            if not isinstance(password, str) or not password.strip():
                return jsonify({'success': False, 'message': 'Invalid password provided'}), 400
            user.set_password(password)
            changes.append("password")
        
        try:
            db.session.commit()
            
            # Log changes if any were made
            if changes:
                changes_str = ", ".join(changes)
                log_system_event(f"Admin {current_user.name} modified user {user.name}: {changes_str}", event_type='audit', event_level='information')
            
            return jsonify({'success': True})
        except IntegrityError as e:
            db.session.rollback()
            log_system_event(f"Admin {current_user.name} failed to modify user {user.name}: Database integrity error", event_type='audit', event_level='error')
            return jsonify({'success': False, 'message': 'Email address already in use'}), 400
        except Exception as e:
            db.session.rollback()
            log_system_event(f"Admin {current_user.name} failed to modify user {user.name}: {str(e)}", event_type='audit', event_level='error')
            return jsonify({'success': False, 'message': 'Failed to update user'}), 500
    
    elif request.method == 'DELETE':
        # Enhanced admin protection
        if user_id == 1:
            return jsonify({'success': False, 'message': 'Cannot delete primary admin account'}), 403
        
        # Prevent deleting the last active admin
        valid, error = check_admin_protection(user_id)
        if not valid:
            return jsonify({'success': False, 'message': error}), 403
        
        # Store user info for logging before deletion
        user_info = f"{user.name} (email: {user.email}, role: {user.role})"
        
        try:
            db.session.delete(user)
            db.session.commit()
            log_system_event(f"Admin {current_user.name} deleted user: {user_info}", event_type='audit', event_level='warning')
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            log_system_event(f"Admin {current_user.name} failed to delete user {user_info}: {str(e)}", event_type='audit', event_level='error')
            return jsonify({'success': False, 'message': 'Failed to delete user'}), 500
