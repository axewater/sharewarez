import pytest
import json
from flask import url_for
from unittest.mock import patch, MagicMock
from modules.models import User, DownloadRequest, Game, Library
from modules.platform import LibraryPlatform
from modules import db
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
    """Create a test game."""
    game = Game(
        name='Test Game',
        library_uuid=test_library.uuid
    )
    db_session.add(game)
    db_session.commit()
    return game


@pytest.fixture
def sample_download_request(db_session, regular_user, test_game):
    """Create a sample download request."""
    download_request = DownloadRequest(
        user_id=regular_user.id,
        game_uuid=test_game.uuid,
        status='completed',
        zip_file_path='test_game.zip',
        request_time=datetime.now(timezone.utc)
    )
    db_session.add(download_request)
    db_session.commit()
    return download_request


@pytest.fixture
def processing_download_request(db_session, regular_user, test_game):
    """Create a download request with processing status."""
    download_request = DownloadRequest(
        user_id=regular_user.id,
        game_uuid=test_game.uuid,
        status='processing',
        request_time=datetime.now(timezone.utc)
    )
    db_session.add(download_request)
    db_session.commit()
    return download_request


class TestManageDownloadsRoute:
    """Test the manage downloads admin route."""

    def test_manage_downloads_requires_admin_login(self, client, regular_user):
        """Test that manage downloads requires admin login."""
        with client.session_transaction() as session:
            session['_user_id'] = str(regular_user.id)
        
        response = client.get('/admin/manage-downloads')
        assert response.status_code == 302  # Should redirect due to lack of admin access

    def test_manage_downloads_admin_access(self, client, admin_user):
        """Test that admin can access manage downloads page."""
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        with patch('modules.routes_downloads_ext.admin.get_zip_storage_stats') as mock_stats:
            mock_stats.return_value = (5, 1024000, 2048000)
            
            response = client.get('/admin/manage-downloads')
            assert response.status_code == 200
            assert b'admin_manage_downloads' in response.data or b'manage' in response.data

    @patch('modules.routes_downloads_ext.admin.get_zip_storage_stats')
    def test_manage_downloads_displays_data(self, mock_stats, client, admin_user, sample_download_request):
        """Test that manage downloads displays download requests and storage stats."""
        mock_stats.return_value = (3, 500000, 1000000)
        
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        response = client.get('/admin/manage-downloads')
        assert response.status_code == 200
        mock_stats.assert_called_once()

    def test_manage_downloads_unauthenticated(self, client):
        """Test that unauthenticated users are redirected."""
        response = client.get('/admin/manage-downloads')
        assert response.status_code == 302  # Should redirect to login


class TestDeleteDownloadRequestRoute:
    """Test the delete download request route."""

    def test_delete_requires_admin_login(self, client, regular_user, sample_download_request):
        """Test that delete requires admin login."""
        with client.session_transaction() as session:
            session['_user_id'] = str(regular_user.id)
        
        response = client.post(f'/delete_download_request/{sample_download_request.id}')
        assert response.status_code == 302  # Should redirect due to lack of admin access

    @patch('modules.routes_downloads_ext.admin.delete_zip_file_safely')
    @patch('modules.routes_downloads_ext.admin.log_system_event')
    def test_delete_download_request_success(self, mock_log, mock_delete, client, admin_user, sample_download_request, app):
        """Test successful deletion of download request."""
        mock_delete.return_value = (True, "ZIP file deleted successfully")
        
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/test/zip/path'
            
            response = client.post(f'/delete_download_request/{sample_download_request.id}')
            assert response.status_code == 302  # Should redirect
            
            # Verify the download request was deleted from database
            deleted_request = db.session.get(DownloadRequest, sample_download_request.id)
            assert deleted_request is None
            
            # Verify logging and ZIP deletion were called
            mock_delete.assert_called_once()
            mock_log.assert_called()

    @patch('modules.routes_downloads_ext.admin.delete_zip_file_safely')
    @patch('modules.routes_downloads_ext.admin.log_system_event')
    def test_delete_download_request_zip_deletion_failure(self, mock_log, mock_delete, client, admin_user, sample_download_request, app):
        """Test deletion when ZIP file deletion fails."""
        mock_delete.return_value = (False, "File not found")
        
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/test/zip/path'
            
            response = client.post(f'/delete_download_request/{sample_download_request.id}')
            assert response.status_code == 302
            
            # Verify the download request was still deleted from database
            deleted_request = db.session.get(DownloadRequest, sample_download_request.id)
            assert deleted_request is None
            
            # Verify error was logged
            mock_log.assert_called()

    @patch('modules.routes_downloads_ext.admin.log_system_event')
    def test_delete_download_request_no_zip_save_path(self, mock_log, client, admin_user, sample_download_request, app):
        """Test deletion when ZIP_SAVE_PATH is not configured."""
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        with app.app_context():
            app.config.pop('ZIP_SAVE_PATH', None)  # Remove ZIP_SAVE_PATH
            
            response = client.post(f'/delete_download_request/{sample_download_request.id}')
            assert response.status_code == 302
            
            # Verify the download request was still deleted
            deleted_request = db.session.get(DownloadRequest, sample_download_request.id)
            assert deleted_request is None

    def test_delete_nonexistent_download_request(self, client, admin_user):
        """Test deletion of non-existent download request."""
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        response = client.post('/delete_download_request/99999')
        assert response.status_code == 302  # Should redirect

    def test_delete_download_request_no_zip_file(self, client, admin_user, db_session, regular_user, test_game):
        """Test deletion of download request with no ZIP file path."""
        # Create download request without zip_file_path
        download_request = DownloadRequest(
            user_id=regular_user.id,
            game_uuid=test_game.uuid,
            status='completed',
            zip_file_path=None,  # No ZIP file
            request_time=datetime.now(timezone.utc)
        )
        db_session.add(download_request)
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/delete_download_request/{download_request.id}')
        assert response.status_code == 302
        
        # Verify the download request was deleted
        deleted_request = db.session.get(DownloadRequest, download_request.id)
        assert deleted_request is None

    def test_delete_unauthenticated(self, client, sample_download_request):
        """Test that unauthenticated users cannot delete download requests."""
        response = client.post(f'/delete_download_request/{sample_download_request.id}')
        assert response.status_code == 302  # Should redirect to login


class TestClearProcessingDownloadsRoute:
    """Test the clear processing downloads route."""

    def test_clear_processing_requires_admin_login(self, client, regular_user):
        """Test that clear processing requires admin login."""
        with client.session_transaction() as session:
            session['_user_id'] = str(regular_user.id)
        
        response = client.post('/admin/clear-processing-downloads')
        assert response.status_code == 302  # Should redirect due to lack of admin access

    @patch.object(DownloadRequest, 'error_message', create=True)
    def test_clear_processing_downloads_success(self, mock_error_message, client, admin_user, processing_download_request, db_session):
        """Test successful clearing of processing downloads."""
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        # Verify initial state
        assert processing_download_request.status == 'processing'
        
        response = client.post('/admin/clear-processing-downloads')
        assert response.status_code == 302  # Should redirect
        
        # Refresh the object from database
        db_session.refresh(processing_download_request)
        
        # Verify status was updated
        assert processing_download_request.status == 'failed'
        # Note: error_message field doesn't exist in current model, but test verifies the status change

    @patch.object(DownloadRequest, 'error_message', create=True)
    def test_clear_processing_downloads_multiple(self, mock_error_message, client, admin_user, db_session, regular_user, test_game):
        """Test clearing multiple processing downloads."""
        # Create multiple processing downloads
        downloads = []
        for i in range(3):
            download_request = DownloadRequest(
                user_id=regular_user.id,
                game_uuid=test_game.uuid,
                status='processing',
                request_time=datetime.now(timezone.utc)
            )
            db_session.add(download_request)
            downloads.append(download_request)
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        response = client.post('/admin/clear-processing-downloads')
        assert response.status_code == 302
        
        # Verify all processing downloads were updated
        for download in downloads:
            db_session.refresh(download)
            assert download.status == 'failed'
            # Note: error_message field doesn't exist in current model

    def test_clear_processing_downloads_no_processing_downloads(self, client, admin_user, sample_download_request):
        """Test clearing when no processing downloads exist."""
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        # Ensure sample_download_request is not processing
        assert sample_download_request.status != 'processing'
        
        response = client.post('/admin/clear-processing-downloads')
        assert response.status_code == 302  # Should still succeed

    @patch('modules.routes_downloads_ext.admin.db.session.commit')
    @patch('modules.routes_downloads_ext.admin.log_system_event')
    def test_clear_processing_downloads_database_error(self, mock_log, mock_commit, client, admin_user, processing_download_request):
        """Test handling of database errors during clear processing downloads."""
        mock_commit.side_effect = Exception("Database error")
        
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        response = client.post('/admin/clear-processing-downloads')
        assert response.status_code == 302
        
        # Verify error was logged
        mock_log.assert_called_with('admin_download', 'Error clearing processing downloads: Database error', 'error')

    def test_clear_processing_unauthenticated(self, client):
        """Test that unauthenticated users cannot clear processing downloads."""
        response = client.post('/admin/clear-processing-downloads')
        assert response.status_code == 302  # Should redirect to login


class TestIntegration:
    """Integration tests for admin download management."""

    @patch.object(DownloadRequest, 'error_message', create=True) 
    def test_full_workflow_admin_management(self, mock_error_message, client, admin_user, db_session, regular_user, test_game):
        """Test the full workflow of admin download management."""
        # Create multiple download requests with different statuses
        completed_request = DownloadRequest(
            user_id=regular_user.id,
            game_uuid=test_game.uuid,
            status='completed',
            zip_file_path='completed_game.zip',
            request_time=datetime.now(timezone.utc)
        )
        processing_request = DownloadRequest(
            user_id=regular_user.id,
            game_uuid=test_game.uuid,
            status='processing',
            request_time=datetime.now(timezone.utc)
        )
        db_session.add_all([completed_request, processing_request])
        db_session.commit()
        
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        # 1. View manage downloads page
        with patch('modules.routes_downloads_ext.admin.get_zip_storage_stats') as mock_stats:
            mock_stats.return_value = (2, 1024000, 2048000)
            response = client.get('/admin/manage-downloads')
            assert response.status_code == 200
        
        # 2. Clear processing downloads
        response = client.post('/admin/clear-processing-downloads')
        assert response.status_code == 302
        
        # Verify processing request was updated
        db_session.refresh(processing_request)
        assert processing_request.status == 'failed'
        # Note: error_message field doesn't exist in current model
        
        # 3. Delete completed request
        with patch('modules.routes_downloads_ext.admin.delete_zip_file_safely') as mock_delete:
            with patch('modules.routes_downloads_ext.admin.log_system_event'):
                mock_delete.return_value = (True, "ZIP file deleted successfully")
                
                response = client.post(f'/delete_download_request/{completed_request.id}')
                assert response.status_code == 302
                
                # Verify request was deleted
                deleted_request = db.session.get(DownloadRequest, completed_request.id)
                assert deleted_request is None

    @patch('modules.routes_downloads_ext.admin.delete_zip_file_safely')
    def test_zip_file_safety_warnings(self, mock_delete, client, admin_user, sample_download_request, app):
        """Test that security warnings are properly handled."""
        mock_delete.return_value = (True, "ZIP file not in the expected directory")
        
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)
        
        with app.app_context():
            app.config['ZIP_SAVE_PATH'] = '/test/zip/path'
            
            response = client.post(f'/delete_download_request/{sample_download_request.id}')
            assert response.status_code == 302
            
            # Verify the request was still deleted despite the warning
            deleted_request = db.session.get(DownloadRequest, sample_download_request.id)
            assert deleted_request is None