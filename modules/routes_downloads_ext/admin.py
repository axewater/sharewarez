from flask import render_template, redirect, url_for, flash
from flask_login import login_required
from modules.models import DownloadRequest, User
from sqlalchemy import select
from modules.utils_auth import admin_required
from modules.utils_logging import log_system_event
from modules import db
from . import download_bp

@download_bp.route('/admin/manage-downloads', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_downloads():
    # Modified query to return full objects
    download_requests = db.session.execute(
        select(DownloadRequest, User.name.label('username'))
        .join(User, DownloadRequest.user_id == User.id)
    ).all()

    return render_template('admin/admin_manage_downloads.html', download_requests=download_requests)

@download_bp.route('/delete_download_request/<int:request_id>', methods=['POST'])
@login_required
@admin_required
def delete_download_request(request_id):
    """
    Delete a download request via admin interface.
    """
    download_request = db.session.get(DownloadRequest, request_id)
    if not download_request:
        flash('Download request not found.', 'error')
        return redirect(url_for('download.manage_downloads'))

    # Delete the download request from database
    log_system_event('admin_download', f'Admin deleting download request {request_id}', 'info')
    db.session.delete(download_request)
    db.session.commit()

    flash('Download request deleted.', 'success')
    return redirect(url_for('download.manage_downloads'))
