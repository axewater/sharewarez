# /modules/routes_apis/library.py
from flask import jsonify, request, url_for
from flask_login import login_required
from modules import db
from modules.models import Library
from modules.utils_auth import admin_required
from . import apis_bp

@apis_bp.route('/get_libraries')
def get_libraries():
    # Direct query to the Library model
    libraries_query = Library.query.all()
    libraries = [
        {
            'uuid': lib.uuid,
            'name': lib.name,
            'image_url': lib.image_url if lib.image_url else url_for('static', filename='newstyle/default_library.jpg')
        } for lib in libraries_query
    ]
    print(f"Returning {len(libraries)} libraries.")
    return jsonify(libraries)

@apis_bp.route('/reorder_libraries', methods=['POST'])
@login_required
@admin_required
def reorder_libraries():
    try:
        new_order = request.json.get('order', [])
        for index, library_uuid in enumerate(new_order):
            library = Library.query.get(library_uuid)
            if library:
                library.display_order = index
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@apis_bp.route('/library/<string:library_uuid>', methods=['GET'])
@login_required
def get_library(library_uuid):
    """Return information about a specific library"""
    library = Library.query.filter_by(uuid=library_uuid).first()
    if not library:
        return jsonify({'error': 'Library not found'}), 404
        
    return jsonify({
        'uuid': library.uuid,
        'name': library.name,
        'platform': library.platform.name
    })
