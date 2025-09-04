import os
from flask import redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from modules import db
from modules.models import DownloadRequest
from sqlalchemy import select
from flask import abort
from modules.utils_security import is_safe_path, get_allowed_base_directories
from modules.utils_logging import log_system_event
from modules.utils_streaming import create_streaming_response
from . import download_bp

@download_bp.route('/download_zip/<download_id>')
@login_required
def download_zip(download_id):
    log_system_event(f"Download attempt for ID: {download_id}", event_type='download', event_level='information')
    
    download_request = db.session.execute(select(DownloadRequest).filter_by(id=download_id, user_id=current_user.id)).scalars().first() or abort(404)
    
    if download_request.status != 'available':
        log_system_event(f"Download blocked - not ready: {download_id}", event_type='download', event_level='warning')
        flash("The requested download is not ready yet.")
        return redirect(url_for('library.library'))

    # Get the file path (stored as absolute path in database)
    file_path = download_request.zip_file_path
    
    # Security validation: Ensure file is within allowed directories
    zip_save_path = current_app.config.get('ZIP_SAVE_PATH')
    if not zip_save_path:
        log_system_event("ZIP_SAVE_PATH not configured", event_type='system', event_level='error')
        flash("System configuration error.", "error")
        return redirect(url_for('library.library'))
    
    # Validate file path is safe (within ZIP_SAVE_PATH or other allowed directories)
    allowed_bases = [zip_save_path]
    is_safe, error_message = is_safe_path(file_path, allowed_bases)
    if not is_safe:
        log_system_event(f"Security violation - path outside allowed directories: {file_path[:100]}", 
                        event_type='security', event_level='warning')
        flash("Access denied.", "error")
        return redirect(url_for('library.library'))
    
    if not os.path.exists(file_path):
        log_system_event(f"Download failed - file not found: {file_path[:100]}", event_type='download', event_level='error')
        flash("Error: File does not exist.")
        return redirect(url_for('library.library'))

    try:
        filename = os.path.basename(file_path)
        
        log_system_event(f"File downloaded: {filename}", event_type='download', event_level='information')
        
        # Stream the file using chunked response
        return create_streaming_response(file_path, filename)
        
    except Exception as e:
        log_system_event(f"Download error for {download_id}: {str(e)}", event_type='download', event_level='error')
        flash("An error occurred while trying to serve the file.")
        return redirect(url_for('library.library'))
