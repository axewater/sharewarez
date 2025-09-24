from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from modules.utils_auth import admin_required
from modules.models import SystemEvents, DiscoverySection, Game, Library, user_favorites
from modules import db
from modules.utils_logging import log_system_event
from sqlalchemy import select, and_, func
from datetime import datetime
from typing import Optional, Dict, Any
from . import admin2_bp

# Constants
DEFAULT_PER_PAGE = 50
MAX_PER_PAGE = 200
DATE_FORMAT = '%Y-%m-%d'


def validate_pagination_params(page: int, per_page: int) -> tuple[int, int]:
    """Validate and sanitize pagination parameters."""
    page = max(1, page)  # Ensure page is at least 1
    per_page = min(max(1, per_page), MAX_PER_PAGE)  # Clamp per_page between 1 and MAX_PER_PAGE
    return page, per_page


def parse_date_filter(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string and return datetime object or None if invalid."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, DATE_FORMAT)
    except ValueError:
        return None


def validate_json_request(data: Dict[str, Any], required_fields: list[str]) -> tuple[bool, Optional[str]]:
    """Validate JSON request data for required fields."""
    if data is None:
        return False, "No JSON data provided"
    
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    return True, None

@admin2_bp.route('/admin/system_logs')
@login_required
@admin_required
def system_logs() -> str:
    """
    Display system logs with filtering and pagination.
    
    Query parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 50, max: 200)
    - event_type: Filter by event type
    - event_level: Filter by event level
    - date_from: Filter events from date (YYYY-MM-DD format)
    - date_to: Filter events to date (YYYY-MM-DD format)
    """
    # Get and validate pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', DEFAULT_PER_PAGE, type=int)
    page, per_page = validate_pagination_params(page, per_page)
    
    # Get filter parameters
    event_type = request.args.get('event_type', '').strip()
    event_level = request.args.get('event_level', '').strip()
    date_from_str = request.args.get('date_from', '').strip()
    date_to_str = request.args.get('date_to', '').strip()
    
    # Parse date filters
    date_from = parse_date_filter(date_from_str)
    date_to = parse_date_filter(date_to_str)
    
    # Build query with eager loading for user relationship
    query = select(SystemEvents).options(db.joinedload(SystemEvents.user)).order_by(SystemEvents.timestamp.desc())
    
    # Apply filters if they exist
    filters = []
    
    if event_type:
        filters.append(SystemEvents.event_type == event_type)
    
    if event_level:
        filters.append(SystemEvents.event_level == event_level)
    
    if date_from:
        filters.append(SystemEvents.timestamp >= date_from)
    
    if date_to:
        # Add one day to include events from the entire end date
        date_to_end = date_to.replace(hour=23, minute=59, second=59)
        filters.append(SystemEvents.timestamp <= date_to_end)
    
    if filters:
        query = query.filter(and_(*filters))
    
    logs = db.paginate(query, page=page, per_page=per_page)
    return render_template('admin/admin_server_logs.html', logs=logs)

@admin2_bp.route('/admin/discovery_sections')
@login_required
@admin_required
def discovery_sections() -> str:
    """
    Display and manage discovery sections configuration.

    Returns a page where admins can view, reorder, and toggle visibility
    of discovery sections on the main discovery page.
    """
    sections = db.session.execute(select(DiscoverySection).order_by(DiscoverySection.display_order)).scalars().all()

    # Calculate item counts for each section
    section_counts = {}

    for section in sections:
        if section.identifier == 'libraries':
            count = db.session.execute(select(func.count(Library.uuid))).scalar()
        elif section.identifier == 'latest_games':
            count = db.session.execute(select(func.count(Game.id))).scalar()
        elif section.identifier == 'most_downloaded':
            count = db.session.execute(select(func.count(Game.id)).filter(Game.times_downloaded > 0)).scalar()
        elif section.identifier == 'highest_rated':
            count = db.session.execute(select(func.count(Game.id)).filter(Game.rating != None)).scalar()
        elif section.identifier == 'last_updated':
            count = db.session.execute(select(func.count(Game.id)).filter(Game.last_updated != None)).scalar()
        elif section.identifier == 'most_favorited':
            count = db.session.execute(
                select(func.count(func.distinct(Game.uuid)))
                .join(user_favorites, Game.uuid == user_favorites.c.game_uuid)
            ).scalar()
        else:
            count = 0

        section_counts[section.identifier] = count

    return render_template('admin/admin_discovery_sections.html', sections=sections, section_counts=section_counts)

@admin2_bp.route('/admin/api/discovery_sections/order', methods=['POST'])
@login_required
@admin_required
def update_section_order() -> tuple[Dict[str, Any], int]:
    """
    Update the display order of discovery sections.
    
    Expected JSON payload:
    {
        "sections": [
            {"id": 1, "order": 1},
            {"id": 2, "order": 2},
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        
        # Validate request data
        is_valid, error_msg = validate_json_request(data, ['sections'])
        if not is_valid:
            return jsonify({'success': False, 'error': error_msg}), 400
        
        if not isinstance(data['sections'], list):
            return jsonify({'success': False, 'error': 'sections must be an array'}), 400
        
        updated_sections = []
        for section_data in data['sections']:
            # Validate each section data
            if not isinstance(section_data, dict) or 'id' not in section_data or 'order' not in section_data:
                return jsonify({'success': False, 'error': 'Invalid section data format'}), 400
            
            try:
                section_id = int(section_data['id'])
                order = int(section_data['order'])
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': 'Section ID and order must be integers'}), 400
            
            if order < 0:
                return jsonify({'success': False, 'error': 'Display order must be non-negative'}), 400
            
            section = db.session.get(DiscoverySection, section_id)
            if not section:
                return jsonify({'success': False, 'error': f'Section with ID {section_id} not found'}), 404
            
            section.display_order = order
            updated_sections.append(section.name)
        
        db.session.commit()
        
        # Log the action for audit trail
        log_system_event(
            f"Updated display order for {len(updated_sections)} discovery sections: {', '.join(updated_sections)}",
            event_type='admin_action',
            event_level='information',
            audit_user=current_user.id
        )
        
        return jsonify({
            'success': True, 
            'message': f'Updated order for {len(updated_sections)} sections',
            'updated_sections': updated_sections
        }), 200
        
    except Exception as e:
        db.session.rollback()
        log_system_event(
            f"Failed to update discovery section order: {str(e)}",
            event_type='admin_action',
            event_level='error',
            audit_user=current_user.id
        )
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@admin2_bp.route('/admin/api/discovery_sections/visibility', methods=['POST'])
@login_required
@admin_required
def update_section_visibility() -> tuple[Dict[str, Any], int]:
    """
    Update the visibility status of a discovery section.
    
    Expected JSON payload:
    {
        "section_id": 1,
        "is_visible": true
    }
    """
    try:
        data = request.get_json()
        
        # Validate request data
        is_valid, error_msg = validate_json_request(data, ['section_id', 'is_visible'])
        if not is_valid:
            return jsonify({'success': False, 'error': error_msg}), 400
        
        # Validate section_id
        try:
            section_id = int(data['section_id'])
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'section_id must be an integer'}), 400
        
        # Validate is_visible
        if not isinstance(data['is_visible'], bool):
            return jsonify({'success': False, 'error': 'is_visible must be a boolean'}), 400
        
        section = db.session.get(DiscoverySection, section_id)
        if not section:
            return jsonify({'success': False, 'error': f'Section with ID {section_id} not found'}), 404
        
        old_visibility = section.is_visible
        section.is_visible = data['is_visible']
        
        db.session.commit()
        
        # Log the action for audit trail
        visibility_status = 'visible' if data['is_visible'] else 'hidden'
        log_system_event(
            f"Changed discovery section '{section.name}' visibility to {visibility_status}",
            event_type='admin_action',
            event_level='information',
            audit_user=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': f"Section '{section.name}' is now {'visible' if data['is_visible'] else 'hidden'}",
            'section_name': section.name,
            'old_visibility': old_visibility,
            'new_visibility': data['is_visible']
        }), 200
        
    except Exception as e:
        db.session.rollback()
        log_system_event(
            f"Failed to update discovery section visibility: {str(e)}",
            event_type='admin_action',
            event_level='error',
            audit_user=current_user.id
        )
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@admin2_bp.route('/admin/api/system_logs/clear', methods=['DELETE'])
@login_required
@admin_required
def clear_system_logs() -> tuple[Dict[str, Any], int]:
    """
    Clear all system logs from the database.
    
    This is a destructive action that cannot be undone.
    The action is logged after clearing the logs for audit purposes.
    """
    try:
        # Get count of logs before deletion for the response
        logs_count = db.session.execute(select(db.func.count(SystemEvents.id))).scalar()
        
        # Delete all system events
        db.session.execute(db.delete(SystemEvents))
        db.session.commit()
        
        # Log the action after clearing logs so it persists
        log_system_event(
            f"System logs cleared by admin user '{current_user.name}' (ID: {current_user.id}). {logs_count} logs were deleted.",
            event_type='admin_action',
            event_level='warning',
            audit_user=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': f'Successfully cleared {logs_count} system logs',
            'deleted_count': logs_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        log_system_event(
            f"Failed to clear system logs: {str(e)}",
            event_type='admin_action',
            event_level='error',
            audit_user=current_user.id
        )
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
