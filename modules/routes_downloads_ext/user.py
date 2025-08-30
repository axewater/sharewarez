import os
from flask import render_template, redirect, url_for, flash, jsonify, current_app, abort
from flask_login import login_required, current_user
from modules.forms import CsrfProtectForm
from modules.models import DownloadRequest
from sqlalchemy import select
from modules.utils_functions import format_size
from . import download_bp
from modules import db

@download_bp.route('/downloads')
@login_required
def downloads():
    user_id = current_user.id
    print(f"Route: /downloads user_id: {user_id}")
    download_requests = db.session.execute(select(DownloadRequest).filter_by(user_id=user_id)).scalars().all()
    for download_request in download_requests:
        download_request.formatted_size = format_size(download_request.download_size)
    form = CsrfProtectForm()
    return render_template('games/manage_downloads.html', download_requests=download_requests, form=form)

@download_bp.route('/delete_download/<int:download_id>', methods=['POST'])
@login_required
def delete_download(download_id):
    download_request = db.session.execute(select(DownloadRequest).filter_by(id=download_id, user_id=current_user.id)).scalars().first() or abort(404)
    zip_save_path = current_app.config['ZIP_SAVE_PATH']
    # Allow deletion regardless of status
    if download_request.zip_file_path and os.path.exists(download_request.zip_file_path):
        # Only delete the file if it's a generated zip file in our ZIP_SAVE_PATH
        try:
            file_path = os.path.abspath(download_request.zip_file_path)
            zip_save_path = os.path.abspath(zip_save_path)
            
            if file_path.startswith(zip_save_path):
                os.remove(file_path)
                flash('Zipped download deleted successfully.', 'success')
            else:
                # For direct file downloads, just remove the download request
                flash('Download request removed. Original file preserved.', 'info')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while deleting the file: {e}', 'danger')
            return redirect(url_for('download.downloads'))
        else:
            flash('Only the download request was deleted, the original game file was not removed.', 'info')
    else:
        flash('No file found to delete, only the download request was removed.', 'info')
    db.session.delete(download_request)
    db.session.commit()

    return redirect(url_for('download.downloads'))

@download_bp.route('/check_download_status/<download_id>')
@login_required
def check_download_status(download_id):
    download_request = db.session.execute(select(DownloadRequest).filter_by(id=download_id, user_id=current_user.id)).scalars().first()
    
    if download_request:
        return jsonify({
            'status': download_request.status,
            'downloadId': download_request.id,
            'found': True
        })
    
    return jsonify({
        'status': 'not_found',
        'downloadId': download_id,
        'found': False
    }), 200
