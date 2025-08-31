import os
from flask import render_template, redirect, url_for, flash, current_app
from flask_login import login_required
from modules.models import DownloadRequest, User
from sqlalchemy import select
from modules.utils_system_stats import format_bytes
from modules.utils_download import get_zip_storage_stats
from modules.utils_auth import admin_required
from modules import db
from . import download_bp

@download_bp.route('/admin/manage-downloads', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_downloads():
    print("Route: /admin/manage-downloads")    
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
    download_request = db.session.get(DownloadRequest, request_id)
    if not download_request:
        flash('Download request not found.', 'error')
        return redirect(url_for('download.manage_downloads'))
    
    if download_request.zip_file_path and os.path.exists(download_request.zip_file_path):
        if download_request.zip_file_path.startswith(current_app.config['ZIP_SAVE_PATH']):
            try:
                os.remove(download_request.zip_file_path)
                print(f"Deleted ZIP file: {download_request.zip_file_path}")
            except Exception as e:
                print(f"Error deleting ZIP file: {e}")
                flash(f"Error deleting ZIP file: {e}", 'error')
        else:
            print(f"ZIP file is not in the expected directory: {download_request.zip_file_path}")
            flash("ZIP file is not in the expected directory. Only the download request will be removed.", 'warning')
    
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
            download.error_message = 'Cleared by administrator'
        
        db.session.commit()
        flash('Successfully cleared all processing downloads.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing processing downloads: {str(e)}', 'error')
    
    return redirect(url_for('download.manage_downloads'))
