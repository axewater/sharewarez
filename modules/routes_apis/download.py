# /modules/routes_apis/download.py
import os
from flask import jsonify, current_app
from flask_login import login_required
from modules import db
from modules.utils_auth import admin_required
from modules.models import DownloadRequest
from . import apis_bp

@apis_bp.route('/delete_download/<int:request_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_download_request(request_id):
    try:
        download_request = DownloadRequest.query.get_or_404(request_id)
        
        # Check if zip file exists and is in the expected directory
        if download_request.zip_file_path and os.path.exists(download_request.zip_file_path):
            if download_request.zip_file_path.startswith(current_app.config['ZIP_SAVE_PATH']):
                try:
                    os.remove(download_request.zip_file_path)
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'message': f'Error deleting ZIP file: {str(e)}'
                    }), 500
            else:
                print(f"Deleting download request: {download_request}")
                db.session.delete(download_request)
                db.session.commit()
                return jsonify({
                    'status': 'success',
                    'message': 'Download is not linked to a generated ZIP file. Only the download request has been removed.'
                }), 200
        print(f"Deleting download request: {download_request}")
        db.session.delete(download_request)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Download request deleted successfully'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error deleting download request: {str(e)}'
        }), 500
