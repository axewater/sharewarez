from flask import render_template, request, jsonify
from flask_login import login_required
from modules.utils_auth import admin_required
from modules.models import SystemEvents, DiscoverySection
from modules import db
from sqlalchemy import select
from . import admin2_bp

@admin2_bp.route('/admin/system_logs')
@login_required
@admin_required
def system_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Get filter parameters
    event_type = request.args.get('event_type')
    event_level = request.args.get('event_level')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = select(SystemEvents).options(db.joinedload(SystemEvents.user)).order_by(SystemEvents.timestamp.desc())
    
    # Apply filters if they exist
    if event_type:
        query = query.filter(SystemEvents.event_type == event_type)
    if event_level:
        query = query.filter(SystemEvents.event_level == event_level)
    
    logs = db.paginate(query, page=page, per_page=per_page)
    return render_template('admin/admin_server_logs.html', logs=logs)

@admin2_bp.route('/admin/discovery_sections')
@login_required
@admin_required
def discovery_sections():
    sections = db.session.execute(select(DiscoverySection).order_by(DiscoverySection.display_order)).scalars().all()
    return render_template('admin/admin_discovery_sections.html', sections=sections)

@admin2_bp.route('/admin/api/discovery_sections/order', methods=['POST'])
@login_required
@admin_required
def update_section_order():
    try:
        data = request.json
        for section_data in data['sections']:
            section = db.session.get(DiscoverySection, section_data['id'])
            if section:
                section.display_order = section_data['order']
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@admin2_bp.route('/admin/api/discovery_sections/visibility', methods=['POST'])
@login_required
@admin_required
def update_section_visibility():
    try:
        data = request.json
        section = db.session.get(DiscoverySection, data['section_id'])
        if section:
            section.is_visible = data['is_visible']
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Section not found'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})
