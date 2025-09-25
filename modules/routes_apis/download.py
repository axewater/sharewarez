# /modules/routes_apis/download.py
from typing import Tuple
from flask import jsonify
from flask_login import login_required
from modules import db
from modules.utils_auth import admin_required
from modules.models import DownloadRequest
from modules.utils_logging import log_system_event
from . import apis_bp

@apis_bp.route('/delete_download/<int:request_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_download_request(request_id: int) -> Tuple[dict, int]:
    """
    Delete a download request.

    Args:
        request_id: The ID of the download request to delete

    Returns:
        JSON response with status and message
    """
    # Validate request_id is positive
    if request_id <= 0:
        log_system_event('download_api', f'Invalid request ID: {request_id}', 'warning')
        return jsonify({
            'status': 'error',
            'message': 'Invalid request ID'
        }), 400
        
    try:
        download_request = db.session.get(DownloadRequest, request_id)
        if not download_request:
            return jsonify({
                'status': 'error',
                'message': 'Download request not found'
            }), 404

        # Delete the download request from database
        log_system_event(
            'download_api',
            f'Deleting download request {request_id} for user {download_request.user_id}',
            'info'
        )

        db.session.delete(download_request)
        db.session.commit()

        log_system_event('download_api', f'Successfully deleted download request {request_id}', 'info')

        return jsonify({
            'status': 'success',
            'message': 'Download request deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        log_system_event(
            'download_api', 
            f'Error deleting download request {request_id}: {str(e)}', 
            'error'
        )
        return jsonify({
            'status': 'error',
            'message': f'Error deleting download request: {str(e)}'
        }), 500
