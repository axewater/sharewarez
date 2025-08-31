# /modules/routes_apis/system.py
import os
from flask import jsonify, request, current_app, abort
from flask_login import login_required
from modules import db
from modules.models import AllowedFileType, IgnoredFileType
from modules.platform import Emulator, LibraryPlatform, platform_emulator_mapping
from modules.utils_auth import admin_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from . import apis_bp

@apis_bp.route('/file_types/<string:type_category>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@admin_required
def manage_file_types(type_category):
    if type_category not in ['allowed', 'ignored']:
        return jsonify({'error': 'Invalid type category'}), 400

    ModelClass = AllowedFileType if type_category == 'allowed' else IgnoredFileType

    if request.method == 'GET':
        types = db.session.execute(select(ModelClass).order_by(ModelClass.value.asc())).scalars().all()
        return jsonify([{'id': t.id, 'value': t.value} for t in types])

    elif request.method == 'POST':
        data = request.get_json()
        new_type = ModelClass(value=data['value'].lower())
        try:
            db.session.add(new_type)
            db.session.commit()
            return jsonify({'id': new_type.id, 'value': new_type.value})
        except IntegrityError:
            db.session.rollback()
            return jsonify({'error': 'Type already exists'}), 400

    elif request.method == 'PUT':
        data = request.get_json()
        file_type = db.session.get(ModelClass, data['id']) or abort(404)
        file_type.value = data['value'].lower()
        try:
            db.session.commit()
            return jsonify({'id': file_type.id, 'value': file_type.value})
        except IntegrityError:
            db.session.rollback()
            return jsonify({'error': 'Type already exists'}), 400

    elif request.method == 'DELETE':
        file_type = db.session.get(ModelClass, request.get_json()['id']) or abort(404)
        db.session.delete(file_type)
        db.session.commit()
        return jsonify({'success': True})
    
@apis_bp.route('/check_path_availability', methods=['GET'])
@login_required
def check_path_availability():
    full_disk_path = request.args.get('full_disk_path', '').strip()
    
    # Security: Validate the path is within allowed directories
    if not full_disk_path:
        return jsonify({'available': False, 'error': 'Path required'}), 400
    
    # Get allowed base directories from config
    allowed_bases = []
    if current_app.config.get('BASE_FOLDER_WINDOWS'):
        allowed_bases.append(current_app.config.get('BASE_FOLDER_WINDOWS'))
    if current_app.config.get('BASE_FOLDER_POSIX'):
        allowed_bases.append(current_app.config.get('BASE_FOLDER_POSIX'))
    if current_app.config.get('DATA_FOLDER_WAREZ'):
        allowed_bases.append(current_app.config.get('DATA_FOLDER_WAREZ'))
    
    # Resolve the absolute path and check it's within allowed directories
    try:
        abs_path = os.path.abspath(full_disk_path)
        path_allowed = any(abs_path.startswith(os.path.abspath(base)) for base in allowed_bases if base)
        
        if not path_allowed:
            return jsonify({'available': False, 'error': 'Access denied'}), 403
        
        is_available = os.path.exists(abs_path)
        return jsonify({'available': is_available})
    except (OSError, ValueError):
        return jsonify({'available': False, 'error': 'Invalid path'}), 400

@apis_bp.route('/emulators', methods=['GET'])
@apis_bp.route('/emulators/<platform>', methods=['GET'])
@login_required
def get_emulators(platform=None):
    """Return emulators for a specific platform or all emulators if no platform specified"""
    try:
        if platform:
            platform_enum = LibraryPlatform[platform]
            emulators = [e.value for e in platform_emulator_mapping.get(platform_enum, [])]
        else:
            emulators = [e.value for e in Emulator]
    except KeyError:
        return jsonify({'error': f'Invalid platform: {platform}'}), 400
        
    return jsonify(emulators)
