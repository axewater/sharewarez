import pytest
from flask import url_for
from modules.models import GlobalSettings, User
from modules import db
from uuid import uuid4
import time
import json
from unittest.mock import patch, Mock
from datetime import datetime, timezone


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
def clean_global_settings(db_session):
    """Clean GlobalSettings and create a fresh one."""
    # Clear any existing settings
    db_session.execute(db.delete(GlobalSettings))
    db_session.commit()
    
    settings = GlobalSettings(
        igdb_client_id='test_client_id',
        igdb_client_secret='test_client_secret'
    )
    db_session.add(settings)
    db_session.commit()
    return settings

@pytest.fixture
def clean_db(db_session):
    """Clean GlobalSettings table."""
    # Clear any existing settings
    db_session.execute(db.delete(GlobalSettings))
    db_session.commit()


class TestIGDBSettingsRoute:
    
    def test_igdb_settings_requires_login(self, client):
        """Test that IGDB settings requires login."""
        response = client.get('/admin/igdb_settings')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_igdb_settings_requires_admin(self, client, regular_user):
        """Test that IGDB settings requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/igdb_settings')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_igdb_settings_get_admin_access(self, client, admin_user):
        """Test that admin can access IGDB settings page."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/igdb_settings')
        assert response.status_code == 200
    
    def test_igdb_settings_get_with_existing_settings(self, client, admin_user, clean_global_settings):
        """Test GET request displays existing IGDB settings."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/igdb_settings')
        assert response.status_code == 200
        # The template should receive the settings object
        response_data = response.get_data(as_text=True)
        assert 'admin_manage_igdb_settings.html' in response_data or 'settings' in response_data
    
    def test_igdb_settings_get_no_existing_settings(self, client, admin_user):
        """Test GET request when no settings exist."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/igdb_settings')
        assert response.status_code == 200
    
    def test_igdb_settings_post_create_new_settings(self, client, admin_user, clean_db):
        """Test POST request creates new settings when none exist."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        test_data = {
            'igdb_client_id': 'new_client_id',
            'igdb_client_secret': 'new_client_secret'
        }
        
        response = client.post('/admin/igdb_settings', 
                             json=test_data,
                             content_type='application/json')
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['status'] == 'success'
        assert 'updated successfully' in response_data['message']
        
        # Verify settings were created in database
        settings = db.session.execute(db.select(GlobalSettings)).scalars().first()
        assert settings is not None
        assert settings.igdb_client_id == 'new_client_id'
        assert settings.igdb_client_secret == 'new_client_secret'
    
    def test_igdb_settings_post_update_existing_settings(self, client, admin_user, clean_global_settings):
        """Test POST request updates existing settings."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        test_data = {
            'igdb_client_id': 'updated_client_id',
            'igdb_client_secret': 'updated_client_secret'
        }
        
        response = client.post('/admin/igdb_settings', 
                             json=test_data,
                             content_type='application/json')
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['status'] == 'success'
        
        # Verify settings were updated in database
        db.session.refresh(clean_global_settings)
        assert clean_global_settings.igdb_client_id == 'updated_client_id'
        assert clean_global_settings.igdb_client_secret == 'updated_client_secret'
    
    def test_igdb_settings_post_partial_data(self, client, admin_user, clean_db):
        """Test POST request with partial data."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        test_data = {
            'igdb_client_id': 'only_client_id'
            # Missing igdb_client_secret
        }
        
        response = client.post('/admin/igdb_settings', 
                             json=test_data,
                             content_type='application/json')
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['status'] == 'success'
        
        # Verify settings were saved
        settings = db.session.execute(db.select(GlobalSettings)).scalars().first()
        assert settings.igdb_client_id == 'only_client_id'
        assert settings.igdb_client_secret is None
    
    def test_igdb_settings_post_empty_data(self, client, admin_user):
        """Test POST request with empty data."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/igdb_settings', 
                             json={},
                             content_type='application/json')
        
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['status'] == 'success'
    
    @patch('modules.routes_admin_ext.igdb.db.session.commit')
    def test_igdb_settings_post_database_error(self, mock_commit, client, admin_user):
        """Test POST request handles database errors."""
        mock_commit.side_effect = Exception("Database error")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        test_data = {
            'igdb_client_id': 'test_id',
            'igdb_client_secret': 'test_secret'
        }
        
        response = client.post('/admin/igdb_settings', 
                             json=test_data,
                             content_type='application/json')
        
        assert response.status_code == 500
        response_data = response.get_json()
        assert response_data['status'] == 'error'
        assert 'Database error' in response_data['message']
    
    def test_igdb_settings_post_invalid_json(self, client, admin_user):
        """Test POST request with invalid JSON."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/igdb_settings', 
                             data='invalid json',
                             content_type='application/json')
        
        # Should handle the error gracefully
        assert response.status_code in [400, 500]


class TestIGDBTestRoute:
    
    def test_test_igdb_requires_login(self, client):
        """Test that IGDB test requires login."""
        response = client.post('/admin/test_igdb')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_test_igdb_requires_admin(self, client, regular_user):
        """Test that IGDB test requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_igdb')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_test_igdb_no_settings(self, client, admin_user):
        """Test IGDB test when no settings exist."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_igdb')
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['status'] == 'error'
        assert 'not configured' in response_data['message']
    
    def test_test_igdb_incomplete_settings(self, client, admin_user):
        """Test IGDB test with incomplete settings."""
        # Create settings with only client_id, missing client_secret
        settings = GlobalSettings(igdb_client_id='test_id')
        db.session.add(settings)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_igdb')
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['status'] == 'error'
        assert 'not configured' in response_data['message']
    
    @patch('modules.routes_admin_ext.igdb.make_igdb_api_request')
    def test_test_igdb_successful_api_call(self, mock_api_request, client, admin_user, clean_global_settings):
        """Test successful IGDB API test."""
        # Mock successful API response
        mock_api_request.return_value = [{'name': 'Test Game'}]
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_igdb')
        assert response.status_code == 200
        response_data = response.get_json()
        assert response_data['status'] == 'success'
        assert 'successful' in response_data['message']
        
        # Verify API was called with correct parameters
        mock_api_request.assert_called_once_with(
            'https://api.igdb.com/v4/games', 
            'fields name; limit 1;'
        )
        
        # Verify last_tested timestamp was updated
        db.session.refresh(clean_global_settings)
        assert clean_global_settings.igdb_last_tested is not None
    
    @patch('modules.routes_admin_ext.igdb.make_igdb_api_request')
    def test_test_igdb_invalid_api_response(self, mock_api_request, client, admin_user, clean_global_settings):
        """Test IGDB test with invalid API response."""
        # Mock invalid API response (not a list)
        mock_api_request.return_value = {'error': 'Invalid response'}
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_igdb')
        assert response.status_code == 500
        response_data = response.get_json()
        assert response_data['status'] == 'error'
        assert 'Invalid API response' in response_data['message']
    
    @patch('modules.routes_admin_ext.igdb.make_igdb_api_request')
    def test_test_igdb_api_exception(self, mock_api_request, client, admin_user, clean_global_settings):
        """Test IGDB test when API call raises exception."""
        # Mock API request to raise an exception
        mock_api_request.side_effect = Exception("API connection failed")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_igdb')
        assert response.status_code == 500
        response_data = response.get_json()
        assert response_data['status'] == 'error'
        assert 'API connection failed' in response_data['message']
    
    def test_test_igdb_get_method_not_allowed(self, client, admin_user):
        """Test that GET method is not allowed for IGDB test."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/test_igdb')
        assert response.status_code == 405  # Method Not Allowed


class TestIGDBIntegration:
    
    def test_igdb_settings_and_test_workflow(self, client, admin_user):
        """Test complete workflow: set settings then test them."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # First, set IGDB settings
        settings_data = {
            'igdb_client_id': 'workflow_client_id',
            'igdb_client_secret': 'workflow_client_secret'
        }
        
        settings_response = client.post('/admin/igdb_settings', 
                                      json=settings_data,
                                      content_type='application/json')
        assert settings_response.status_code == 200
        
        # Then test with those settings (will fail without mock, but that's expected)
        test_response = client.post('/admin/test_igdb')
        # Should get an error since we don't have real IGDB credentials, but it should not be a 400
        assert test_response.status_code in [200, 500]  # 500 for actual API failure, not config failure
    
    def test_igdb_routes_blueprint_registration(self, app):
        """Test that IGDB routes are properly registered."""
        with app.test_request_context():
            assert url_for('admin2.igdb_settings') == '/admin/igdb_settings'
            assert url_for('admin2.test_igdb') == '/admin/test_igdb'
    
    @patch('modules.routes_admin_ext.igdb.make_igdb_api_request')
    def test_igdb_last_tested_timestamp_update(self, mock_api_request, client, admin_user, clean_global_settings):
        """Test that igdb_last_tested timestamp is properly updated."""
        # Mock successful API response
        mock_api_request.return_value = [{'name': 'Test Game'}]
        
        # Record original timestamp
        original_timestamp = clean_global_settings.igdb_last_tested
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Small delay to ensure timestamp difference
        time.sleep(0.01)
        
        response = client.post('/admin/test_igdb')
        assert response.status_code == 200
        
        # Verify timestamp was updated
        db.session.refresh(clean_global_settings)
        assert clean_global_settings.igdb_last_tested != original_timestamp
        assert clean_global_settings.igdb_last_tested is not None
    
    def test_igdb_settings_persistence(self, client, admin_user, clean_db):
        """Test that IGDB settings persist correctly."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Set settings
        settings_data = {
            'igdb_client_id': 'persist_client_id',
            'igdb_client_secret': 'persist_client_secret'
        }
        
        client.post('/admin/igdb_settings', 
                   json=settings_data,
                   content_type='application/json')
        
        # Retrieve settings via GET request
        response = client.get('/admin/igdb_settings')
        assert response.status_code == 200
        
        # Verify settings are still in database
        settings = db.session.execute(db.select(GlobalSettings)).scalars().first()
        assert settings.igdb_client_id == 'persist_client_id'
        assert settings.igdb_client_secret == 'persist_client_secret'