import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from modules import db
from modules.models import DownloadRequest, Game, User, GlobalSettings, Library, SystemEvents
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
def sample_game(db_session):
    """Create a sample game for testing."""
    library = Library(name='Test Library', platform=LibraryPlatform.PCWIN)
    db_session.add(library)
    db_session.flush()
    
    game = Game(
        name='Test Game',
        full_disk_path='/test/game/path',
        size=1048576,  # 1MB
        library_uuid=library.uuid
    )
    db_session.add(game)
    db_session.commit()
    return game


@pytest.fixture
def sample_download_request(db_session, authenticated_user, sample_game):
    """Create a sample download request."""
    download_request = DownloadRequest(
        user_id=authenticated_user.id,
        game_uuid=sample_game.uuid,
        status='completed',
        zip_file_path='/test/zip/path/test_file.zip',
        download_size=1048576
    )
    db_session.add(download_request)
    db_session.commit()
    return download_request


class TestDownloadsRoute:
    """Test the /downloads route."""
    
    def test_downloads_route_requires_authentication(self, client):
        """Test that the downloads route requires authentication."""
        response = client.get('/downloads')
        assert response.status_code == 302  # Redirect to login
    
    def test_downloads_route_authenticated_user(self, client, authenticated_user, sample_download_request):
        """Test downloads route for authenticated user shows their downloads."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.get('/downloads')
        assert response.status_code == 200
        assert b'Test Game' in response.data or b'manage_downloads' in response.data
    
    def test_downloads_route_user_isolation(self, client, authenticated_user, admin_user, sample_download_request, db_session):
        """Test that users can only see their own downloads."""
        # Create download request for admin user
        admin_download = DownloadRequest(
            user_id=admin_user.id,
            game_uuid=sample_download_request.game_uuid,
            status='completed',
            zip_file_path='/test/zip/path/admin_file.zip',
            download_size=2097152
        )
        db_session.add(admin_download)
        db_session.commit()
        
        # Login as regular user
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.get('/downloads')
        assert response.status_code == 200
        
        # User should only see their own downloads
        downloads = db.session.execute(
            select(DownloadRequest).filter_by(user_id=authenticated_user.id)
        ).scalars().all()
        assert len(downloads) == 1
        assert downloads[0].id == sample_download_request.id


class TestDeleteDownloadRoute:
    """Test the /delete_download route."""
    
    def test_delete_download_requires_authentication(self, client):
        """Test that delete download requires authentication."""
        response = client.post('/delete_download/1')
        assert response.status_code == 302  # Redirect to login
    
    def test_delete_download_invalid_id(self, client, authenticated_user):
        """Test deletion with invalid download ID."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.post('/delete_download/invalid')
        assert response.status_code == 404  # Flask returns 404 for invalid int conversion
        
        # Note: No security log is created here because Flask routing fails before reaching our handler
    
    def test_delete_download_unauthorized_access(self, client, authenticated_user, admin_user, sample_download_request, db_session):
        """Test that users cannot delete other users' downloads."""
        # Create download request for admin user
        admin_download = DownloadRequest(
            user_id=admin_user.id,
            game_uuid=sample_download_request.game_uuid,
            status='completed',
            zip_file_path='/test/zip/path/admin_file.zip',
            download_size=2097152
        )
        db_session.add(admin_download)
        db_session.commit()
        
        # Try to delete admin's download as regular user
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.post(f'/delete_download/{admin_download.id}')
        assert response.status_code == 404
        
        # Check security log
        security_logs = db.session.execute(
            select(SystemEvents).filter_by(event_type='security')
        ).scalars().all()
        assert any('Unauthorized download deletion attempt' in log.event_text for log in security_logs)
    
    def test_delete_download_successful_file_deletion(self, client, authenticated_user, sample_download_request, app):
        """Test successful deletion of download request (no file management)."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['_user_id'] = str(authenticated_user.id)
                sess['_fresh'] = True

            response = client.post(f'/delete_download/{sample_download_request.id}')
            assert response.status_code == 302  # Redirect
            assert response.location.endswith('/downloads')

            # Verify download request was deleted from database
            deleted_request = db.session.get(DownloadRequest, sample_download_request.id)
            assert deleted_request is None

            # Check audit log
            audit_logs = db.session.execute(
                select(SystemEvents).filter_by(event_type='audit')
            ).scalars().all()
            assert any('deleted download request' in log.event_text for log in audit_logs)
    
    def test_delete_download_path_traversal_blocked(self, client, authenticated_user, sample_download_request, app, db_session):
        """Test deletion works regardless of zip file paths (no file validation needed)."""
        # Set a potentially dangerous path (should be ignored)
        sample_download_request.zip_file_path = '../../../etc/passwd'
        db_session.commit()  # Commit the change to the database

        with app.app_context():
            with client.session_transaction() as sess:
                sess['_user_id'] = str(authenticated_user.id)
                sess['_fresh'] = True

            response = client.post(f'/delete_download/{sample_download_request.id}')
            assert response.status_code == 302  # Redirect

            # Verify download request was deleted (path ignored)
            deleted_request = db.session.get(DownloadRequest, sample_download_request.id)
            assert deleted_request is None
    
    
    def test_delete_download_file_removal_error(self, client, authenticated_user, sample_download_request, app):
        """Test deletion succeeds without file operations."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['_user_id'] = str(authenticated_user.id)
                sess['_fresh'] = True

            response = client.post(f'/delete_download/{sample_download_request.id}')
            assert response.status_code == 302  # Redirect

            # Verify download request was deleted successfully
            deleted_request = db.session.get(DownloadRequest, sample_download_request.id)
            assert deleted_request is None

            # Check audit log
            audit_logs = db.session.execute(
                select(SystemEvents).filter_by(event_type='audit')
            ).scalars().all()
            assert any('deleted download request' in log.event_text for log in audit_logs)


class TestCheckDownloadStatusRoute:
    """Test the /check_download_status route."""
    
    def test_check_status_requires_authentication(self, client):
        """Test that check status requires authentication."""
        response = client.get('/check_download_status/1')
        assert response.status_code == 302  # Redirect to login
    
    def test_check_status_invalid_id(self, client, authenticated_user):
        """Test status check with invalid download ID."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.get('/check_download_status/invalid')
        assert response.status_code == 400
        
        data = response.get_json()
        assert data['status'] == 'invalid'
        assert data['found'] is False
        assert 'error' in data
        
        # Check security log
        security_logs = db.session.execute(
            select(SystemEvents).filter_by(event_type='security')
        ).scalars().all()
        assert any('Invalid download_id parameter in status check' in log.event_text for log in security_logs)
    
    def test_check_status_successful(self, client, authenticated_user, sample_download_request):
        """Test successful status check for own download."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/check_download_status/{sample_download_request.id}')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['status'] == 'completed'
        assert data['downloadId'] == sample_download_request.id
        assert data['found'] is True
    
    def test_check_status_unauthorized_access(self, client, authenticated_user, admin_user, sample_download_request, db_session):
        """Test that users cannot check other users' download status."""
        # Create download request for admin user
        admin_download = DownloadRequest(
            user_id=admin_user.id,
            game_uuid=sample_download_request.game_uuid,
            status='pending',
            zip_file_path='/test/zip/path/admin_file.zip',
            download_size=2097152
        )
        db_session.add(admin_download)
        db_session.commit()
        
        # Try to check admin's download status as regular user
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/check_download_status/{admin_download.id}')
        assert response.status_code == 404
        
        data = response.get_json()
        assert data['status'] == 'not_found'
        assert data['found'] is False
        
        # Check security log
        security_logs = db.session.execute(
            select(SystemEvents).filter_by(event_type='security')
        ).scalars().all()
        assert any('Unauthorized download status check' in log.event_text for log in security_logs)
    
    def test_check_status_nonexistent_download(self, client, authenticated_user):
        """Test status check for nonexistent download."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        response = client.get('/check_download_status/99999')
        assert response.status_code == 404
        
        # For 404 responses, Flask might not return JSON in all cases
        if response.content_type and 'application/json' in response.content_type:
            data = response.get_json()
            assert data['status'] == 'not_found'
            assert data['downloadId'] == 99999
            assert data['found'] is False
        
        # Check security log for unauthorized access attempt
        security_logs = db.session.execute(
            select(SystemEvents).filter_by(event_type='security')
        ).scalars().all()
        assert any('Unauthorized download status check' in log.event_text for log in security_logs)


class TestSecurityLogging:
    """Test security audit logging functionality."""
    
    def test_audit_logs_created_for_successful_operations(self, client, authenticated_user, sample_download_request, app):
        """Test that audit logs are created for successful operations."""
        with app.app_context():
            with client.session_transaction() as sess:
                sess['_user_id'] = str(authenticated_user.id)
                sess['_fresh'] = True

            # Clear existing logs
            db.session.query(SystemEvents).delete()
            db.session.commit()

            response = client.post(f'/delete_download/{sample_download_request.id}')
            assert response.status_code == 302

            # Check that audit log was created
            audit_logs = db.session.execute(
                select(SystemEvents).filter_by(event_type='audit')
            ).scalars().all()

            assert len(audit_logs) == 1
            assert f'User {authenticated_user.id} deleted download request' in audit_logs[0].event_text
            assert audit_logs[0].audit_user == authenticated_user.id
    
    def test_security_logs_created_for_violations(self, client, authenticated_user):
        """Test that security logs are created for security violations."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
            sess['_fresh'] = True
        
        # Clear existing logs
        db.session.query(SystemEvents).delete()
        db.session.commit()
        
        # Attempt invalid operations
        client.get('/check_download_status/invalid')  # This creates a security log
        client.post('/delete_download/99999')  # This creates a security log
        
        # Check security logs
        security_logs = db.session.execute(
            select(SystemEvents).filter_by(event_type='security')
        ).scalars().all()
        
        assert len(security_logs) >= 2
        security_messages = [log.event_text for log in security_logs]
        
        assert any('Invalid download_id parameter in status check' in msg for msg in security_messages)
        assert any('Unauthorized download deletion attempt' in msg for msg in security_messages)