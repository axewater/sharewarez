from flask import render_template, redirect, url_for, flash
from flask_login import login_required
from modules.utils_auth import admin_required
from modules.models import ReleaseGroup
from modules import db
from modules.forms import ReleaseGroupForm
from . import admin2_bp

@admin2_bp.route('/admin/edit_filters', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_filters():
    form = ReleaseGroupForm()
    if form.validate_on_submit():
        new_group = ReleaseGroup(rlsgroup=form.rlsgroup.data, rlsgroupcs=form.rlsgroupcs.data)
        db.session.add(new_group)
        db.session.commit()
        flash('New release group filter added.')
        return redirect(url_for('admin2.edit_filters'))
    groups = ReleaseGroup.query.order_by(ReleaseGroup.rlsgroup.asc()).all()
    return render_template('admin/admin_manage_filters.html', form=form, groups=groups)

@admin2_bp.route('/delete_filter/<int:id>', methods=['GET'])
@login_required
@admin_required
def delete_filter(id):
    group_to_delete = ReleaseGroup.query.get_or_404(id)
    db.session.delete(group_to_delete)
    db.session.commit()
    flash('Release group filter removed.')
    return redirect(url_for('admin2.edit_filters'))
