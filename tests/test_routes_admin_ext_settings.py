import pytest
import json
from flask import url_for
from unittest.mock import patch, MagicMock
from modules.models import User, GlobalSettings
from modules import db, cache
from modules.routes_admin_ext.settings import (
    validate_settings_data, get_or_create_settings_record, 
    update_settings_fields, build_current_settings,
    DEFAULT_SETTINGS, FIELD_MAPPINGS,
    MIN_SCAN_THREADS, MAX_SCAN_THREADS, MIN_DOWNLOAD_THREADS, MAX_DOWNLOAD_THREADS,
    MIN_BATCH_SIZE, MAX_BATCH_SIZE
)
from uuid import uuid4
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
def global_settings(db_session):
    """Create a GlobalSettings record."""
    # Clear existing settings
    db_session.query(GlobalSettings).delete()
    db_session.commit()
    
    settings = GlobalSettings(
        settings={
            'showSystemLogo': True,
            'enableNewsletterFeature': False,
            'siteUrl': 'http://test.local'
        },
        enable_delete_game_on_disk=True,
        discord_notify_new_games=False,
        scan_thread_count=2,
        turbo_download_threads=10,
        turbo_download_batch_size=150
    )
    db_session.add(settings)
    db_session.commit()
    return settings


@pytest.fixture
def clean_settings(db_session):
    """Clean settings for isolated testing."""
    db_session.query(GlobalSettings).delete()
    db_session.commit()
    cache.clear()


class TestValidateSettingsData:
    """Test the validate_settings_data function."""
    
    def test_validate_settings_valid_data(self):
        """Test validation with valid settings data."""
        valid_data = {
            'scanThreadCount': 2,
            'turboDownloadThreads': 10,
            'turboDownloadBatchSize': 100,
            'updateFolderName': 'updates',
            'extrasFolderName': 'extras',
            'siteUrl': 'http://test.com'
        }
        errors = validate_settings_data(valid_data)
        assert errors == []

    def test_validate_settings_invalid_data_type(self):
        """Test validation with non-dict data."""
        errors = validate_settings_data("not_a_dict")
        assert "Settings data must be a JSON object" in errors

    def test_validate_scan_threads_invalid_range(self):
        """Test validation with invalid scan thread count."""
        # Test below minimum
        errors = validate_settings_data({'scanThreadCount': 0})
        assert any("Scan thread count must be between" in error for error in errors)
        
        # Test above maximum
        errors = validate_settings_data({'scanThreadCount': 10})
        assert any("Scan thread count must be between" in error for error in errors)

    def test_validate_download_threads_invalid_range(self):
        """Test validation with invalid download thread count."""
        errors = validate_settings_data({'turboDownloadThreads': 0})
        assert any("Download threads must be between" in error for error in errors)
        
        errors = validate_settings_data({'turboDownloadThreads': 30})
        assert any("Download threads must be between" in error for error in errors)

    def test_validate_batch_size_invalid_range(self):
        """Test validation with invalid batch size."""
        errors = validate_settings_data({'turboDownloadBatchSize': 5})
        assert any("Batch size must be between" in error for error in errors)
        
        errors = validate_settings_data({'turboDownloadBatchSize': 2000})
        assert any("Batch size must be between" in error for error in errors)

    def test_validate_folder_names_invalid(self):
        """Test validation with invalid folder names."""
        # Empty string
        errors = validate_settings_data({'updateFolderName': ''})
        assert any("updateFolderName must be a non-empty string" in error for error in errors)
        
        # Too long
        errors = validate_settings_data({'extrasFolderName': 'x' * 101})
        assert any("extrasFolderName must be less than 100 characters" in error for error in errors)
        
        # Non-string type
        errors = validate_settings_data({'updateFolderName': 123})
        assert any("updateFolderName must be a non-empty string" in error for error in errors)

    def test_validate_site_url_invalid(self):
        """Test validation with invalid site URL."""
        # Empty string
        errors = validate_settings_data({'siteUrl': ''})
        assert any("Site URL must be a non-empty string" in error for error in errors)
        
        # Too long
        errors = validate_settings_data({'siteUrl': 'x' * 501})
        assert any("Site URL must be less than 500 characters" in error for error in errors)
        
        # Non-string type
        errors = validate_settings_data({'siteUrl': 123})
        assert any("Site URL must be a non-empty string" in error for error in errors)


class TestGetOrCreateSettingsRecord:
    """Test the get_or_create_settings_record function."""
    
    def test_get_existing_settings_record(self, db_session, global_settings):
        """Test retrieving existing settings record."""
        with patch('modules.routes_admin_ext.settings.db.session', db_session):
            record = get_or_create_settings_record()
            assert record.id == global_settings.id

    def test_create_new_settings_record(self, db_session, clean_settings):
        """Test creating new settings record when none exists."""
        with patch('modules.routes_admin_ext.settings.db.session', db_session):
            record = get_or_create_settings_record()
            assert record is not None
            assert record.settings == {}


class TestUpdateSettingsFields:
    """Test the update_settings_fields function."""
    
    def test_update_settings_fields_success(self, db_session, global_settings):
        """Test successful field updates."""
        new_settings = {
            'enableDeleteGameOnDisk': False,
            'discordNotifyNewGames': True,
            'scanThreadCount': 3,
            'updateFolderName': 'new_updates'
        }
        
        update_settings_fields(global_settings, new_settings)
        
        assert global_settings.enable_delete_game_on_disk == False
        assert global_settings.discord_notify_new_games == True
        assert global_settings.scan_thread_count == 3
        assert global_settings.update_folder_name == 'new_updates'
        assert global_settings.settings == new_settings

    def test_update_settings_fields_invalid_scan_threads(self, db_session, global_settings):
        """Test updating with invalid scan thread count."""
        original_scan_threads = global_settings.scan_thread_count
        new_settings = {'scanThreadCount': 10}  # Invalid value
        
        update_settings_fields(global_settings, new_settings)
        
        # Should not update scan_thread_count due to validation
        assert global_settings.scan_thread_count == original_scan_threads


class TestBuildCurrentSettings:
    """Test the build_current_settings function."""
    
    def test_build_current_settings_no_record(self):
        """Test building settings when no record exists."""
        settings = build_current_settings(None)
        assert settings == DEFAULT_SETTINGS

    def test_build_current_settings_with_record(self, global_settings):
        """Test building settings with existing record."""
        settings = build_current_settings(global_settings)
        
        # Should contain defaults merged with database values
        assert 'showSystemLogo' in settings
        assert settings['enableDeleteGameOnDisk'] == global_settings.enable_delete_game_on_disk
        assert settings['scanThreadCount'] == global_settings.scan_thread_count

    def test_build_current_settings_missing_fields(self, db_session):
        """Test building settings with missing database fields."""
        # Create settings record with minimal data
        settings_record = GlobalSettings(settings={'showVersion': False})
        db_session.add(settings_record)
        db_session.commit()
        
        settings = build_current_settings(settings_record)
        
        # Should fill in defaults for missing fields
        assert 'showSystemLogo' in settings
        assert settings['showSystemLogo'] == DEFAULT_SETTINGS['showSystemLogo']
        assert settings['showVersion'] == False  # From database


class TestSettingsRoutes:
    """Test the settings route handlers."""
    
    def test_get_settings_requires_login(self, client):
        """Test that GET settings requires login."""
        response = client.get('/admin/settings')
        assert response.status_code == 302
        assert 'login' in response.location

    def test_get_settings_requires_admin(self, client, regular_user):
        """Test that GET settings requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/settings')
        assert response.status_code == 302

    def test_get_settings_success(self, client, admin_user, global_settings):
        """Test successful GET settings request."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/settings')
        assert response.status_code == 200

    def test_update_settings_requires_login(self, client):
        """Test that POST settings requires login."""
        response = client.post('/admin/settings', json={'test': 'data'})
        assert response.status_code == 302

    def test_update_settings_requires_admin(self, client, regular_user):
        """Test that POST settings requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/settings', json={'test': 'data'})
        assert response.status_code == 302

    def test_update_settings_invalid_json(self, client, admin_user):
        """Test POST settings with invalid JSON."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/settings', data='invalid json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_update_settings_no_data(self, client, admin_user):
        """Test POST settings with no data."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # Test with empty JSON object
        response = client.post('/admin/settings', json={})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'No settings data provided' in data['error']

    def test_update_settings_validation_errors(self, client, admin_user):
        """Test POST settings with validation errors."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        invalid_data = {'scanThreadCount': 10}  # Invalid value
        response = client.post('/admin/settings', json=invalid_data)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'errors' in data

    @patch('modules.routes_admin_ext.settings.log_system_event')
    @patch('modules.routes_admin_ext.settings.cache.delete')
    def test_update_settings_success(self, mock_cache_delete, mock_log_event, 
                                   client, admin_user, db_session, clean_settings):
        """Test successful settings update."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        valid_data = {
            'showSystemLogo': False,
            'scanThreadCount': 2,
            'turboDownloadThreads': 15,
            'updateFolderName': 'my_updates'
        }
        
        response = client.post('/admin/settings', json=valid_data)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['message'] == 'Settings updated successfully'
        
        # Verify database was updated
        settings_record = db_session.query(GlobalSettings).first()
        assert settings_record is not None
        assert settings_record.scan_thread_count == 2
        assert settings_record.turbo_download_threads == 15
        assert settings_record.update_folder_name == 'my_updates'
        
        # Verify logging and cache clearing were called
        mock_log_event.assert_called_once()
        mock_cache_delete.assert_called_once_with('global_settings')

    @patch('modules.routes_admin_ext.settings.db.session.commit')
    def test_update_settings_database_error(self, mock_commit, client, admin_user):
        """Test settings update with database error."""
        mock_commit.side_effect = Exception('Database error')
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        valid_data = {'showSystemLogo': False}
        response = client.post('/admin/settings', json=valid_data)
        assert response.status_code == 500
        
        data = json.loads(response.data)
        assert 'Failed to update settings' in data['error']


class TestLegacyRouteHandler:
    """Test the legacy manage_settings route handler."""
    
    def test_legacy_route_get(self, client, admin_user, global_settings):
        """Test legacy route with GET method."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/settings')
        assert response.status_code == 200

    @patch('modules.routes_admin_ext.settings.log_system_event')
    @patch('modules.routes_admin_ext.settings.cache.delete')
    def test_legacy_route_post(self, mock_cache_delete, mock_log_event,
                             client, admin_user, clean_settings):
        """Test legacy route with POST method."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        valid_data = {'showSystemLogo': False}
        response = client.post('/admin/settings', json=valid_data)
        assert response.status_code == 200


class TestSettingsIntegration:
    """Integration tests for settings functionality."""
    
    @patch('modules.routes_admin_ext.settings.log_system_event')
    @patch('modules.routes_admin_ext.settings.cache.delete')
    def test_complete_settings_workflow(self, mock_cache_delete, mock_log_event,
                                      client, admin_user, db_session, clean_settings):
        """Test complete settings workflow from GET to POST."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # Step 1: GET initial settings
        response = client.get('/admin/settings')
        assert response.status_code == 200
        
        # Step 2: Update settings
        new_settings = {
            'showSystemLogo': False,
            'enableNewsletterFeature': True,
            'scanThreadCount': 3,
            'turboDownloadThreads': 12,
            'turboDownloadBatchSize': 250,
            'updateFolderName': 'game_updates',
            'extrasFolderName': 'game_extras',
            'siteUrl': 'https://mygames.local'
        }
        
        response = client.post('/admin/settings', json=new_settings)
        assert response.status_code == 200
        
        # Step 3: Verify database state
        settings_record = db_session.query(GlobalSettings).first()
        assert settings_record is not None
        assert settings_record.settings == new_settings
        assert settings_record.scan_thread_count == 3
        assert settings_record.turbo_download_threads == 12
        assert settings_record.turbo_download_batch_size == 250
        assert settings_record.update_folder_name == 'game_updates'
        assert settings_record.extras_folder_name == 'game_extras'
        assert settings_record.site_url == 'https://mygames.local'
        
        # Step 4: GET updated settings to verify
        response = client.get('/admin/settings')
        assert response.status_code == 200

    def test_settings_persistence(self, client, admin_user, db_session, clean_settings):
        """Test that settings persist across requests."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # Create initial settings
        initial_settings = {
            'showSystemLogo': False,
            'scanThreadCount': 2,
            'updateFolderName': 'persistent_updates'
        }
        
        with patch('modules.routes_admin_ext.settings.log_system_event'), \
             patch('modules.routes_admin_ext.settings.cache.delete'):
            response = client.post('/admin/settings', json=initial_settings)
            assert response.status_code == 200
        
        # Update some settings
        updated_settings = {
            'showSystemLogo': True,  # Changed
            'scanThreadCount': 2,    # Unchanged
            'turboDownloadThreads': 15  # New field
        }
        
        with patch('modules.routes_admin_ext.settings.log_system_event'), \
             patch('modules.routes_admin_ext.settings.cache.delete'):
            response = client.post('/admin/settings', json=updated_settings)
            assert response.status_code == 200
        
        # Verify final state combines both updates
        settings_record = db_session.query(GlobalSettings).first()
        final_settings = settings_record.settings
        
        assert final_settings['showSystemLogo'] == True  # Updated value
        assert final_settings['scanThreadCount'] == 2    # Persistent value
        assert final_settings['turboDownloadThreads'] == 15  # New value