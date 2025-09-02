# /modules/routes_apis/system.py
import os
import re
from pathlib import Path
from flask import jsonify, request, current_app, abort
from flask_login import login_required
from modules import db
from modules.models import AllowedFileType, IgnoredFileType
from modules.platform import Emulator, LibraryPlatform, platform_emulator_mapping
from modules.utils_auth import admin_required
from modules.utils_security import is_safe_path, get_allowed_base_directories
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from . import apis_bp


def validate_file_type_value(value):
    """Validate and sanitize file type values to prevent injection attacks."""
    if not value or not isinstance(value, str):
        return None
    
    # Remove any potentially dangerous characters and normalize
    value = str(value).strip().lower()
    
    # File extensions should only contain alphanumeric characters, dots, and hyphens
    if not re.match(r'^[a-z0-9.-]+$', value):
        return None
    
    # Ensure it starts with a dot for file extensions
    if not value.startswith('.'):
        value = '.' + value
    
    # Prevent excessively long values
    if len(value) > 10:
        return None
    
    return value




def validate_json_input(required_fields=None):
    """Validate JSON input and check for required fields."""
    if not request.is_json:
        return None, "Request must be JSON"
    
    try:
        data = request.get_json()
        if data is None:
            return None, "Invalid JSON format"
        
        if required_fields:
            for field in required_fields:
                if field not in data:
                    return None, f"Missing required field: {field}"
        
        return data, None
    
    except Exception as e:
        current_app.logger.warning(f"JSON validation error: {e}")
        return None, "Invalid JSON format"


@apis_bp.route('/file_types/<string:type_category>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@admin_required
def manage_file_types(type_category):
    # Validate type category
    if type_category not in ['allowed', 'ignored']:
        return jsonify({'error': 'Invalid type category'}), 400

    ModelClass = AllowedFileType if type_category == 'allowed' else IgnoredFileType

    try:
        if request.method == 'GET':
            types = db.session.execute(select(ModelClass).order_by(ModelClass.value.asc())).scalars().all()
            return jsonify([{'id': t.id, 'value': t.value} for t in types])

        elif request.method == 'POST':
            data, error = validate_json_input(['value'])
            if error:
                return jsonify({'error': error}), 400
            
            # Validate and sanitize the file type value
            sanitized_value = validate_file_type_value(data['value'])
            if not sanitized_value:
                return jsonify({'error': 'Invalid file type format'}), 400
            
            new_type = ModelClass(value=sanitized_value)
            try:
                db.session.add(new_type)
                db.session.commit()
                return jsonify({'id': new_type.id, 'value': new_type.value}), 201
            except IntegrityError:
                db.session.rollback()
                return jsonify({'error': 'File type already exists'}), 409

        elif request.method == 'PUT':
            data, error = validate_json_input(['id', 'value'])
            if error:
                return jsonify({'error': error}), 400
            
            # Validate ID is numeric
            try:
                file_type_id = int(data['id'])
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid ID format'}), 400
            
            # Validate and sanitize the file type value
            sanitized_value = validate_file_type_value(data['value'])
            if not sanitized_value:
                return jsonify({'error': 'Invalid file type format'}), 400
            
            file_type = db.session.get(ModelClass, file_type_id)
            if not file_type:
                return jsonify({'error': 'File type not found'}), 404
                
            file_type.value = sanitized_value
            try:
                db.session.commit()
                return jsonify({'id': file_type.id, 'value': file_type.value})
            except IntegrityError:
                db.session.rollback()
                return jsonify({'error': 'File type already exists'}), 409

        elif request.method == 'DELETE':
            data, error = validate_json_input(['id'])
            if error:
                return jsonify({'error': error}), 400
            
            # Validate ID is numeric
            try:
                file_type_id = int(data['id'])
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid ID format'}), 400
            
            file_type = db.session.get(ModelClass, file_type_id)
            if not file_type:
                return jsonify({'error': 'File type not found'}), 404
                
            db.session.delete(file_type)
            db.session.commit()
            return jsonify({'success': True})
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error managing file types: {e}")
        return jsonify({'error': 'An error occurred while processing your request'}), 500
    
@apis_bp.route('/check_path_availability', methods=['GET'])
@login_required
def check_path_availability():
    """Check if a file path exists, with security validation to prevent path traversal."""
    full_disk_path = request.args.get('full_disk_path', '').strip()
    
    if not full_disk_path:
        return jsonify({'available': False, 'error': 'Path parameter required'}), 400
    
    # Get allowed base directories from config
    allowed_bases = get_allowed_base_directories(current_app)
    if not allowed_bases:
        current_app.logger.error("No allowed base directories configured")
        return jsonify({'available': False, 'error': 'Service configuration error'}), 500
    
    # Use secure path validation
    is_safe, error_message = is_safe_path(full_disk_path, allowed_bases)
    if not is_safe:
        return jsonify({'available': False, 'error': error_message}), 403
    
    try:
        # Only check existence if path is validated as safe
        path_obj = Path(full_disk_path).resolve()
        is_available = path_obj.exists()
        
        # Don't reveal detailed filesystem information - just return boolean
        return jsonify({'available': is_available})
        
    except (OSError, ValueError) as e:
        current_app.logger.warning(f"Path existence check failed for validated path: {e}")
        return jsonify({'available': False, 'error': 'Unable to check path'}), 500

@apis_bp.route('/emulators', methods=['GET'])
@apis_bp.route('/emulators/<platform>', methods=['GET'])
@login_required
def get_emulators(platform=None):
    """Return emulators for a specific platform or all emulators if no platform specified."""
    try:
        if platform:
            # Validate platform parameter to prevent enumeration attacks
            if not isinstance(platform, str) or len(platform) > 50:
                return jsonify({'error': 'Invalid platform parameter'}), 400
            
            try:
                platform_enum = LibraryPlatform[platform]
                emulators = [e.value for e in platform_emulator_mapping.get(platform_enum, [])]
            except KeyError:
                # Don't reveal valid platform names in error message
                return jsonify({'error': 'Platform not supported'}), 404
        else:
            emulators = [e.value for e in Emulator]
            
        return jsonify({'emulators': emulators})
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving emulators: {e}")
        return jsonify({'error': 'Unable to retrieve emulators'}), 500
