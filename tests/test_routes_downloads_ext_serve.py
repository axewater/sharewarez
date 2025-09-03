import pytest
import os
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

    def test_download_zip_nonexistent_request(self, client, authenticated_user):
        """Test download with non-existent download request."""
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        response = client.get('/download_zip/99999')
        assert response.status_code == 404

    def test_download_zip_wrong_user(self, client, authenticated_user, admin_user, sample_download_request):
        """Test that users can only download their own requests."""
        # Login as different user
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
            session['_fresh'] = True
        
        response = client.get(f'/download_zip/{sample_download_request.id}')
        assert response.status_code == 404

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_not_ready_status(self, mock_log, client, authenticated_user, 
                                          sample_download_request, db_session):
        """Test download when request status is not 'available'."""
        # Change status to processing
        sample_download_request.status = 'processing'
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        response = client.get(f'/download_zip/{sample_download_request.id}')
        
        assert response.status_code == 302
        assert '/library' in response.location
        
        # Verify logging
        mock_log.assert_any_call(f"Download attempt for ID: {sample_download_request.id}", 
                                event_type='download', event_level='information')
        mock_log.assert_any_call(f"Download blocked - not ready: {sample_download_request.id}", 
                                event_type='download', event_level='warning')

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_missing_config(self, mock_log, client, authenticated_user, 
                                        sample_download_request, app):
        """Test download when ZIP_SAVE_PATH is not configured."""
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            # Remove ZIP_SAVE_PATH from config
            app.config.pop('ZIP_SAVE_PATH', None)
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            assert response.status_code == 302
            assert '/library' in response.location
            
            # Verify logging
            mock_log.assert_any_call("ZIP_SAVE_PATH not configured", 
                                   event_type='system', event_level='error')

    @patch('modules.routes_downloads_ext.serve.is_safe_path')
    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_path_security_violation(self, mock_log, mock_is_safe_path, 
                                                  client, authenticated_user, sample_download_request, app):
        """Test download with unsafe file path."""
        mock_is_safe_path.return_value = (False, "Path outside allowed directories")
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/test/zip/path'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            assert response.status_code == 302
            assert '/library' in response.location
            
            # Verify security logging
            mock_log.assert_any_call(
                f"Security violation - path outside allowed directories: {sample_download_request.zip_file_path}",
                event_type='security', event_level='warning'
            )

    @patch('modules.routes_downloads_ext.serve.os.path.exists')
    @patch('modules.routes_downloads_ext.serve.is_safe_path')
    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_file_not_exists(self, mock_log, mock_is_safe_path, mock_exists,
                                         client, authenticated_user, sample_download_request, app):
        """Test download when file doesn't exist on disk."""
        mock_is_safe_path.return_value = (True, None)
        mock_exists.return_value = False
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/test/zip/path'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            assert response.status_code == 302
            assert '/library' in response.location
            
            # Verify logging
            mock_log.assert_any_call(
                f"Download failed - file not found: {sample_download_request.zip_file_path}",
                event_type='download', event_level='error'
            )

    @patch('modules.routes_downloads_ext.serve.send_from_directory')
    @patch('modules.routes_downloads_ext.serve.os.path.exists')
    @patch('modules.routes_downloads_ext.serve.is_safe_path')
    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_successful_download(self, mock_log, mock_is_safe_path, mock_exists, 
                                             mock_send_from_directory, client, authenticated_user, 
                                             sample_download_request, db_session, app, temp_zip_file):
        """Test successful file download."""
        mock_is_safe_path.return_value = (True, None)
        mock_exists.return_value = True
        mock_send_from_directory.return_value = MagicMock()
        
        # Update the download request with the temp file path
        sample_download_request.zip_file_path = temp_zip_file
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = os.path.dirname(temp_zip_file)
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Verify send_from_directory was called correctly
            expected_directory = os.path.dirname(temp_zip_file)
            expected_filename = os.path.basename(temp_zip_file)
            mock_send_from_directory.assert_called_once_with(
                expected_directory, expected_filename, as_attachment=True
            )
            
            # Verify success logging
            mock_log.assert_any_call(f"File downloaded: {expected_filename}", 
                                   event_type='download', event_level='information')

    @patch('modules.routes_downloads_ext.serve.send_from_directory')
    @patch('modules.routes_downloads_ext.serve.os.path.exists')
    @patch('modules.routes_downloads_ext.serve.is_safe_path')
    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_send_from_directory_exception(self, mock_log, mock_is_safe_path, 
                                                       mock_exists, mock_send_from_directory,
                                                       client, authenticated_user, sample_download_request, app):
        """Test handling of send_from_directory exceptions."""
        mock_is_safe_path.return_value = (True, None)
        mock_exists.return_value = True
        mock_send_from_directory.side_effect = Exception("File permission error")
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/test/zip/path'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            assert response.status_code == 302
            assert '/library' in response.location
            
            # Verify error logging
            mock_log.assert_any_call(
                f"Download error for {sample_download_request.id}: File permission error",
                event_type='download', event_level='error'
            )


class TestSecurityValidation:
    """Test security aspects of the download_zip route."""

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_path_traversal_protection(self, mock_log, client, authenticated_user, 
                                      sample_download_request, db_session, app):
        """Test protection against path traversal attacks."""
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
            
            assert response.status_code == 302
            assert '/library' in response.location
            
            # Verify security violation was logged
            mock_log.assert_any_call(
                f"Security violation - path outside allowed directories: {malicious_path}",
                event_type='security', event_level='warning'
            )

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_absolute_path_outside_allowed_directories(self, mock_log, client, authenticated_user,
                                                      sample_download_request, db_session, app):
        """Test rejection of absolute paths outside allowed directories."""
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
            
            assert response.status_code == 302
            assert '/library' in response.location
            
            # Verify security violation was logged
            mock_log.assert_any_call(
                f"Security violation - path outside allowed directories: {outside_path}",
                event_type='security', event_level='warning'
            )

    @patch('modules.routes_downloads_ext.serve.send_from_directory')
    @patch('modules.routes_downloads_ext.serve.os.path.exists')
    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_valid_path_within_allowed_directory(self, mock_log, mock_exists, mock_send_from_directory,
                                                 client, authenticated_user, sample_download_request, 
                                                 db_session, app):
        """Test that valid paths within allowed directories are accepted."""
        # Set valid path within ZIP_SAVE_PATH
        valid_path = "/var/www/sharewarez/modules/static/library/zips/valid_game.zip"
        sample_download_request.zip_file_path = valid_path
        db_session.commit()
        
        mock_exists.return_value = True
        mock_send_from_directory.return_value = MagicMock()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/var/www/sharewarez/modules/static/library/zips'
            
            response = client.get(f'/download_zip/{sample_download_request.id}')
            
            # Should succeed - send_from_directory should be called
            mock_send_from_directory.assert_called_once()
            
            # Verify success logging
            mock_log.assert_any_call("File downloaded: valid_game.zip", 
                                   event_type='download', event_level='information')


class TestLoggingFunctionality:
    """Test logging aspects of the download_zip route."""

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_all_log_events_recorded(self, mock_log, client, authenticated_user, 
                                    sample_download_request, db_session, app, temp_zip_file):
        """Test that all expected log events are recorded during successful download."""
        sample_download_request.zip_file_path = temp_zip_file
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = os.path.dirname(temp_zip_file)
            
            with patch('modules.routes_downloads_ext.serve.send_from_directory') as mock_send:
                mock_send.return_value = MagicMock()
                
                response = client.get(f'/download_zip/{sample_download_request.id}')
                
                # Verify all expected log calls
                expected_calls = [
                    call(f"Download attempt for ID: {sample_download_request.id}", 
                         event_type='download', event_level='information'),
                    call(f"File downloaded: {os.path.basename(temp_zip_file)}", 
                         event_type='download', event_level='information')
                ]
                
                mock_log.assert_has_calls(expected_calls)

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_log_truncates_long_paths(self, mock_log, client, authenticated_user,
                                     sample_download_request, db_session, app):
        """Test that log messages truncate very long file paths."""
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
            
            # Find the security violation log call
            security_call = None
            for call_args in mock_log.call_args_list:
                if 'Security violation' in str(call_args):
                    security_call = call_args
                    break
            
            assert security_call is not None
            # Verify path was truncated to 100 characters
            logged_message = security_call[0][0]
            path_part = logged_message.split(': ')[1]
            assert len(path_part) <= 100


class TestIntegration:
    """Integration tests for the download_zip route."""

    def test_complete_download_workflow(self, client, authenticated_user, sample_download_request, 
                                       db_session, app, temp_zip_file):
        """Test the complete workflow from request to file delivery."""
        # Update request with real temp file
        sample_download_request.zip_file_path = temp_zip_file
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = os.path.dirname(temp_zip_file)
            
            with patch('modules.routes_downloads_ext.serve.send_from_directory') as mock_send:
                mock_send.return_value = MagicMock()
                
                response = client.get(f'/download_zip/{sample_download_request.id}')
                
                # Verify successful call to send_from_directory
                mock_send.assert_called_once_with(
                    os.path.dirname(temp_zip_file),
                    os.path.basename(temp_zip_file),
                    as_attachment=True
                )

    def test_security_and_logging_integration(self, client, authenticated_user, 
                                             sample_download_request, db_session, app):
        """Test that security validation and logging work together properly."""
        # Set up malicious path
        malicious_path = "/etc/passwd"
        sample_download_request.zip_file_path = malicious_path
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(authenticated_user.id)
            session['_fresh'] = True
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/var/www/sharewarez/modules/static/library/zips'
            
            with patch('modules.routes_downloads_ext.serve.log_system_event') as mock_log:
                response = client.get(f'/download_zip/{sample_download_request.id}')
                
                # Should be blocked and logged
                assert response.status_code == 302
                assert '/library' in response.location
                
                # Verify both download attempt and security violation were logged
                download_logged = any('Download attempt' in str(call) for call in mock_log.call_args_list)
                security_logged = any('Security violation' in str(call) for call in mock_log.call_args_list)
                
                assert download_logged
                assert security_logged