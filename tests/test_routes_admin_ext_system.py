import pytest
from flask import url_for
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from modules.models import User, SystemEvents, DiscoverySection
from modules import db
from modules.routes_admin_ext.system import (
    validate_pagination_params, 
    parse_date_filter, 
    validate_json_request,
    DEFAULT_PER_PAGE,
    MAX_PER_PAGE,
    DATE_FORMAT
)
from uuid import uuid4
import json


@pytest.fixture
def admin_user(db_session):
    """Create an admin user."""
    admin_uuid = str(uuid4())
    unique_id = str(uuid4())[:8]
    admin = User(
        user_id=admin_uuid,
        name=f'TestAdmin_{unique_id}',
        email=f'admin_{unique_id}@test.com',
        role='admin',
        is_email_verified=True
    )
    admin.set_password('testpass123')
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture
def regular_user(db_session):
    """Create a regular user."""
    user_uuid = str(uuid4())
    unique_id = str(uuid4())[:8]
    user = User(
        user_id=user_uuid,
        name=f'TestUser_{unique_id}',
        email=f'user_{unique_id}@test.com',
        role='user',
        is_email_verified=True
    )
    user.set_password('testpass123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_system_events(db_session, admin_user):
    """Create sample system events for testing."""
    # Clear existing events
    db_session.query(SystemEvents).delete()
    db_session.commit()
    
    base_time = datetime.now()
    events = []
    
    # Create events with different types, levels, and dates
    event_data = [
        ('log', 'information', 'System startup completed', base_time - timedelta(days=2)),
        ('admin_action', 'information', 'User created new game', base_time - timedelta(days=1)),
        ('error', 'error', 'Database connection failed', base_time - timedelta(hours=12)),
        ('scan', 'information', 'Library scan completed', base_time - timedelta(hours=6)),
        ('admin_action', 'warning', 'Invalid login attempt', base_time - timedelta(hours=1)),
    ]
    
    for event_type, event_level, event_text, timestamp in event_data:
        event = SystemEvents(
            event_type=event_type,
            event_level=event_level,
            event_text=event_text,
            timestamp=timestamp,
            audit_user=admin_user.id if event_type == 'admin_action' else None
        )
        events.append(event)
        db_session.add(event)
    
    db_session.commit()
    return events


@pytest.fixture
def sample_discovery_sections(db_session):
    """Create sample discovery sections for testing."""
    # Clear existing sections
    db_session.query(DiscoverySection).delete()
    db_session.commit()
    
    sections = []
    section_data = [
        ('Popular Games', 'popular_games', True, 1),
        ('New Releases', 'new_releases', True, 2),
        ('Top Rated', 'top_rated', False, 3),
        ('Recently Added', 'recently_added', True, 4),
    ]
    
    for name, identifier, is_visible, display_order in section_data:
        section = DiscoverySection(
            name=name,
            identifier=identifier,
            is_visible=is_visible,
            display_order=display_order
        )
        sections.append(section)
        db_session.add(section)
    
    db_session.commit()
    return sections


class TestHelperFunctions:
    """Test helper functions in the system module."""
    
    def test_validate_pagination_params_normal_values(self):
        """Test pagination validation with normal values."""
        page, per_page = validate_pagination_params(5, 25)
        assert page == 5
        assert per_page == 25
    
    def test_validate_pagination_params_negative_page(self):
        """Test pagination validation with negative page."""
        page, per_page = validate_pagination_params(-1, 25)
        assert page == 1
        assert per_page == 25
    
    def test_validate_pagination_params_zero_page(self):
        """Test pagination validation with zero page."""
        page, per_page = validate_pagination_params(0, 25)
        assert page == 1
        assert per_page == 25
    
    def test_validate_pagination_params_excessive_per_page(self):
        """Test pagination validation with excessive per_page."""
        page, per_page = validate_pagination_params(1, 500)
        assert page == 1
        assert per_page == MAX_PER_PAGE
    
    def test_validate_pagination_params_zero_per_page(self):
        """Test pagination validation with zero per_page."""
        page, per_page = validate_pagination_params(1, 0)
        assert page == 1
        assert per_page == 1
    
    def test_parse_date_filter_valid_date(self):
        """Test date parsing with valid date."""
        result = parse_date_filter('2024-01-15')
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
    
    def test_parse_date_filter_invalid_date(self):
        """Test date parsing with invalid date."""
        result = parse_date_filter('invalid-date')
        assert result is None
    
    def test_parse_date_filter_empty_string(self):
        """Test date parsing with empty string."""
        result = parse_date_filter('')
        assert result is None
    
    def test_parse_date_filter_none(self):
        """Test date parsing with None."""
        result = parse_date_filter(None)
        assert result is None
    
    def test_parse_date_filter_wrong_format(self):
        """Test date parsing with wrong format."""
        result = parse_date_filter('15-01-2024')
        assert result is None
    
    def test_validate_json_request_valid_data(self):
        """Test JSON validation with valid data."""
        data = {'section_id': 1, 'is_visible': True}
        is_valid, error_msg = validate_json_request(data, ['section_id', 'is_visible'])
        assert is_valid is True
        assert error_msg is None
    
    def test_validate_json_request_missing_field(self):
        """Test JSON validation with missing field."""
        data = {'section_id': 1}
        is_valid, error_msg = validate_json_request(data, ['section_id', 'is_visible'])
        assert is_valid is False
        assert error_msg == 'Missing required field: is_visible'
    
    def test_validate_json_request_no_data(self):
        """Test JSON validation with no data."""
        is_valid, error_msg = validate_json_request(None, ['section_id'])
        assert is_valid is False
        assert error_msg == 'No JSON data provided'
    
    def test_validate_json_request_empty_dict(self):
        """Test JSON validation with empty dict."""
        is_valid, error_msg = validate_json_request({}, ['section_id'])
        assert is_valid is False
        assert error_msg == 'Missing required field: section_id'


class TestSystemLogsRoute:
    """Test the system_logs route."""
    
    def test_system_logs_requires_login(self, client):
        """Test that system logs page requires login."""
        response = client.get('/admin/system_logs')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_system_logs_requires_admin(self, client, regular_user):
        """Test that system logs page requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/system_logs')
        assert response.status_code == 302
    
    def test_system_logs_get_success(self, client, admin_user, sample_system_events):
        """Test successful GET request to system logs."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/system_logs')
        assert response.status_code == 200
        assert b'System startup completed' in response.data
    
    def test_system_logs_pagination(self, client, admin_user, sample_system_events):
        """Test pagination parameters."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/system_logs?page=1&per_page=2')
        assert response.status_code == 200
    
    def test_system_logs_event_type_filter(self, client, admin_user, sample_system_events):
        """Test filtering by event type."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/system_logs?event_type=admin_action')
        assert response.status_code == 200
    
    def test_system_logs_event_level_filter(self, client, admin_user, sample_system_events):
        """Test filtering by event level."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/system_logs?event_level=error')
        assert response.status_code == 200
    
    def test_system_logs_date_filter(self, client, admin_user, sample_system_events):
        """Test filtering by date range."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        yesterday = (datetime.now() - timedelta(days=1)).strftime(DATE_FORMAT)
        response = client.get(f'/admin/system_logs?date_from={yesterday}')
        assert response.status_code == 200
    
    def test_system_logs_date_to_filter(self, client, admin_user, sample_system_events):
        """Test filtering by end date."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        yesterday = (datetime.now() - timedelta(days=1)).strftime(DATE_FORMAT)
        response = client.get(f'/admin/system_logs?date_to={yesterday}')
        assert response.status_code == 200
    
    def test_system_logs_date_range_filter(self, client, admin_user, sample_system_events):
        """Test filtering by date range (both from and to)."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        yesterday = (datetime.now() - timedelta(days=1)).strftime(DATE_FORMAT)
        today = datetime.now().strftime(DATE_FORMAT)
        response = client.get(f'/admin/system_logs?date_from={yesterday}&date_to={today}')
        assert response.status_code == 200
    
    def test_system_logs_invalid_date_filter(self, client, admin_user, sample_system_events):
        """Test with invalid date filter."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/system_logs?date_from=invalid-date')
        assert response.status_code == 200  # Should not crash, just ignore invalid date
    
    def test_system_logs_excessive_per_page(self, client, admin_user, sample_system_events):
        """Test with excessive per_page parameter."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/system_logs?per_page=500')
        assert response.status_code == 200


class TestDiscoverySectionsRoute:
    """Test the discovery_sections route."""
    
    def test_discovery_sections_requires_login(self, client):
        """Test that discovery sections page requires login."""
        response = client.get('/admin/discovery_sections')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_discovery_sections_requires_admin(self, client, regular_user):
        """Test that discovery sections page requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/discovery_sections')
        assert response.status_code == 302
    
    def test_discovery_sections_get_success(self, client, admin_user, sample_discovery_sections):
        """Test successful GET request to discovery sections."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/discovery_sections')
        assert response.status_code == 200
        assert b'Popular Games' in response.data
        assert b'New Releases' in response.data


class TestUpdateSectionOrderAPI:
    """Test the update_section_order API endpoint."""
    
    def test_update_section_order_requires_login(self, client):
        """Test that API requires login."""
        data = {'sections': [{'id': 1, 'order': 1}]}
        response = client.post('/admin/api/discovery_sections/order', 
                             json=data, content_type='application/json')
        assert response.status_code == 302
    
    def test_update_section_order_requires_admin(self, client, regular_user):
        """Test that API requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        data = {'sections': [{'id': 1, 'order': 1}]}
        response = client.post('/admin/api/discovery_sections/order', 
                             json=data, content_type='application/json')
        assert response.status_code == 302
    
    @patch('modules.routes_admin_ext.system.log_system_event')
    def test_update_section_order_success(self, mock_log, client, admin_user, sample_discovery_sections, db_session):
        """Test successful section order update."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Get section IDs
        sections = sample_discovery_sections
        data = {
            'sections': [
                {'id': sections[0].id, 'order': 5},
                {'id': sections[1].id, 'order': 10}
            ]
        }
        
        response = client.post('/admin/api/discovery_sections/order', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert 'Updated order for 2 sections' in response_data['message']
        
        # Verify database was updated
        updated_section = db_session.get(DiscoverySection, sections[0].id)
        assert updated_section.display_order == 5
        
        # Verify logging was called
        mock_log.assert_called()
    
    def test_update_section_order_empty_json(self, client, admin_user):
        """Test API with empty JSON data."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Send request with empty JSON object
        response = client.post('/admin/api/discovery_sections/order',
                             json={}, content_type='application/json')
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Missing required field: sections' in response_data['error']
    
    def test_update_section_order_no_content_type(self, client, admin_user):
        """Test API with no content type (Flask raises 415 -> caught as 500)."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Send request with no content type - Flask raises 415 error for get_json()
        response = client.post('/admin/api/discovery_sections/order')
        assert response.status_code == 500
        response_data = response.get_json()
        assert response_data['success'] is False
        assert response_data['error'] == 'Internal server error'
    
    def test_update_section_order_missing_sections(self, client, admin_user):
        """Test API with missing sections field."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {'other_field': 'value'}
        response = client.post('/admin/api/discovery_sections/order', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Missing required field: sections' in response_data['error']
    
    def test_update_section_order_invalid_sections_type(self, client, admin_user):
        """Test API with invalid sections type."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {'sections': 'not_an_array'}
        response = client.post('/admin/api/discovery_sections/order', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'sections must be an array' in response_data['error']
    
    def test_update_section_order_invalid_section_data(self, client, admin_user):
        """Test API with invalid section data format."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {'sections': [{'invalid': 'data'}]}
        response = client.post('/admin/api/discovery_sections/order', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Invalid section data format' in response_data['error']
    
    def test_update_section_order_invalid_id_type(self, client, admin_user):
        """Test API with invalid section ID type."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {'sections': [{'id': 'not_an_int', 'order': 1}]}
        response = client.post('/admin/api/discovery_sections/order', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Section ID and order must be integers' in response_data['error']
    
    def test_update_section_order_negative_order(self, client, admin_user):
        """Test API with negative display order."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {'sections': [{'id': 1, 'order': -1}]}
        response = client.post('/admin/api/discovery_sections/order', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Display order must be non-negative' in response_data['error']
    
    def test_update_section_order_nonexistent_section(self, client, admin_user):
        """Test API with nonexistent section ID."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {'sections': [{'id': 99999, 'order': 1}]}
        response = client.post('/admin/api/discovery_sections/order', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 404
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Section with ID 99999 not found' in response_data['error']


class TestUpdateSectionVisibilityAPI:
    """Test the update_section_visibility API endpoint."""
    
    def test_update_section_visibility_requires_login(self, client):
        """Test that API requires login."""
        data = {'section_id': 1, 'is_visible': True}
        response = client.post('/admin/api/discovery_sections/visibility', 
                             json=data, content_type='application/json')
        assert response.status_code == 302
    
    def test_update_section_visibility_requires_admin(self, client, regular_user):
        """Test that API requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        data = {'section_id': 1, 'is_visible': True}
        response = client.post('/admin/api/discovery_sections/visibility', 
                             json=data, content_type='application/json')
        assert response.status_code == 302
    
    @patch('modules.routes_admin_ext.system.log_system_event')
    def test_update_section_visibility_success(self, mock_log, client, admin_user, sample_discovery_sections, db_session):
        """Test successful section visibility update."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        section = sample_discovery_sections[0]
        original_visibility = section.is_visible
        
        data = {'section_id': section.id, 'is_visible': not original_visibility}
        response = client.post('/admin/api/discovery_sections/visibility', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert section.name in response_data['message']
        
        # Verify database was updated
        updated_section = db_session.get(DiscoverySection, section.id)
        assert updated_section.is_visible == (not original_visibility)
        
        # Verify logging was called
        mock_log.assert_called()
    
    def test_update_section_visibility_empty_json(self, client, admin_user):
        """Test API with empty JSON data."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/api/discovery_sections/visibility',
                             json={}, content_type='application/json')
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Missing required field: section_id' in response_data['error']
    
    def test_update_section_visibility_no_content_type(self, client, admin_user):
        """Test API with no content type (Flask raises 415 -> caught as 500)."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/api/discovery_sections/visibility')
        assert response.status_code == 500
        response_data = response.get_json()
        assert response_data['success'] is False
        assert response_data['error'] == 'Internal server error'
    
    def test_update_section_visibility_missing_field(self, client, admin_user):
        """Test API with missing required field."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {'section_id': 1}  # Missing is_visible
        response = client.post('/admin/api/discovery_sections/visibility', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Missing required field: is_visible' in response_data['error']
    
    def test_update_section_visibility_invalid_section_id(self, client, admin_user):
        """Test API with invalid section ID."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {'section_id': 'not_an_int', 'is_visible': True}
        response = client.post('/admin/api/discovery_sections/visibility', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'section_id must be an integer' in response_data['error']
    
    def test_update_section_visibility_invalid_boolean(self, client, admin_user):
        """Test API with invalid is_visible type."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {'section_id': 1, 'is_visible': 'not_a_boolean'}
        response = client.post('/admin/api/discovery_sections/visibility', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'is_visible must be a boolean' in response_data['error']
    
    def test_update_section_visibility_nonexistent_section(self, client, admin_user):
        """Test API with nonexistent section ID."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {'section_id': 99999, 'is_visible': True}
        response = client.post('/admin/api/discovery_sections/visibility', 
                             json=data, content_type='application/json')
        
        assert response.status_code == 404
        response_data = response.get_json()
        assert response_data['success'] is False
        assert 'Section with ID 99999 not found' in response_data['error']


class TestSystemIntegration:
    """Integration tests for system functionality."""
    
    @patch('modules.routes_admin_ext.system.log_system_event')
    def test_complete_section_management_workflow(self, mock_log, client, admin_user, sample_discovery_sections, db_session):
        """Test complete workflow of managing discovery sections."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Step 1: View sections page
        response = client.get('/admin/discovery_sections')
        assert response.status_code == 200
        
        # Step 2: Update section order
        sections = sample_discovery_sections
        order_data = {
            'sections': [
                {'id': sections[0].id, 'order': 10},
                {'id': sections[1].id, 'order': 5}
            ]
        }
        
        response = client.post('/admin/api/discovery_sections/order', 
                             json=order_data, content_type='application/json')
        assert response.status_code == 200
        
        # Verify order was updated
        updated_section1 = db_session.get(DiscoverySection, sections[0].id)
        updated_section2 = db_session.get(DiscoverySection, sections[1].id)
        assert updated_section1.display_order == 10
        assert updated_section2.display_order == 5
        
        # Step 3: Update section visibility
        visibility_data = {'section_id': sections[0].id, 'is_visible': False}
        response = client.post('/admin/api/discovery_sections/visibility', 
                             json=visibility_data, content_type='application/json')
        assert response.status_code == 200
        
        # Verify visibility was updated
        updated_section1 = db_session.get(DiscoverySection, sections[0].id)
        assert updated_section1.is_visible is False
        
        # Verify logging was called multiple times
        assert mock_log.call_count >= 2


class TestClearSystemLogsAPI:
    """Test the clear_system_logs API endpoint."""
    
    def test_clear_logs_requires_login(self, client):
        """Test that API requires login."""
        response = client.delete('/admin/api/system_logs/clear')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_clear_logs_requires_admin(self, client, regular_user):
        """Test that API requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.delete('/admin/api/system_logs/clear')
        assert response.status_code == 302
    
    def test_clear_logs_success(self, client, admin_user, sample_system_events, db_session):
        """Test successful log clearing."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Verify we have logs before clearing
        initial_count = db_session.query(SystemEvents).count()
        assert initial_count == 5  # From sample_system_events fixture
        
        response = client.delete('/admin/api/system_logs/clear')
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert f'Successfully cleared {initial_count} system logs' in response_data['message']
        assert response_data['deleted_count'] == initial_count
        
        # Verify all logs were deleted except the audit log
        remaining_count = db_session.query(SystemEvents).count()
        assert remaining_count == 1  # Only the new log entry created after clearing
        
        # Verify the audit log was created with correct content
        audit_log = db_session.query(SystemEvents).first()
        assert audit_log.event_type == 'admin_action'
        assert audit_log.event_level == 'warning'
        assert audit_log.audit_user == admin_user.id
        assert f"System logs cleared by admin user '{admin_user.name}' (ID: {admin_user.id})" in audit_log.event_text
        assert f"{initial_count} logs were deleted" in audit_log.event_text
    
    @patch('modules.routes_admin_ext.system.log_system_event')
    def test_clear_logs_empty_database(self, mock_log, client, admin_user, db_session):
        """Test clearing logs when database is already empty."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Clear any existing logs first
        db_session.query(SystemEvents).delete()
        db_session.commit()
        
        response = client.delete('/admin/api/system_logs/clear')
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['success'] is True
        assert 'Successfully cleared 0 system logs' in response_data['message']
        assert response_data['deleted_count'] == 0
        
        # Verify the action was still logged
        mock_log.assert_called_with(
            f"System logs cleared by admin user '{admin_user.name}' (ID: {admin_user.id}). 0 logs were deleted.",
            event_type='admin_action',
            event_level='warning',
            audit_user=admin_user.id
        )
    
    @patch('modules.routes_admin_ext.system.log_system_event')
    def test_clear_logs_database_error(self, mock_log, client, admin_user, sample_system_events, db_session):
        """Test error handling when database operation fails."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Simulate a database error by mocking the delete operation
        with patch('modules.routes_admin_ext.system.db.session.execute') as mock_execute:
            mock_execute.side_effect = Exception("Database connection lost")
            
            response = client.delete('/admin/api/system_logs/clear')
            
            assert response.status_code == 500
            response_data = response.get_json()
            assert response_data['success'] is False
            assert response_data['error'] == 'Internal server error'
            
            # Verify error logging was called
            mock_log.assert_called_with(
                'Failed to clear system logs: Database connection lost',
                event_type='admin_action',
                event_level='error',
                audit_user=admin_user.id
            )
    
    def test_clear_logs_wrong_method(self, client, admin_user):
        """Test that endpoint only accepts DELETE method."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Try with GET
        response = client.get('/admin/api/system_logs/clear')
        assert response.status_code == 405  # Method Not Allowed
        
        # Try with POST
        response = client.post('/admin/api/system_logs/clear')
        assert response.status_code == 405  # Method Not Allowed
        
        # Try with PUT
        response = client.put('/admin/api/system_logs/clear')
        assert response.status_code == 405  # Method Not Allowed
    
    @patch('modules.routes_admin_ext.system.log_system_event')
    def test_clear_logs_includes_user_details(self, mock_log, client, admin_user, sample_system_events, db_session):
        """Test that the log entry includes proper user details."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        initial_count = db_session.query(SystemEvents).count()
        
        response = client.delete('/admin/api/system_logs/clear')
        
        assert response.status_code == 200
        
        # Verify the log message includes both user name and ID
        mock_log.assert_called_with(
            f"System logs cleared by admin user '{admin_user.name}' (ID: {admin_user.id}). {initial_count} logs were deleted.",
            event_type='admin_action',
            event_level='warning',
            audit_user=admin_user.id
        )
    
    def test_clear_logs_audit_persistence(self, client, admin_user, sample_system_events, db_session):
        """Test that the audit log persists after clearing."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        initial_count = db_session.query(SystemEvents).count()
        
        response = client.delete('/admin/api/system_logs/clear')
        assert response.status_code == 200
        
        # After clearing, there should be exactly 1 log entry (the audit log)
        final_count = db_session.query(SystemEvents).count()
        assert final_count == 1
        
        # The remaining log should be the audit log
        remaining_log = db_session.query(SystemEvents).first()
        assert remaining_log.event_type == 'admin_action'
        assert remaining_log.event_level == 'warning'
        assert remaining_log.audit_user == admin_user.id
        assert 'System logs cleared by admin user' in remaining_log.event_text


class TestSystemIntegrationExtended:
    """Additional integration tests for system functionality."""
    
    def test_system_logs_with_multiple_filters(self, client, admin_user, sample_system_events):
        """Test system logs with multiple filters applied."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Apply multiple filters
        yesterday = (datetime.now() - timedelta(days=1)).strftime(DATE_FORMAT)
        params = {
            'event_type': 'admin_action',
            'event_level': 'information',
            'date_from': yesterday,
            'per_page': 10
        }
        
        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        response = client.get(f'/admin/system_logs?{query_string}')
        
        assert response.status_code == 200
        # Should only show admin_action events with information level from yesterday onwards
    
    @patch('modules.routes_admin_ext.system.log_system_event')
    def test_error_handling_with_database_rollback(self, mock_log, client, admin_user, sample_discovery_sections, db_session):
        """Test that database errors are handled properly with rollback."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Use an existing section to avoid 404 error
        section = sample_discovery_sections[0]
        
        # Simulate a database error by mocking the commit method
        with patch('modules.routes_admin_ext.system.db.session.commit') as mock_commit:
            mock_commit.side_effect = Exception("Database connection lost")
            
            data = {'sections': [{'id': section.id, 'order': 1}]}
            response = client.post('/admin/api/discovery_sections/order', 
                                 json=data, content_type='application/json')
            
            assert response.status_code == 500
            response_data = response.get_json()
            assert response_data['success'] is False
            assert response_data['error'] == 'Internal server error'
            
            # Verify error logging was called
            mock_log.assert_called_with(
                'Failed to update discovery section order: Database connection lost',
                event_type='admin_action',
                event_level='error',
                audit_user=admin_user.id
            )