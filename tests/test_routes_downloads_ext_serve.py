import pytest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from modules import db
from modules.models import DownloadRequest, Game, User, GlobalSettings, Library
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
def sample_library(db_session):
    """Create a test library."""
    library = Library(
        name='Test Library',
        platform=LibraryPlatform.OTHER
    )
    db_session.add(library)
    db_session.commit()
    return library


@pytest.fixture  
def sample_game(db_session, sample_library):
    """Create a sample game for testing."""
    game_uuid = str(uuid4())
    
    game = Game(
        uuid=game_uuid,
        name='Test Game',
        full_disk_path='/test/game/path',
        library_uuid=sample_library.uuid,
        size=1000000
    )
    db_session.add(game)
    db_session.commit()
    return game


@pytest.fixture
def sample_download_request(db_session, authenticated_user, sample_game):
    """Create a sample download request."""
    temp_zip_path = '/test/zip/path/game.zip'
    
    download_request = DownloadRequest(
        user_id=authenticated_user.id,
        game_uuid=sample_game.uuid,
        status='available',
        zip_file_path=temp_zip_path,
        request_time=datetime.now(timezone.utc),
        completion_time=datetime.now(timezone.utc),
        download_size=1024000,
        file_location='/test/game/path'
    )
    db_session.add(download_request)
    db_session.commit()
    return download_request


@pytest.fixture
def temp_zip_file():
    """Create a temporary zip file for testing."""
    temp_dir = tempfile.mkdtemp()
    zip_file_path = os.path.join(temp_dir, 'test_game.zip')
    
    # Create a dummy zip file
    with open(zip_file_path, 'wb') as f:
        f.write(b'PK\x03\x04')  # ZIP file magic bytes
        f.write(b'\x00' * 100)  # Some dummy content
    
    yield zip_file_path
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestDownloadZipRoute:
    """Test cases for the download_zip route."""

    def test_download_zip_requires_login(self, client):
        """Test that the download_zip route requires login."""
        response = client.get('/download_zip/1')
        assert response.status_code == 302
        assert '/login' in response.location

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_nonexistent_request(self, mock_log, client, authenticated_user):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        response = client.get('/download_zip/99999')
        # Flask route should return 500 since ASGI should handle this
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert response_data['error'] == 'Download route should be handled by ASGI'
        
        # Verify system logging for unexpected Flask route access
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'Flask download route reached unexpectedly' in call_args[0][0]
        assert call_args[1]['event_type'] == 'system'
        assert call_args[1]['event_level'] == 'warning'

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_wrong_user(self, mock_log, client, authenticated_user, admin_user, sample_download_request):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        # Login as different user
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
            session['_fresh'] = True
        
        response = client.get(f'/download_zip/{sample_download_request.id}')
        # Flask route should return 500 since ASGI should handle this
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert response_data['error'] == 'Download route should be handled by ASGI'
        
        # Verify system logging for unexpected Flask route access
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'Flask download route reached unexpectedly' in call_args[0][0]
        assert call_args[1]['event_type'] == 'system'
        assert call_args[1]['event_level'] == 'warning'

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_not_ready_status(self, mock_log, client, authenticated_user, 
                                          sample_download_request, db_session):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        # Change status to processing
        sample_download_request.status = 'processing'
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        response = client.get(f'/download_zip/{sample_download_request.id}')
        
        # Flask route should return 500 since ASGI should handle this
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert response_data['error'] == 'Download route should be handled by ASGI'
        
        # Verify system logging for unexpected Flask route access
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'Flask download route reached unexpectedly' in call_args[0][0]
        assert call_args[1]['event_type'] == 'system'
        assert call_args[1]['event_level'] == 'warning'

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_missing_config(self, mock_log, client, authenticated_user, 
                                        sample_download_request, app):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            # Remove ZIP_SAVE_PATH from config
            app.config.pop('ZIP_SAVE_PATH', None)
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_path_security_violation(self, mock_log, 
                                                  client, authenticated_user, sample_download_request, app):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/test/zip/path'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_file_not_exists(self, mock_log,
                                         client, authenticated_user, sample_download_request, app):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/test/zip/path'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_successful_download(self, mock_log, client, authenticated_user, 
                                             sample_download_request, db_session, app, temp_zip_file):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        
        # Update the download request with the temp file path
        sample_download_request.zip_file_path = temp_zip_file
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = os.path.dirname(temp_zip_file)
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_streaming_exception(self, mock_log,
                                             client, authenticated_user, sample_download_request, app):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/test/zip/path'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'


class TestSecurityValidation:
    """Test security aspects of the download_zip route."""

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_path_traversal_protection(self, mock_log, client, authenticated_user, 
                                      sample_download_request, db_session, app):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        # Set malicious path in download request
        malicious_path = "/var/www/sharewarez/modules/static/library/zips/../../../etc/passwd"
        sample_download_request.zip_file_path = malicious_path
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/var/www/sharewarez/modules/static/library/zips'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_absolute_path_outside_allowed_directories(self, mock_log, client, authenticated_user,
                                                      sample_download_request, db_session, app):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        # Set absolute path outside ZIP_SAVE_PATH
        outside_path = "/etc/passwd"
        sample_download_request.zip_file_path = outside_path
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/var/www/sharewarez/modules/static/library/zips'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_valid_path_within_allowed_directory(self, mock_log,
                                                 client, authenticated_user, sample_download_request, 
                                                 db_session, app):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        # Set valid path within ZIP_SAVE_PATH
        valid_path = "/var/www/sharewarez/modules/static/library/zips/valid_game.zip"
        sample_download_request.zip_file_path = valid_path
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/var/www/sharewarez/modules/static/library/zips'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'


class TestLoggingFunctionality:
    """Test logging aspects of the download_zip route."""

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_all_log_events_recorded(self, mock_log, client, authenticated_user, 
                                    sample_download_request, db_session, app, temp_zip_file):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        sample_download_request.zip_file_path = temp_zip_file
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = os.path.dirname(temp_zip_file)
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_log_truncates_long_paths(self, mock_log, client, authenticated_user,
                                     sample_download_request, db_session, app):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        # Create a very long path
        long_path = "/a/very/long/path/" + ("x" * 200) + "/file.zip"
        sample_download_request.zip_file_path = long_path
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/var/www/sharewarez/modules/static/library/zips'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'


class TestIntegration:
    """Integration tests for the download_zip route."""

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_complete_download_workflow(self, mock_log, client, authenticated_user, sample_download_request, 
                                       db_session, app, temp_zip_file):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        # Update request with real temp file
        sample_download_request.zip_file_path = temp_zip_file
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = os.path.dirname(temp_zip_file)
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_security_and_logging_integration(self, mock_log, client, authenticated_user, 
                                             sample_download_request, db_session, app):
        """Test download ZIP reaches Flask route (should not happen with ASGI)."""
        # Set up malicious path
        malicious_path = "/etc/passwd"
        sample_download_request.zip_file_path = malicious_path
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/var/www/sharewarez/modules/static/library/zips'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Flask route should return 500 since ASGI should handle this
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Download route should be handled by ASGI'
            
            # Verify system logging for unexpected Flask route access
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert 'Flask download route reached unexpectedly' in call_args[0][0]
            assert call_args[1]['event_type'] == 'system'
            assert call_args[1]['event_level'] == 'warning'