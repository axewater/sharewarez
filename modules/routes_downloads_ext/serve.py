import os
from flask import redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from modules import db
from modules.models import DownloadRequest
from sqlalchemy import select
from flask import abort
from modules.utils_security import is_safe_path, get_allowed_base_directories
from modules.utils_logging import log_system_event
from . import download_bp

# NOTE: This route is now handled by ASGI for async streaming
# This Flask route should not be reached as ASGI intercepts it first
@download_bp.route('/download_zip/<download_id>')
@login_required
def download_zip(download_id):
    # This route should not be reached as ASGI intercepts download routes
    log_system_event(f"Flask download route reached unexpectedly for ID: {download_id}", 
                    event_type='system', event_level='warning')
    return jsonify({"error": "Download route should be handled by ASGI"}), 500
