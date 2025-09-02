import os
from flask import render_template, redirect, url_for, flash, current_app
from flask_login import login_required
from modules.models import DownloadRequest, User
from sqlalchemy import select
from modules.utils_system_stats import format_bytes
from modules.utils_download import get_zip_storage_stats, delete_zip_file_safely
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

    zip_count, zip_size, total_size = get_zip_storage_stats()
    storage_stats = {
        'zip_count': zip_count,
        'total_size': format_bytes(total_size)
    }
    return render_template('admin/admin_manage_downloads.html', download_requests=download_requests, storage_stats=storage_stats)

@download_bp.route('/delete_download_request/<int:request_id>', methods=['POST'])
@login_required
@admin_required
def delete_download_request(request_id):
    """
    Delete a download request and its associated ZIP file via admin interface.
    """
    download_request = db.session.get(DownloadRequest, request_id)
    if not download_request:
        flash('Download request not found.', 'error')
        return redirect(url_for('download.manage_downloads'))
    
    # Handle ZIP file deletion using the centralized utility function
    if download_request.zip_file_path:
        zip_save_path = current_app.config.get('ZIP_SAVE_PATH')
        if zip_save_path:
            zip_deletion_success, zip_deletion_message = delete_zip_file_safely(
                download_request.zip_file_path, 
                zip_save_path
            )
            
            if zip_deletion_success:
                log_system_event('admin_download', zip_deletion_message, 'info')
                if 'not in the expected directory' in zip_deletion_message:
                    flash("ZIP file was not in expected directory. Only download request removed.", 'warning')
            else:
                log_system_event('admin_download', f'ZIP deletion failed: {zip_deletion_message}', 'warning')
                flash(f"Error deleting ZIP file: {zip_deletion_message}", 'error')
        else:
            log_system_event('admin_download', 'ZIP_SAVE_PATH not configured', 'warning')
            flash("ZIP save path not configured.", 'warning')
    
    # Delete the download request from database
    log_system_event('admin_download', f'Admin deleting download request {request_id}', 'info')
    db.session.delete(download_request)
    db.session.commit()
    
    flash('Download request deleted successfully.', 'success')
    return redirect(url_for('download.manage_downloads'))

@download_bp.route('/admin/clear-processing-downloads', methods=['POST'])
@login_required
@admin_required
def clear_processing_downloads():
    try:
        # Find all download requests with 'processing' status
        processing_downloads = db.session.execute(select(DownloadRequest).filter_by(status='processing')).scalars().all()
        
        # Update their status to 'failed'
        for download in processing_downloads:
            download.status = 'failed'
            # Note: DownloadRequest model doesn't currently have error_message field
        
        db.session.commit()
        flash('Successfully cleared all processing downloads.', 'success')
        
    except Exception as e:
        db.session.rollback()
        log_system_event('admin_download', f'Error clearing processing downloads: {str(e)}', 'error')
        flash('An error occurred while clearing processing downloads. Please try again.', 'error')
    
    return redirect(url_for('download.manage_downloads'))
