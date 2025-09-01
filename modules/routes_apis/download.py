# /modules/routes_apis/download.py
from typing import Tuple
from flask import jsonify, current_app, abort
from flask_login import login_required
from modules import db
from modules.utils_auth import admin_required
from modules.models import DownloadRequest
from modules.utils_download import delete_zip_file_safely
from modules.utils_logging import log_system_event
from . import apis_bp

@apis_bp.route('/delete_download/<int:request_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_download_request(request_id: int) -> Tuple[dict, int]:
    """
    Delete a download request and its associated ZIP file.
    
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
        
        zip_deletion_message = "No ZIP file to delete"
        zip_deletion_success = True
        
        # Handle ZIP file deletion if it exists
        if download_request.zip_file_path:
            zip_save_path = current_app.config.get('ZIP_SAVE_PATH')
            if not zip_save_path:
                log_system_event('download_api', 'ZIP_SAVE_PATH not configured', 'error')
                return jsonify({
                    'status': 'error',
                    'message': 'ZIP save path not configured'
                }), 500
                
            zip_deletion_success, zip_deletion_message = delete_zip_file_safely(
                download_request.zip_file_path, 
                zip_save_path
            )
            
            if not zip_deletion_success:
                log_system_event(
                    'download_api', 
                    f'ZIP file deletion failed for request {request_id}: {zip_deletion_message}', 
                    'warning'
                )
        
        # Delete the download request from database
        log_system_event(
            'download_api', 
            f'Deleting download request {request_id} for user {download_request.user_id}', 
            'info'
        )
        
        db.session.delete(download_request)
        db.session.commit()
        
        # Determine response message based on ZIP deletion result
        if zip_deletion_success:
            message = 'Download request deleted successfully'
            if 'not in the expected directory' in zip_deletion_message:
                message += '. ZIP file was not in expected directory.'
        else:
            message = f'Download request deleted, but ZIP file deletion failed: {zip_deletion_message}'
        
        log_system_event('download_api', f'Successfully deleted download request {request_id}', 'info')
        
        return jsonify({
            'status': 'success',
            'message': message
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
