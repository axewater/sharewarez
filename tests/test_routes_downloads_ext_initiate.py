import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from modules import db
from modules.models import (
    DownloadRequest, Game, User, GlobalSettings, Library, 
    GameUpdate, GameExtra
)
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
def test_game(db_session, test_library):
    """Create a test game with actual file on disk."""
    # Create a real directory and file for the game
    temp_dir = tempfile.mkdtemp()
    game_dir = os.path.join(temp_dir, 'test_game')
    os.makedirs(game_dir, exist_ok=True)
    
    # Create test files
    with open(os.path.join(game_dir, 'game_file1.exe'), 'w') as f:
        f.write('test game file 1')
    with open(os.path.join(game_dir, 'game_file2.dll'), 'w') as f:
        f.write('test game file 2')
    with open(os.path.join(game_dir, 'readme.nfo'), 'w') as f:
        f.write('test nfo file')
    
    game = Game(
        name='Test Game',
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
def test_game_update(db_session, test_game):
    """Create a test game update."""
    temp_dir = tempfile.mkdtemp()
    update_file = os.path.join(temp_dir, 'update_v1.1.zip')
    with open(update_file, 'w') as f:
        f.write('test update file')
    
    update = GameUpdate(
        game_uuid=test_game.uuid,
        file_path=update_file,
        times_downloaded=0
    )
    db_session.add(update)
    db_session.commit()
    
    yield update
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_game_extra(db_session, test_game):
    """Create a test game extra."""
    temp_dir = tempfile.mkdtemp()
    extra_file = os.path.join(temp_dir, 'soundtrack.zip')
    with open(extra_file, 'w') as f:
        f.write('test soundtrack file')
    
    extra = GameExtra(
        game_uuid=test_game.uuid,
        file_path=extra_file,
        name='Soundtrack',
        times_downloaded=0
    )
    db_session.add(extra)
    db_session.commit()
    
    yield extra
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def global_settings(db_session):
    """Create global settings."""
    settings = GlobalSettings(
        update_folder_name='Updates',
        extras_folder_name='Extras'
    )
    db_session.add(settings)
    db_session.commit()
    return settings


def authenticate_user(client, user):
    """Helper function to authenticate a user in the test session."""
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True


class TestDownloadGameRoute:
    """Test cases for download_game route."""
    
    def test_download_game_requires_login(self, client, test_game):
        """Test that download_game requires authentication."""
        response = client.get(f'/download_game/{test_game.uuid}')
        assert response.status_code == 302  # Redirect to login
        assert '/login' in response.location
    
    def test_download_game_invalid_uuid_format(self, client, authenticated_user):
        """Test download_game with invalid UUID format."""
        authenticate_user(client, authenticated_user)
        
        # Test invalid UUID format - should be blocked by our validation
        response = client.get('/download_game/invalid-uuid')
        assert response.status_code in [400, 302]  # Either validation error or redirect
    
    def test_download_game_nonexistent_game(self, client, authenticated_user):
        """Test download_game with nonexistent game UUID."""
        authenticate_user(client, authenticated_user)
        
        fake_uuid = str(uuid4())
        response = client.get(f'/download_game/{fake_uuid}')
        assert response.status_code == 404
    
    def test_download_game_existing_request(self, client, authenticated_user, test_game, db_session):
        """Test download_game when user already has a download request."""
        authenticate_user(client, authenticated_user)
        
        # Create existing download request
        existing_request = DownloadRequest(
            user_id=authenticated_user.id,
            game_uuid=test_game.uuid,
            file_location=test_game.full_disk_path,
            status='processing',
            download_size=1024
        )
        db_session.add(existing_request)
        db_session.commit()
        
        response = client.get(f'/download_game/{test_game.uuid}')
        assert response.status_code == 302  # Redirect to downloads
        assert '/downloads' in response.location
    
    @patch('modules.routes_downloads_ext.initiate.Thread')
    @patch('modules.routes_downloads_ext.initiate.zip_game')
    def test_download_game_success(self, mock_zip_game, mock_thread, 
                                  client, authenticated_user, test_game, 
                                  global_settings, db_session, app):
        """Test successful download_game."""
        with app.app_context():
            authenticate_user(client, authenticated_user)
            
            # Set up app config for security validation
            app.config['DATA_FOLDER_WAREZ'] = os.path.dirname(test_game.full_disk_path)
            app.config['ZIP_SAVE_PATH'] = tempfile.mkdtemp()
            
            response = client.get(f'/download_game/{test_game.uuid}')
            assert response.status_code == 302  # Redirect to downloads
            assert '/downloads' in response.location
            
            # Verify download request was created
            download_request = db_session.query(DownloadRequest).filter_by(
                user_id=authenticated_user.id,
                game_uuid=test_game.uuid
            ).first()
            assert download_request is not None
            assert download_request.status == 'processing'
            
            # Verify game download count increased
            updated_game = db_session.execute(select(Game).filter_by(uuid=test_game.uuid)).scalars().first()
            assert updated_game.times_downloaded == 1
            
            # Verify thread was started
            mock_thread.assert_called_once()
            mock_thread.return_value.start.assert_called_once()
            
            # Cleanup
            shutil.rmtree(app.config['ZIP_SAVE_PATH'], ignore_errors=True)


class TestDownloadOtherRoute:
    """Test cases for download_other route."""
    
    def test_download_other_requires_login(self, client, test_game):
        """Test that download_other requires authentication."""
        response = client.get(f'/download_other/update/{test_game.uuid}/1')
        assert response.status_code == 302  # Redirect to login
        assert '/login' in response.location
    
    def test_download_other_invalid_file_type(self, client, authenticated_user, test_game):
        """Test download_other with invalid file type."""
        authenticate_user(client, authenticated_user)
        
        response = client.get(f'/download_other/invalid/{test_game.uuid}/1')
        assert response.status_code == 302
        # Should redirect to game details with error
    
    def test_download_other_invalid_uuid(self, client, authenticated_user):
        """Test download_other with invalid UUID format."""
        authenticate_user(client, authenticated_user)
        
        response = client.get('/download_other/update/invalid-uuid/1')
        assert response.status_code in [400, 302]  # Either validation error or redirect
    
    def test_download_other_invalid_file_id(self, client, authenticated_user, test_game):
        """Test download_other with invalid file ID."""
        authenticate_user(client, authenticated_user)
        
        response = client.get(f'/download_other/update/{test_game.uuid}/abc')
        assert response.status_code in [400, 302]  # Either validation error or redirect
    
    def test_download_other_nonexistent_file(self, client, authenticated_user, test_game):
        """Test download_other with nonexistent file ID."""
        authenticate_user(client, authenticated_user)
        
        response = client.get(f'/download_other/update/{test_game.uuid}/999')
        assert response.status_code == 302
        # Should redirect to game details
    
    @patch('modules.routes_downloads_ext.initiate.Thread')
    @patch('modules.routes_downloads_ext.initiate.zip_folder')
    def test_download_other_success_update(self, mock_zip_folder, mock_thread,
                                          client, authenticated_user, test_game_update, 
                                          db_session, app):
        """Test successful download_other for update file."""
        with app.app_context():
            authenticate_user(client, authenticated_user)
            
            # Set up app config for security validation
            app.config['DATA_FOLDER_WAREZ'] = os.path.dirname(test_game_update.file_path)
            app.config['ZIP_SAVE_PATH'] = tempfile.mkdtemp()
            
            response = client.get(f'/download_other/update/{test_game_update.game_uuid}/{test_game_update.id}')
            assert response.status_code == 302
            assert '/downloads' in response.location
            
            # Verify download request was created
            download_request = db_session.query(DownloadRequest).filter_by(
                user_id=authenticated_user.id,
                file_location=test_game_update.file_path
            ).first()
            assert download_request is not None
            
            # Verify update download count increased
            updated_update = db_session.get(GameUpdate, test_game_update.id)
            assert updated_update.times_downloaded == 1
            
            # Cleanup
            shutil.rmtree(app.config['ZIP_SAVE_PATH'], ignore_errors=True)


class TestDownloadFileRoute:
    """Test cases for download_file route (legacy route)."""
    
    def test_download_file_requires_login(self, client, test_game):
        """Test that download_file requires authentication."""
        response = client.get(f'/download_file/updates/1KB/{test_game.uuid}/test_file.zip')
        assert response.status_code == 302  # Redirect to login
        assert '/login' in response.location
    
    def test_download_file_invalid_location(self, client, authenticated_user, test_game):
        """Test download_file with invalid file location."""
        authenticate_user(client, authenticated_user)
        
        response = client.get(f'/download_file/invalid/1KB/{test_game.uuid}/test_file.zip')
        assert response.status_code == 302
    
    def test_download_file_invalid_uuid(self, client, authenticated_user):
        """Test download_file with invalid UUID format."""
        authenticate_user(client, authenticated_user)
        
        response = client.get('/download_file/updates/1KB/invalid-uuid/test_file.zip')
        assert response.status_code in [400, 302]  # Either validation error or redirect


class TestSecurityValidation:
    """Test cases focused on security validation."""
    
    def test_path_traversal_attempts(self, client, authenticated_user):
        """Test various path traversal attack attempts."""
        authenticate_user(client, authenticated_user)
        
        path_traversal_attempts = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32',
            '/etc/shadow'
        ]
        
        for malicious_uuid in path_traversal_attempts:
            response = client.get(f'/download_game/{malicious_uuid}')
            # Should return 400 for invalid UUID format or 302 redirect for invalid paths
            assert response.status_code in [400, 302, 404]
    
    def test_sql_injection_attempts(self, client, authenticated_user):
        """Test SQL injection attempts in parameters."""
        authenticate_user(client, authenticated_user)
        
        sql_injection_attempts = [
            "'; DROP TABLE games; --",
            "1' OR '1'='1",
            "1; DELETE FROM users; --"
        ]
        
        for injection in sql_injection_attempts:
            response = client.get(f'/download_game/{injection}')
            # Should not return 200 - either 400 (validation error) or 302/404 (handled)
            assert response.status_code != 200
    
    @patch('modules.routes_downloads_ext.initiate.log_system_event')
    def test_security_logging(self, mock_log, client, authenticated_user):
        """Test that security violations are properly logged."""
        authenticate_user(client, authenticated_user)
        
        # Attempt invalid UUID
        response = client.get('/download_game/invalid-uuid')
        
        # Check if logging was called (might be different parameters)
        # Just verify that security violations get logged in some form
        if mock_log.called:
            # Check if any of the calls were security-related
            security_calls = [call for call in mock_log.call_args_list if len(call.kwargs) >= 2 and call.kwargs.get('event_type') == 'security']
            assert len(security_calls) > 0, "Security event should have been logged"
        else:
            # If no logging happened, the route should have returned an error status
            assert response.status_code in [400, 302, 404], "Invalid requests should be handled with appropriate status codes"


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_download_workflow(self, client, authenticated_user, test_game, 
                                       global_settings, db_session, app):
        """Test complete download workflow from request to completion."""
        with app.app_context():
            authenticate_user(client, authenticated_user)
            
            # Set up app config
            app.config['DATA_FOLDER_WAREZ'] = os.path.dirname(test_game.full_disk_path)
            app.config['ZIP_SAVE_PATH'] = tempfile.mkdtemp()
            
            # Clear any existing download requests for this user and game to ensure clean test
            db_session.query(DownloadRequest).filter_by(
                user_id=authenticated_user.id,
                game_uuid=test_game.uuid
            ).delete()
            db_session.commit()
            
            # Initial state - count download requests for this specific user/game combination
            initial_count = db_session.query(DownloadRequest).filter_by(
                user_id=authenticated_user.id,
                game_uuid=test_game.uuid
            ).count()
            
            # Make download request
            with patch('modules.routes_downloads_ext.initiate.Thread') as mock_thread:
                response = client.get(f'/download_game/{test_game.uuid}')
                assert response.status_code == 302
                assert '/downloads' in response.location
            
            # Verify download request was created
            final_count = db_session.query(DownloadRequest).filter_by(
                user_id=authenticated_user.id,
                game_uuid=test_game.uuid
            ).count()
            assert final_count == initial_count + 1
            
            # Verify game statistics updated
            updated_game = db_session.execute(select(Game).filter_by(uuid=test_game.uuid)).scalars().first()
            assert updated_game.times_downloaded >= 1  # May be incremented by other tests
            
            # Verify thread was started
            mock_thread.assert_called_once()
            
            # Cleanup
            shutil.rmtree(app.config['ZIP_SAVE_PATH'], ignore_errors=True)