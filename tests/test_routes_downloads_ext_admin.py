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

        response = client.get('/admin/manage-downloads')
        assert response.status_code == 200
        assert b'admin_manage_downloads' in response.data or b'manage' in response.data

    def test_manage_downloads_displays_data(self, client, admin_user, sample_download_request):
        """Test that manage downloads displays download requests."""
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)

        response = client.get('/admin/manage-downloads')
        assert response.status_code == 200

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

    @patch('modules.routes_downloads_ext.admin.log_system_event')
    def test_delete_download_request_success(self, mock_log, client, admin_user, sample_download_request, app):
        """Test successful deletion of download request."""
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_user.id)

        response = client.post(f'/delete_download_request/{sample_download_request.id}')
        assert response.status_code == 302  # Should redirect

        # Verify the download request was deleted from database
        deleted_request = db.session.get(DownloadRequest, sample_download_request.id)
        assert deleted_request is None

        # Verify logging was called
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
        response = client.get('/admin/manage-downloads')
        assert response.status_code == 200

        # 2. Delete completed request
        with patch('modules.routes_downloads_ext.admin.log_system_event'):
            response = client.post(f'/delete_download_request/{completed_request.id}')
            assert response.status_code == 302

            # Verify request was deleted
            deleted_request = db.session.get(DownloadRequest, completed_request.id)
            assert deleted_request is None

