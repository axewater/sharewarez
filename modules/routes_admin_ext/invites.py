from flask import render_template, request, flash
from flask_login import login_required
from modules.utils_auth import admin_required
from modules.models import User, InviteToken
from modules import db
from . import admin2_bp

@admin2_bp.route('/admin/manage_invites', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_invites():

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        invites_number = int(request.form.get('invites_number'))

        user = User.query.filter_by(user_id=user_id).first()
        if user:
            user.invite_quota += invites_number
            db.session.commit()
            flash('Invites updated successfully.', 'success')
        else:
            flash('User not found.', 'error')

    users = User.query.all()
    # Calculate unused invites for each user
    user_unused_invites = {}
    for user in users:
        unused_count = InviteToken.query.filter_by(
            creator_user_id=user.user_id,
            used=False
        ).count()
        user_unused_invites[user.user_id] = unused_count

    return render_template('admin/admin_manage_invites.html', 
                         users=users, 
                         user_unused_invites=user_unused_invites)
