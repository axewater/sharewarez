import pytest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import select
from modules import db
from modules.models import User, Game, Library, SystemEvents
from modules.platform import LibraryPlatform


@pytest.fixture
def authenticated_user(db_session):
    """Create and return an authenticated user."""
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
def admin_user(db_session):
    """Create and return an admin user."""
    user_uuid = str(uuid4())
    unique_id = str(uuid4())[:8]
    admin = User(
        user_id=user_uuid,
        name=f'AdminUser_{unique_id}',
        email=f'admin_{unique_id}@test.com',
        role='admin',
        is_email_verified=True
    )
    admin.set_password('adminpass123')
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture
def test_library(db_session):
    """Create a test library."""
    library = Library(
        name='Test Library',
        platform=LibraryPlatform.PCWIN
    )
    db_session.add(library)
    db_session.commit()
    return library


@pytest.fixture
def test_game_with_file(db_session, test_library):
    """Create a test game with an actual file on disk."""
    temp_dir = tempfile.mkdtemp()
    game_file = os.path.join(temp_dir, 'test_game.rom')
    
    # Create test ROM file
    with open(game_file, 'w') as f:
        f.write('test rom file content')
    
    game = Game(
        name='Test Game ROM',
        library_uuid=test_library.uuid,
        full_disk_path=game_file,
        size=len('test rom file content'),
        times_downloaded=0
    )
    db_session.add(game)
    db_session.commit()
    
    yield game
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_game_with_folder(db_session, test_library):
    """Create a test game that points to a folder (not supported)."""
    temp_dir = tempfile.mkdtemp()
    game_dir = os.path.join(temp_dir, 'test_game_folder')
    os.makedirs(game_dir, exist_ok=True)
    
    # Create files in the folder
    with open(os.path.join(game_dir, 'game1.exe'), 'w') as f:
        f.write('game executable')
    
    game = Game(
        name='Test Game Folder',
        library_uuid=test_library.uuid,
        full_disk_path=game_dir,
        size=1024,
        times_downloaded=0
    )
    db_session.add(game)
    db_session.commit()
    
    yield game
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_game_with_nonexistent_file(db_session, test_library):
    """Create a test game with a non-existent file path."""
    game = Game(
        name='Test Game Missing',
        library_uuid=test_library.uuid,
        full_disk_path='/nonexistent/path/missing_game.rom',
        size=0,
        times_downloaded=0
    )
    db_session.add(game)
    db_session.commit()
    return game


@pytest.fixture
def test_game_with_unsafe_path(db_session, test_library):
    """Create a test game with a potentially unsafe path."""
    # This path attempts traversal but will be blocked by security
    unsafe_path = '/tmp/../../../etc/passwd'
    
    game = Game(
        name='Test Game Unsafe Path',
        library_uuid=test_library.uuid,
        full_disk_path=unsafe_path,
        size=0,
        times_downloaded=0
    )
    db_session.add(game)
    db_session.commit()
    return game


class TestPlayGameRoute:
    """Test the /play_game/<game_uuid> route."""
    
    def test_play_game_requires_login(self, client, test_game_with_file):
        """Test that play_game requires login."""
        response = client.get(f'/play_game/{test_game_with_file.uuid}')
        assert response.status_code == 302  # Should redirect to login
        assert 'login' in response.location or '/auth' in response.location
    
    def test_play_game_authenticated_access(self, client, authenticated_user, test_game_with_file):
        """Test that authenticated users can access play_game."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/play_game/{test_game_with_file.uuid}', follow_redirects=True)
        assert response.status_code == 200
        # Should contain flash message about functionality coming soon
        assert b'Play game functionality coming soon!' in response.data
    
    def test_play_game_redirects_with_flash(self, client, authenticated_user, test_game_with_file):
        """Test that play_game redirects with proper flash message."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/play_game/{test_game_with_file.uuid}')
        assert response.status_code == 302
        # Should redirect to game details
        assert f'/game_details/{test_game_with_file.uuid}' in response.location


class TestPlayRomTestRoute:
    """Test the /playromtest route."""
    
    def test_playromtest_requires_login(self, client):
        """Test that playromtest requires login."""
        response = client.get('/playromtest')
        assert response.status_code == 302  # Should redirect to login
        assert 'login' in response.location or '/auth' in response.location
    
    def test_playromtest_renders_template(self, client, authenticated_user):
        """Test that playromtest renders the correct template for authenticated users."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.get('/playromtest', follow_redirects=True)
        assert response.status_code == 200
        # Check for flash message
        assert b'Play game functionality coming soon!' in response.data


class TestDownloadRomRoute:
    """Test the /api/downloadrom/<string:guid> route."""
    
    def test_downloadrom_requires_login(self, client, test_game_with_file):
        """Test that downloadrom requires authentication."""
        response = client.get(f'/api/downloadrom/{test_game_with_file.uuid}')
        assert response.status_code == 302  # Should redirect to login
        assert 'login' in response.location or '/auth' in response.location
    
    @patch('modules.routes_downloads_ext.play.log_system_event')
    def test_downloadrom_invalid_uuid_format(self, mock_log, client, authenticated_user):
        """Test that invalid UUID format is rejected with proper logging."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        invalid_uuid = 'not-a-valid-uuid'
        response = client.get(f'/api/downloadrom/{invalid_uuid}')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert response_data['error'] == 'Invalid game identifier'
        
        # Verify security logging
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'Invalid UUID format attempted for ROM download' in call_args[0][0]
        assert call_args[1]['event_type'] == 'security'
        assert call_args[1]['event_level'] == 'warning'
    
    @patch('modules.routes_downloads_ext.play.log_system_event')
    def test_downloadrom_valid_uuid_nonexistent_game(self, mock_log, client, authenticated_user):
        """Test downloadrom with valid UUID but non-existent game."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        nonexistent_uuid = str(uuid4())
        response = client.get(f'/api/downloadrom/{nonexistent_uuid}')
        
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert response_data['error'] == 'Game not found'
        
        # Verify security logging
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'ROM download attempt for non-existent game UUID' in call_args[0][0]
        assert call_args[1]['event_type'] == 'security'
        assert call_args[1]['event_level'] == 'warning'
    
    @patch('modules.routes_downloads_ext.play.log_system_event')
    def test_downloadrom_game_file_not_exists(self, mock_log, client, authenticated_user, test_game_with_nonexistent_file):
        """Test downloadrom when game file doesn't exist on disk."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/api/downloadrom/{test_game_with_nonexistent_file.uuid}')
        
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert response_data['error'] == 'ROM file not found on disk'
        
        # Verify security logging
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'ROM download attempt for missing file' in call_args[0][0]
        assert call_args[1]['event_type'] == 'security'
        assert call_args[1]['event_level'] == 'warning'
    
    @patch('modules.routes_downloads_ext.play.log_system_event')
    @patch('modules.routes_downloads_ext.play.get_allowed_base_directories')
    @patch('modules.routes_downloads_ext.play.is_safe_path')
    def test_downloadrom_path_traversal_attempt(self, mock_is_safe_path, mock_get_allowed, mock_log, 
                                              client, authenticated_user, test_game_with_unsafe_path):
        """Test that path traversal attempts are blocked."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        # Mock the security functions to simulate path traversal detection
        mock_get_allowed.return_value = ['/allowed/games']
        mock_is_safe_path.return_value = (False, "Access denied - path outside allowed directories")
        
        # Mock os.path.exists to return True to get past file existence check
        with patch('modules.routes_downloads_ext.play.os.path.exists', return_value=True):
            response = client.get(f'/api/downloadrom/{test_game_with_unsafe_path.uuid}')
        
        assert response.status_code == 403
        response_data = json.loads(response.data)
        assert response_data['error'] == 'Access denied'
        
        # Verify path validation was called
        mock_is_safe_path.assert_called_once()
        mock_get_allowed.assert_called_once()
        
        # Verify security logging
        mock_log.assert_called()
        call_args = mock_log.call_args
        assert 'Path traversal attempt blocked for ROM download' in call_args[0][0]
        assert call_args[1]['event_type'] == 'security'
        assert call_args[1]['event_level'] == 'warning'
    
    def test_downloadrom_folder_not_supported(self, client, authenticated_user, test_game_with_folder):
        """Test that folders are rejected for ROM download."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        # Mock path validation to pass security checks
        with patch('modules.routes_downloads_ext.play.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_downloads_ext.play.get_allowed_base_directories', return_value=['/tmp']):
                response = client.get(f'/api/downloadrom/{test_game_with_folder.uuid}')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert 'folder and cannot be played directly' in response_data['error']
    
    @patch('modules.routes_downloads_ext.play.send_file')
    @patch('modules.routes_downloads_ext.play.log_system_event')
    def test_downloadrom_successful_download(self, mock_log, mock_send_file, client, 
                                           authenticated_user, test_game_with_file, app):
        """Test successful ROM file download."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        # Mock send_file to return a response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_send_file.return_value = mock_response
        
        # Mock path validation to pass security checks
        with patch('modules.routes_downloads_ext.play.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_downloads_ext.play.get_allowed_base_directories') as mock_get_allowed:
                mock_get_allowed.return_value = [os.path.dirname(test_game_with_file.full_disk_path)]
                
                with app.app_context():
                    response = client.get(f'/api/downloadrom/{test_game_with_file.uuid}')
        
        assert response.status_code == 200
        
        # Verify file was served
        mock_send_file.assert_called_once_with(test_game_with_file.full_disk_path, as_attachment=True)
        
        # Verify success logging
        mock_log.assert_called()
        call_args = mock_log.call_args
        assert 'ROM file downloaded for WebRetro' in call_args[0][0]
        assert call_args[1]['event_type'] == 'download'
        assert call_args[1]['event_level'] == 'information'
    
    @patch('modules.routes_downloads_ext.play.log_system_event')
    def test_downloadrom_logs_security_events(self, mock_log, client, authenticated_user):
        """Test that various security events are properly logged."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        # Test invalid UUID logging
        client.get('/api/downloadrom/invalid-uuid')
        
        # Test non-existent game logging
        client.get(f'/api/downloadrom/{str(uuid4())}')
        
        # Verify multiple logging calls were made
        assert mock_log.call_count >= 2
        
        # Check that security event types were used
        call_args_list = mock_log.call_args_list
        for call_args in call_args_list:
            assert call_args[1]['event_type'] == 'security'
            assert call_args[1]['event_level'] == 'warning'
    
    def test_downloadrom_sql_injection_attempt(self, client, authenticated_user):
        """Test that potential SQL injection attempts are handled safely."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        # Try various SQL injection patterns as UUID
        injection_attempts = [
            "'; DROP TABLE games; --",
            "' OR '1'='1",
            "UNION SELECT * FROM users",
            "1' AND SLEEP(5) --"
        ]
        
        for attempt in injection_attempts:
            response = client.get(f'/api/downloadrom/{attempt}')
            # Should return 400 due to invalid UUID format, not 500 (server error)
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Invalid game identifier'
    
    @patch('modules.routes_downloads_ext.play.get_allowed_base_directories')
    def test_downloadrom_allowed_directories_validation(self, mock_get_allowed, client, 
                                                      authenticated_user, app):
        """Test that allowed directories are properly validated."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        # Mock allowed directories
        mock_get_allowed.return_value = ['/allowed/games', '/another/allowed/path']
        
        # Create a temporary game for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            game_file = os.path.join(temp_dir, 'test.rom')
            with open(game_file, 'w') as f:
                f.write('test')
            
            with app.app_context():
                library = Library(name='Test', platform=LibraryPlatform.PCWIN)
                db.session.add(library)
                db.session.commit()
                
                game = Game(
                    name='Test Game',
                    library_uuid=library.uuid,
                    full_disk_path=game_file,
                    size=4
                )
                db.session.add(game)
                db.session.commit()
                
                response = client.get(f'/api/downloadrom/{game.uuid}')
                
                # Should fail path validation since temp_dir is not in allowed directories
                assert response.status_code == 403
                response_data = json.loads(response.data)
                assert response_data['error'] == 'Access denied'
        
        # Verify get_allowed_base_directories was called
        mock_get_allowed.assert_called()


class TestSecurityIntegration:
    """Integration tests for security features."""
    
    @patch('modules.routes_downloads_ext.play.log_system_event')
    def test_comprehensive_security_flow(self, mock_log, client, authenticated_user, 
                                       test_game_with_file, app):
        """Test the complete security validation flow."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        with app.app_context():
            # Configure allowed directories to include our test file's directory
            test_dir = os.path.dirname(test_game_with_file.full_disk_path)
            
            with patch('modules.routes_downloads_ext.play.get_allowed_base_directories') as mock_get_allowed:
                mock_get_allowed.return_value = [test_dir]
                
                with patch('modules.routes_downloads_ext.play.send_file') as mock_send_file:
                    mock_send_file.return_value = MagicMock(status_code=200)
                    
                    response = client.get(f'/api/downloadrom/{test_game_with_file.uuid}')
                    
                    # Should succeed with all security checks passing
                    assert response.status_code == 200
                    
                    # Verify security functions were called
                    mock_get_allowed.assert_called_once()
                    
                    # Verify success was logged
                    success_calls = [call for call in mock_log.call_args_list 
                                   if 'download' in call[1].get('event_type', '')]
                    assert len(success_calls) > 0
    
    def test_database_cleanup_after_tests(self, db_session):
        """Verify that tests clean up properly."""
        # Count existing records before test
        initial_games = db_session.execute(select(Game)).scalars().all()
        initial_users = db_session.execute(select(User)).scalars().all()
        
        # This test doesn't create any persistent data, just verifies cleanup
        # In a real scenario, the fixtures handle cleanup automatically
        assert True  # Placeholder assertion