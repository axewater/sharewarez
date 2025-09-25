from flask import render_template, redirect, url_for, flash, abort
from flask_login import login_required
from modules.utils_auth import admin_required
from modules.models import ReleaseGroup
from modules import db
from sqlalchemy import select
from modules.forms import ReleaseGroupForm
from . import admin2_bp

@admin2_bp.route('/admin/edit_filters', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_filters():
    form = ReleaseGroupForm()
    if form.validate_on_submit():
        new_group = ReleaseGroup(filter_pattern=form.filter_pattern.data, case_sensitive=form.case_sensitive.data)
        db.session.add(new_group)
        db.session.commit()
        flash('New scanning filter added.')
        return redirect(url_for('admin2.edit_filters'))
    scanning_filters = db.session.execute(select(ReleaseGroup).order_by(ReleaseGroup.filter_pattern.asc())).scalars().all()
    return render_template('admin/admin_manage_filters.html', form=form, scanning_filters=scanning_filters)

@admin2_bp.route('/delete_filter/<int:id>', methods=['GET'])
@login_required
@admin_required
def delete_filter(id):
    group_to_delete = db.session.get(ReleaseGroup, id) or abort(404)
    db.session.delete(group_to_delete)
    db.session.commit()
    flash('Scanning filter removed.')
    return redirect(url_for('admin2.edit_filters'))
