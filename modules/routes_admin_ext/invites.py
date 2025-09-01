from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required
from modules.utils_auth import admin_required
from modules.models import User, InviteToken
from modules import db
from sqlalchemy import select, func, and_
import uuid
from . import admin2_bp

@admin2_bp.route('/admin/manage_invites', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_invites():

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        invites_number_str = request.form.get('invites_number')
        
        # Input validation for user_id
        if not user_id:
            flash('User ID is required.', 'error')
            return redirect(url_for('admin2.manage_invites'))
        
        # Validate UUID format
        try:
            uuid.UUID(user_id)
        except (ValueError, TypeError):
            flash('Invalid user ID format.', 'error')
            return redirect(url_for('admin2.manage_invites'))
        
        # Error handling for invites_number with proper validation
        try:
            invites_number = int(invites_number_str) if invites_number_str else 0
        except (ValueError, TypeError):
            flash('Invalid invite number provided. Please enter a valid number.', 'error')
            return redirect(url_for('admin2.manage_invites'))
        
        # Input validation for reasonable bounds
        if invites_number < -1000 or invites_number > 1000:
            flash('Invite number must be between -1000 and 1000.', 'error')
            return redirect(url_for('admin2.manage_invites'))

        # Better user lookup with proper error handling
        try:
            user = db.session.execute(select(User).filter_by(user_id=user_id)).scalars().first()
            if user:
                user.invite_quota += invites_number
                db.session.commit()
                flash(f'Invites updated successfully. User {user.name} now has {user.invite_quota} invite quota.', 'success')
            else:
                flash('User not found.', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating invites: {str(e)}', 'error')
            return redirect(url_for('admin2.manage_invites'))

    # Optimized database queries - fix N+1 problem with single JOIN query
    try:
        users = db.session.execute(select(User)).scalars().all()
        
        # Single query with LEFT JOIN to get unused invite counts for all users
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
        
        # Convert to dictionary for template use
        user_unused_invites = {row.user_id: row.unused_count for row in user_invite_counts}
        
    except Exception as e:
        flash(f'Error loading invite data: {str(e)}', 'error')
        users = []
        user_unused_invites = {}

    return render_template('admin/admin_manage_invites.html', 
                         users=users, 
                         user_unused_invites=user_unused_invites)
