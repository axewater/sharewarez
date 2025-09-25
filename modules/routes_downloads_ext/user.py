from flask import render_template, redirect, url_for, flash, jsonify, current_app, abort
from flask_login import login_required, current_user
from modules.forms import CsrfProtectForm
from modules.models import DownloadRequest
from sqlalchemy import select
from modules.utils_functions import format_size
from modules.utils_logging import log_system_event
from . import download_bp
from modules import db

@download_bp.route('/downloads')
@login_required
def downloads():
    user_id = current_user.id
    download_requests = db.session.execute(select(DownloadRequest).filter_by(user_id=user_id)).scalars().all()
    for download_request in download_requests:
        download_request.formatted_size = format_size(download_request.download_size)
    form = CsrfProtectForm()
    return render_template('games/manage_downloads.html', download_requests=download_requests, form=form)

@download_bp.route('/delete_download/<int:download_id>', methods=['POST'])
@login_required
def delete_download(download_id):
    # Validate download_id parameter
    try:
        download_id = int(download_id)
    except (ValueError, TypeError):
        log_system_event(f"Invalid download_id parameter: {download_id}", 
                        event_type='security', event_level='warning')
        abort(400)
    
    download_request = db.session.execute(select(DownloadRequest).filter_by(id=download_id, user_id=current_user.id)).scalars().first()
    
    if not download_request:
        log_system_event(f"Unauthorized download deletion attempt: user {current_user.id} tried to delete download {download_id}", 
                        event_type='security', event_level='warning')
        abort(404)
    
    # Delete download request (no physical files to clean up with new streaming approach)
    flash('Download request removed.', 'info')
    
    db.session.delete(download_request)
    db.session.commit()
    
    log_system_event(f"User {current_user.id} deleted download request {download_id}", 
                   event_type='audit', event_level='information')

    return redirect(url_for('download.downloads'))

@download_bp.route('/check_download_status/<download_id>')
@login_required
def check_download_status(download_id):
    # Validate download_id parameter
    try:
        download_id = int(download_id)
    except (ValueError, TypeError):
        log_system_event(f"Invalid download_id parameter in status check: {download_id}", 
                        event_type='security', event_level='warning')
        return jsonify({
            'status': 'invalid',
            'downloadId': download_id,
            'found': False,
            'error': 'Invalid download ID'
        }), 400
    
    download_request = db.session.execute(select(DownloadRequest).filter_by(id=download_id, user_id=current_user.id)).scalars().first()
    
    if download_request:
        return jsonify({
            'status': download_request.status,
            'downloadId': download_request.id,
            'found': True
        })
    
    # Log unauthorized access attempt
    log_system_event(f"Unauthorized download status check: user {current_user.id} tried to check download {download_id}", 
                    event_type='security', event_level='warning')
    
    return jsonify({
        'status': 'not_found',
        'downloadId': download_id,
        'found': False
    }), 404
