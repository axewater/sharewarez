import os
from flask import render_template, redirect, url_for, flash, jsonify, current_app, abort
from flask_login import login_required, current_user
from modules.forms import CsrfProtectForm
from modules.models import DownloadRequest
from sqlalchemy import select
from modules.utils_functions import format_size
from modules.utils_security import is_safe_path
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
    
    zip_save_path = current_app.config.get('ZIP_SAVE_PATH')
    
    # Allow deletion regardless of status
    if download_request.zip_file_path and os.path.exists(download_request.zip_file_path):
        # Only delete the file if it's a generated zip file in our ZIP_SAVE_PATH
        try:
            if zip_save_path:
                # Use secure path validation
                is_safe, error_msg = is_safe_path(download_request.zip_file_path, [zip_save_path])
                
                if is_safe:
                    os.remove(download_request.zip_file_path)
                    log_system_event(f"User {current_user.id} successfully deleted zip file: {download_request.zip_file_path}", 
                                   event_type='audit', event_level='information')
                    flash('Zipped download deleted successfully.', 'success')
                else:
                    log_system_event(f"Path traversal attempt blocked: user {current_user.id} tried to delete {download_request.zip_file_path} - {error_msg}", 
                                   event_type='security', event_level='warning')
                    flash('Download request removed. Original file preserved.', 'info')
            else:
                # ZIP_SAVE_PATH not configured, just remove the download request
                flash('Download request removed. Original file preserved.', 'info')
        except Exception as e:
            db.session.rollback()
            log_system_event(f"Error deleting download file for user {current_user.id}: {str(e)}", 
                           event_type='error', event_level='error')
            flash(f'An error occurred while deleting the file: {e}', 'danger')
            return redirect(url_for('download.downloads'))
    else:
        flash('No file found to delete, only the download request was removed.', 'info')
    
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
