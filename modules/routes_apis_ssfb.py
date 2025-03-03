from flask import Blueprint, jsonify, request, current_app
import os, sys, re
from flask_login import login_required, current_user
from modules.utils_auth import admin_required

ssfb_bp = Blueprint('ssfb', __name__)

@ssfb_bp.route('/api/browse_folders_ss')
@login_required
@admin_required
def browse_folders_ss():
    # Function to securely validate and normalize path
    def sanitize_path(path):
        # First, normalize the path to handle different formats
        normalized_path = os.path.normpath(path)
        
        # Check for path traversal attempts
        if '..' in normalized_path.split(os.sep):
            log_message(f"Path traversal attempt detected: {path}")
            return ''
        
        # Remove any leading slashes or backslashes
        while normalized_path.startswith('/') or normalized_path.startswith('\\'):
            normalized_path = normalized_path[1:]
           
        log_message(f"Sanitized path: {normalized_path}")
        return normalized_path

    # Log function for debugging
    def log_message(message):
        print(f"SS folder browser: {message}", file=sys.stderr)
        
    # Function to ensure path stays within base directory
    def ensure_base_directory(path, base_dir):
        # If path is empty or just '/', return the base directory
        if not path or path == '/':
            return ''
            
        # Create the full path and resolve any symbolic links
        full_path = os.path.realpath(os.path.join(base_dir, path))
        # Ensure the path is within the base directory
        return '' if not full_path.startswith(base_dir) else path
        
    # Function to safely get file/directory info
    def safe_get_file_info(path, item):
        item_path = os.path.join(path, item)
        return {'exists': os.path.exists(item_path), 'path': item_path}

    # Select base by operating system
    base_directory = current_app.config.get('BASE_FOLDER_WINDOWS') if os.name == 'nt' else current_app.config.get('BASE_FOLDER_POSIX')
    print(f'SS folder browser: Base directory: {base_directory}', file=sys.stderr)
    # Attempt to get 'path' from request arguments; default to an empty string which signifies the base directory
    request_path = request.args.get('path', '')
    print(f'SS folder browser: Requested path: {request_path}', file=sys.stderr)
    
    # Sanitize the requested path
    request_path = sanitize_path(request_path)
    if not request_path:  # If sanitization failed, return access denied
        return jsonify({'error': 'Access denied - invalid path'}), 403
    # Ensure the path stays within base directory
    request_path = ensure_base_directory(request_path, base_directory)
    
    if not request_path:
        print(f'SS folder browser: Using base directory: {base_directory}', file=sys.stderr)
        request_path = ''
        folder_path = base_directory
    else:
        # Safely construct the folder path to prevent directory traversal vulnerabilities
        folder_path = os.path.realpath(os.path.join(base_directory, request_path))
        print(f'SS folder browser: Folder path: {folder_path}', file=sys.stderr)
        # Prevent directory traversal outside the base directory
        if not folder_path.startswith(base_directory):
            print(f'SS folder browser: Access denied: {folder_path} outside of base directory: {base_directory}', file=sys.stderr)
            return jsonify({'error': 'Access denied'}), 403

    if os.path.isdir(folder_path):
        try:
            # Get directory listing
            dir_items = sorted(os.listdir(folder_path))
            contents = []
            skipped_items = 0
            
            # Process each item with error handling
            for item in dir_items:
                try:
                    item_path = os.path.join(folder_path, item)
                    is_dir = os.path.isdir(item_path)
                    
                    # For files, get size safely
                    size = None
                    if not is_dir:
                        try:
                            size = os.path.getsize(item_path)
                        except (FileNotFoundError, PermissionError, OSError) as e:
                            log_message(f"Error getting size for {item_path}: {str(e)}")
                    
                    contents.append({
                        'name': item,
                        'isDir': is_dir,
                        'ext': os.path.splitext(item)[1][1:].lower() if not is_dir else None,
                        'size': size
                    })
                except (FileNotFoundError, PermissionError, OSError) as e:
                    log_message(f"Error processing item {item}: {str(e)}")
                    skipped_items += 1
            
            # Return the successfully processed items
            response_data = {
                'items': sorted(contents, key=lambda x: (not x['isDir'], x['name'].lower())),
                'path': request_path,
                'hasErrors': skipped_items > 0,
                'skippedItems': skipped_items
            }
            return jsonify(response_data)
        except (PermissionError, OSError) as e:
            log_message(f"Error accessing directory {folder_path}: {str(e)}")
            return jsonify({'error': f'Error accessing directory: {str(e)}'}), 500
    else:
        return jsonify({'error': 'SS folder browser: Folder not found'}), 404
