import pytest
import json
import os
import tempfile
from unittest.mock import patch, Mock, MagicMock, mock_open
from datetime import datetime, timezone
from uuid import uuid4
from io import BytesIO
from werkzeug.datastructures import FileStorage
from sqlalchemy import select, func

from modules import create_app, db
from modules.models import (
    User, Game, Library, Genre, GameMode, Theme, Platform, 
    PlayerPerspective, Image, ScanJob, UnmatchedFolder, user_favorites
)
from modules.platform import LibraryPlatform


@pytest.fixture(scope='function')
def app():
    """Create and configure a test app using the actual database."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    app.config['IMAGE_SAVE_PATH'] = '/tmp/test_images'
    app.config['BASE_FOLDER_WINDOWS'] = 'C:\\Games'
    app.config['BASE_FOLDER_POSIX'] = '/home/games'
    
    yield app


@pytest.fixture(scope='function')  
def db_session(app):
    """Create a database session for testing with transaction rollback."""
    with app.app_context():
        # Start a transaction that will be rolled back after each test
        connection = db.engine.connect()
        transaction = connection.begin()
        
        # Bind the session to this transaction
        db.session.configure(bind=connection)
        
        yield db.session
        
        # Rollback the transaction to clean up
        transaction.rollback()
        connection.close()
        db.session.remove()


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user_uuid = str(uuid4())
    user = User(
        name=f'testuser_{user_uuid[:8]}',
        email=f'test_{user_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='user',
        user_id=user_uuid
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin_user(db_session):
    """Create an admin user."""
    admin_uuid = str(uuid4())
    admin = User(
        name=f'admin_{admin_uuid[:8]}',
        email=f'admin_{admin_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='admin',
        user_id=admin_uuid
    )
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture
def test_library(db_session):
    """Create a test library."""
    unique_name = f'Test Library {uuid4().hex[:8]}'
    library = Library(
        name=unique_name,
        image_url='/static/library_test.jpg',
        platform=LibraryPlatform.PCWIN,
        display_order=1
    )
    db_session.add(library)
    db_session.commit()
    return library


@pytest.fixture
def test_game(db_session, test_library):
    """Create a test game."""
    game = Game(
        uuid=str(uuid4()),
        name='Test Game',
        library_uuid=test_library.uuid,
        summary='A test game',
        rating=85,
        size=1024000,
        first_release_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        date_identified=datetime.now(timezone.utc),
        full_disk_path='/test/path/game'
    )
    db_session.add(game)
    db_session.commit()
    return game


@pytest.fixture
def test_genre(db_session):
    """Create a test genre."""
    genre = db.session.execute(select(Genre).filter_by(name='Action')).scalar_one_or_none()
    if not genre:
        genre = Genre(name='Action')
        db_session.add(genre)
        db_session.commit()
    return genre


@pytest.fixture
def test_scan_job(db_session, test_library):
    """Create a test scan job."""
    job = ScanJob(
        scan_folder='test_folder',
        library_uuid=test_library.uuid,
        status='Completed',
        last_run=datetime.now(timezone.utc),
        setting_remove=False,
        setting_filefolder=False,
        is_enabled=True
    )
    db_session.add(job)
    db_session.commit()
    return job


@pytest.fixture
def test_unmatched_folder(db_session, test_library):
    """Create a test unmatched folder."""
    folder = UnmatchedFolder(
        folder_path='/test/unmatched/folder',
        status='Unmatched',
        library_uuid=test_library.uuid
    )
    db_session.add(folder)
    db_session.commit()
    return folder


@pytest.fixture
def test_image(db_session, test_game):
    """Create a test image."""
    image = Image(
        game_uuid=test_game.uuid,
        image_type='cover',
        url='test_cover.jpg'
    )
    db_session.add(image)
    db_session.commit()
    return image


class TestMainBlueprint:
    """Test cases for the main blueprint (routes.py)."""

    @patch('modules.routes.get_global_settings')
    def test_inject_settings_context_processor(self, mock_get_global_settings, app, db_session):
        """Test the inject_settings context processor."""
        mock_get_global_settings.return_value = {'test_setting': 'test_value'}
        
        with app.app_context():
            from modules.routes import inject_settings
            result = inject_settings()
            assert result == {'test_setting': 'test_value'}
            mock_get_global_settings.assert_called_once()

    def test_browse_games_unauthenticated(self, client):
        """Test browse_games route requires authentication."""
        response = client.get('/browse_games')
        assert response.status_code == 302  # Redirect to login

    @patch('flask_login.current_user')
    def test_browse_games_basic(self, mock_current_user, client, app, db_session, test_user, test_game, test_image):
        """Test basic browse_games functionality."""
        mock_current_user.is_authenticated = True
        mock_current_user.name = test_user.name
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
        
        response = client.get('/browse_games')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'games' in data
        assert 'total' in data
        assert 'pages' in data
        assert 'current_page' in data

    @patch('flask_login.current_user')
    def test_browse_games_with_filters(self, mock_current_user, client, app, db_session, test_user, test_game, test_library, test_genre):
        """Test browse_games with various filters."""
        mock_current_user.is_authenticated = True
        mock_current_user.name = test_user.name
        
        # Add genre to game
        test_game.genres.append(test_genre)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
        
        # Test with library filter
        response = client.get(f'/browse_games?library_uuid={test_library.uuid}')
        assert response.status_code == 200
        
        # Test with genre filter
        response = client.get(f'/browse_games?genre=Action')
        assert response.status_code == 200
        
        # Test with rating filter
        response = client.get('/browse_games?rating=80')
        assert response.status_code == 200
        
        # Test with sorting
        response = client.get('/browse_games?sort_by=rating&sort_order=desc')
        assert response.status_code == 200

    @patch('flask_login.current_user')
    def test_browse_games_pagination(self, mock_current_user, client, app, db_session, test_user, test_game):
        """Test browse_games pagination."""
        mock_current_user.is_authenticated = True
        mock_current_user.name = test_user.name
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
        
        response = client.get('/browse_games?page=1&per_page=5')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['current_page'] == 1

    def test_scan_folder_unauthenticated(self, client):
        """Test scan_folder route requires authentication."""
        response = client.get('/scan_manual_folder')
        assert response.status_code == 302  # Redirect to login

    @patch('flask_login.current_user')
    def test_scan_folder_non_admin(self, mock_current_user, client, db_session, test_user):
        """Test scan_folder route requires admin access."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'user'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
        
        response = client.get('/scan_manual_folder')
        assert response.status_code == 302  # Redirect to login

    @patch('flask_login.current_user')
    @patch('modules.routes.os.path.exists')
    @patch('modules.routes.os.access')
    @patch('modules.routes.get_game_names_from_folder')
    def test_scan_folder_valid_path(self, mock_get_games, mock_access, mock_exists, mock_current_user, 
                                   client, app, db_session, admin_user, test_library):
        """Test scan_folder with valid folder path."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_exists.return_value = True
        mock_access.return_value = True
        mock_get_games.return_value = [{'name': 'Test Game', 'full_path': '/test/path'}]
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/scan_manual_folder', data={
            'folder_path': '/test/folder',
            'library_uuid': str(test_library.uuid),
            'csrf_token': 'test_token',
            'scan_mode': 'folders'
        })
        assert response.status_code == 200

    @patch('flask_login.current_user')
    @patch('modules.routes.os.path.exists')
    def test_scan_folder_invalid_path(self, mock_exists, mock_current_user, client, app, db_session, admin_user, test_library):
        """Test scan_folder with invalid folder path."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_exists.return_value = False
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/scan_manual_folder', data={
            'folder_path': '/invalid/folder',
            'library_uuid': str(test_library.uuid),
            'csrf_token': 'test_token',
            'scan_mode': 'folders'
        })
        assert response.status_code == 200
        # Should contain error message about folder not existing

    @patch('flask_login.current_user')
    def test_scan_management_get(self, mock_current_user, client, app, db_session, admin_user, test_library, test_scan_job):
        """Test scan_management GET request."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.get('/scan_management')
        assert response.status_code == 200

    @patch('flask_login.current_user')
    @patch('modules.routes.handle_auto_scan')
    def test_scan_management_auto_scan(self, mock_handle_auto_scan, mock_current_user, 
                                      client, app, db_session, admin_user, test_library):
        """Test scan_management with auto scan submission."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        from flask import Response
        mock_handle_auto_scan.return_value = Response('', status=302, headers={'Location': '/scan_management'})
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/scan_management', data={
            'submit': 'AutoScan',
            'folder_path': '/test/folder',
            'library_uuid': str(test_library.uuid),
            'csrf_token': 'test_token',
            'scan_mode': 'folders'
        })
        mock_handle_auto_scan.assert_called_once()

    @patch('flask_login.current_user')
    @patch('modules.routes.handle_manual_scan')
    def test_scan_management_manual_scan(self, mock_handle_manual_scan, mock_current_user, 
                                        client, app, db_session, admin_user, test_library):
        """Test scan_management with manual scan submission."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        from flask import Response
        mock_handle_manual_scan.return_value = Response('', status=302, headers={'Location': '/scan_management'})
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/scan_management', data={
            'submit': 'ManualScan',
            'folder_path': '/test/folder', 
            'library_uuid': str(test_library.uuid),
            'csrf_token': 'test_token',
            'scan_mode': 'folders'
        })
        mock_handle_manual_scan.assert_called_once()

    @patch('flask_login.current_user')
    @patch('modules.routes.handle_delete_unmatched')
    def test_scan_management_delete_unmatched(self, mock_handle_delete, mock_current_user, 
                                             client, app, db_session, admin_user):
        """Test scan_management with delete unmatched submission."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        from flask import Response
        mock_handle_delete.return_value = Response('', status=302, headers={'Location': '/scan_management'})
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/scan_management', data={
            'submit': 'DeleteAllUnmatched',
            'csrf_token': 'test_token'
        })
        mock_handle_delete.assert_called_once_with(all=True)

    @patch('flask_login.current_user')
    def test_cancel_scan_job(self, mock_current_user, client, app, db_session, admin_user, test_scan_job):
        """Test cancelling a scan job."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        # Set job to running status
        test_scan_job.status = 'Running'
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/cancel_scan_job/{test_scan_job.id}')
        assert response.status_code == 302  # Redirect
        
        # Check job was cancelled
        db_session.refresh(test_scan_job)
        assert test_scan_job.status == 'Failed'
        assert test_scan_job.is_enabled == False

    @patch('flask_login.current_user')
    def test_cancel_scan_job_not_running(self, mock_current_user, client, app, db_session, admin_user, test_scan_job):
        """Test cancelling a non-running scan job."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/cancel_scan_job/{test_scan_job.id}')
        assert response.status_code == 302  # Redirect
        
        # Job should remain in original state
        db_session.refresh(test_scan_job)
        assert test_scan_job.status == 'Completed'

    @patch('flask_login.current_user')
    @patch('modules.routes.Thread')
    @patch('modules.routes.copy_current_request_context')
    def test_restart_scan_job(self, mock_copy_context, mock_thread, mock_current_user, 
                             client, app, db_session, admin_user, test_scan_job):
        """Test restarting a scan job."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/restart_scan_job/{test_scan_job.id}')
        assert response.status_code == 302  # Redirect
        
        # Check job was restarted
        db_session.refresh(test_scan_job)
        assert test_scan_job.status == 'Running'
        assert test_scan_job.is_enabled == True

    @patch('flask_login.current_user')
    def test_restart_running_scan_job(self, mock_current_user, client, app, db_session, admin_user, test_scan_job):
        """Test restarting an already running scan job."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        # Set job to running
        test_scan_job.status = 'Running'
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/restart_scan_job/{test_scan_job.id}')
        assert response.status_code == 302  # Redirect

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    def test_edit_game_images(self, mock_is_scan_running, mock_current_user, 
                             client, app, db_session, admin_user, test_game, test_image):
        """Test edit game images route."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_is_scan_running.return_value = False
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.get(f'/edit_game_images/{test_game.uuid}')
        assert response.status_code == 200

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    def test_edit_game_images_scan_running(self, mock_is_scan_running, mock_current_user, 
                                          client, app, db_session, admin_user, test_game):
        """Test edit game images when scan is running."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_is_scan_running.return_value = True
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.get(f'/edit_game_images/{test_game.uuid}')
        assert response.status_code == 200

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    @patch('modules.routes.PILImage.open')
    @patch('modules.routes.os.path.join')
    def test_upload_image_success(self, mock_path_join, mock_pil_open, mock_is_scan_running, 
                                 mock_current_user, client, app, db_session, admin_user, test_game):
        """Test successful image upload."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_is_scan_running.return_value = False
        
        # Mock PIL image
        mock_img = Mock()
        mock_img.width = 800
        mock_img.height = 600
        mock_pil_open.return_value = mock_img
        
        mock_path_join.return_value = '/tmp/test_image.jpg'
        
        # Create test file
        test_file = FileStorage(
            stream=BytesIO(b'fake image data'),
            filename='test.jpg',
            content_type='image/jpeg'
        )
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/upload_image/{test_game.uuid}', 
                              data={'file': test_file, 'image_type': 'cover'},
                              content_type='multipart/form-data')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'message' in data
        assert data['message'] == 'File uploaded successfully'

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    def test_upload_image_scan_running(self, mock_is_scan_running, mock_current_user, 
                                      client, app, db_session, admin_user, test_game):
        """Test image upload when scan is running."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_is_scan_running.return_value = True
        
        test_file = FileStorage(
            stream=BytesIO(b'fake image data'),
            filename='test.jpg',
            content_type='image/jpeg'
        )
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/upload_image/{test_game.uuid}', 
                              data={'file': test_file},
                              content_type='multipart/form-data')
        assert response.status_code == 403

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    def test_upload_image_no_file(self, mock_is_scan_running, mock_current_user, 
                                 client, app, db_session, admin_user, test_game):
        """Test image upload without file."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_is_scan_running.return_value = False
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/upload_image/{test_game.uuid}')
        assert response.status_code == 400

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    def test_upload_image_invalid_extension(self, mock_is_scan_running, mock_current_user, 
                                           client, app, db_session, admin_user, test_game):
        """Test image upload with invalid file extension."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_is_scan_running.return_value = False
        
        test_file = FileStorage(
            stream=BytesIO(b'fake image data'),
            filename='test.txt',
            content_type='text/plain'
        )
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/upload_image/{test_game.uuid}', 
                              data={'file': test_file},
                              content_type='multipart/form-data')
        assert response.status_code == 400

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    @patch('modules.routes.os.path.exists')
    @patch('modules.routes.os.remove')
    def test_delete_image_success(self, mock_remove, mock_exists, mock_is_scan_running, 
                                 mock_current_user, client, app, db_session, admin_user, test_image):
        """Test successful image deletion."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_is_scan_running.return_value = False
        mock_exists.return_value = True
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/delete_image', 
                              json={'image_id': test_image.id, 'is_cover': True})
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'message' in data
        assert data['message'] == 'Image deleted successfully'

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    def test_delete_image_scan_running(self, mock_is_scan_running, mock_current_user, 
                                      client, app, db_session, admin_user, test_image):
        """Test image deletion when scan is running."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_is_scan_running.return_value = True
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/delete_image', 
                              json={'image_id': test_image.id})
        assert response.status_code == 403

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    def test_delete_image_invalid_request(self, mock_is_scan_running, mock_current_user, 
                                         client, app, db_session, admin_user):
        """Test image deletion with invalid request."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_is_scan_running.return_value = False
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/delete_image', json={})
        assert response.status_code == 400

    @patch('flask_login.current_user')
    def test_delete_scan_job(self, mock_current_user, client, app, db_session, admin_user, test_scan_job):
        """Test deleting a scan job."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        job_id = test_scan_job.id
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/delete_scan_job/{job_id}')
        assert response.status_code == 302  # Redirect
        
        # Check job was deleted
        deleted_job = db.session.get(ScanJob, job_id)
        assert deleted_job is None

    @patch('flask_login.current_user')
    def test_clear_all_scan_jobs(self, mock_current_user, client, app, db_session, admin_user, test_scan_job):
        """Test clearing all scan jobs."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/clear_all_scan_jobs')
        assert response.status_code == 302  # Redirect
        
        # Check all jobs were deleted
        job_count = db.session.scalar(select(func.count(ScanJob.id)))
        assert job_count == 0

    @patch('flask_login.current_user')
    def test_delete_all_unmatched_folders(self, mock_current_user, client, app, db_session, 
                                         admin_user, test_unmatched_folder):
        """Test deleting all unmatched folders."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/delete_all_unmatched_folders')
        assert response.status_code == 302  # Redirect
        
        # Check all unmatched folders were deleted
        folder_count = db.session.scalar(select(func.count(UnmatchedFolder.id)))
        assert folder_count == 0

    @patch('flask_login.current_user')
    def test_update_unmatched_folder_status(self, mock_current_user, client, app, db_session, 
                                           admin_user, test_unmatched_folder):
        """Test updating unmatched folder status."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        original_status = test_unmatched_folder.status
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/update_unmatched_folder_status', 
                              data={'folder_id': test_unmatched_folder.id})
        assert response.status_code == 302  # Redirect
        
        # Check status was toggled
        db_session.refresh(test_unmatched_folder)
        expected_status = 'Ignore' if original_status == 'Unmatched' else 'Unmatched'
        assert test_unmatched_folder.status == expected_status

    @patch('flask_login.current_user')
    def test_update_unmatched_folder_status_ajax(self, mock_current_user, client, app, db_session, 
                                                admin_user, test_unmatched_folder):
        """Test updating unmatched folder status via AJAX."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/update_unmatched_folder_status', 
                              data={'folder_id': test_unmatched_folder.id},
                              headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] == 'success'

    @patch('flask_login.current_user')
    def test_clear_unmatched_entry(self, mock_current_user, client, app, db_session, 
                                  admin_user, test_unmatched_folder):
        """Test clearing a single unmatched folder entry."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        folder_id = test_unmatched_folder.id
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/clear_unmatched_entry/{folder_id}')
        assert response.status_code == 302  # Redirect
        
        # Check folder was deleted
        deleted_folder = db.session.get(UnmatchedFolder, folder_id)
        assert deleted_folder is None

    @patch('flask_login.current_user')
    def test_clear_unmatched_entry_ajax(self, mock_current_user, client, app, db_session, 
                                       admin_user, test_unmatched_folder):
        """Test clearing unmatched entry via AJAX."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/clear_unmatched_entry/{test_unmatched_folder.id}',
                              headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] == 'success'

    @patch('flask_login.current_user')
    @patch('modules.routes.Thread')
    @patch('modules.routes.copy_current_request_context')
    @patch('modules.routes.get_game_name_by_uuid')
    def test_refresh_game_images(self, mock_get_name, mock_copy_context, mock_thread, 
                                mock_current_user, client, app, db_session, admin_user, test_game):
        """Test refreshing game images."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.name = admin_user.name
        mock_get_name.return_value = 'Test Game'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/refresh_game_images/{test_game.uuid}')
        assert response.status_code == 302  # Redirect

    @patch('flask_login.current_user')
    @patch('modules.routes.get_game_name_by_uuid')
    def test_refresh_game_images_ajax(self, mock_get_name, mock_current_user, 
                                     client, app, db_session, admin_user, test_game):
        """Test refreshing game images via AJAX."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.name = admin_user.name
        mock_get_name.return_value = 'Test Game'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/refresh_game_images/{test_game.uuid}',
                              headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'message' in data

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    @patch('modules.routes.delete_game')
    def test_delete_game_route(self, mock_delete_game, mock_is_scan_running, mock_current_user, 
                              client, app, db_session, admin_user, test_game):
        """Test deleting a game."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.name = admin_user.name
        mock_is_scan_running.return_value = False
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/delete_game/{test_game.uuid}')
        assert response.status_code == 302  # Redirect
        mock_delete_game.assert_called_once_with(test_game.uuid)

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    def test_delete_game_route_scan_running(self, mock_is_scan_running, mock_current_user, 
                                           client, app, db_session, admin_user, test_game):
        """Test deleting a game when scan is running."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.name = admin_user.name
        mock_is_scan_running.return_value = True
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/delete_game/{test_game.uuid}')
        assert response.status_code == 302  # Redirect

    @patch('flask_login.current_user')
    @patch('modules.routes.os.path.exists')
    @patch('modules.routes.os.remove')
    def test_delete_folder_file(self, mock_remove, mock_exists, mock_current_user, 
                               client, app, db_session, admin_user):
        """Test deleting a file via delete_folder route."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        # First call returns True (file exists), second call returns False (after deletion)
        mock_exists.side_effect = [True, False]
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        with patch('modules.routes.os.path.isfile', return_value=True):
            response = client.post('/delete_folder', 
                                  json={'folder_path': '/test/file.txt'})
            assert response.status_code == 200
            mock_remove.assert_called_once()

    @patch('flask_login.current_user')
    @patch('modules.routes.os.path.exists')
    @patch('modules.routes.shutil.rmtree')
    def test_delete_folder_directory(self, mock_rmtree, mock_exists, mock_current_user, 
                                    client, app, db_session, admin_user):
        """Test deleting a directory via delete_folder route."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_exists.side_effect = [True, False]  # Exists before, not after deletion
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        with patch('modules.routes.os.path.isfile', return_value=False):
            response = client.post('/delete_folder', 
                                  json={'folder_path': '/test/folder'})
            assert response.status_code == 200
            mock_rmtree.assert_called_once()

    @patch('flask_login.current_user')
    def test_delete_folder_no_path(self, mock_current_user, client, app, db_session, admin_user):
        """Test delete_folder without path."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/delete_folder', json={})
        assert response.status_code == 400

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    @patch('modules.routes.os.path.isdir')
    @patch('modules.routes.shutil.rmtree')
    @patch('modules.routes.os.path.exists')
    @patch('modules.routes.delete_game')
    def test_delete_full_game(self, mock_delete_game, mock_exists, mock_rmtree, 
                             mock_isdir, mock_is_scan_running, mock_current_user, 
                             client, app, db_session, admin_user, test_game):
        """Test deleting a full game (folder + database)."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.name = admin_user.name
        mock_is_scan_running.return_value = False
        mock_isdir.return_value = True
        mock_exists.return_value = False  # Folder deleted successfully
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/delete_full_game', 
                              json={'game_uuid': test_game.uuid})
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] == 'success'
        mock_rmtree.assert_called_once()
        mock_delete_game.assert_called_once_with(test_game.uuid)

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    def test_delete_full_game_scan_running(self, mock_is_scan_running, mock_current_user, 
                                          client, app, db_session, admin_user, test_game):
        """Test delete_full_game when scan is running."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_is_scan_running.return_value = True
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/delete_full_game', 
                              json={'game_uuid': test_game.uuid})
        assert response.status_code == 403

    @patch('flask_login.current_user')
    @patch('modules.routes.is_scan_job_running')
    def test_delete_full_game_no_uuid(self, mock_is_scan_running, mock_current_user, 
                                     client, app, db_session, admin_user):
        """Test delete_full_game without game UUID."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_is_scan_running.return_value = False
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post('/delete_full_game', json={})
        assert response.status_code == 400

    @patch('flask_login.current_user')
    def test_delete_full_library(self, mock_current_user, 
                                client, app, db_session, admin_user, test_library, test_game):
        """Test deleting a full library."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.name = admin_user.name
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/delete_full_library/{test_library.uuid}')
        assert response.status_code == 302  # Redirect
        
        # Check library was deleted
        deleted_library = db.session.execute(select(Library).filter_by(uuid=test_library.uuid)).scalar_one_or_none()
        assert deleted_library is None

    @patch('flask_login.current_user')
    def test_delete_full_library_not_found(self, mock_current_user, client, app, db_session, admin_user):
        """Test deleting a non-existent library."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        fake_uuid = str(uuid4())
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        response = client.post(f'/delete_full_library/{fake_uuid}')
        assert response.status_code == 302  # Redirect

    def test_verify_file_exists(self, app):
        """Test verify_file template global with existing file."""
        with app.app_context():
            verify_file = app.jinja_env.globals['verify_file']
            with patch('modules.routes.os.path.exists', return_value=True):
                result = verify_file('/test/path')
                assert result == True

    def test_verify_file_not_exists(self, app):
        """Test verify_file template global with non-existing file."""
        with app.app_context():
            verify_file = app.jinja_env.globals['verify_file']
            with patch('modules.routes.os.path.exists', return_value=False):
                with patch('modules.routes.os.access', return_value=False):
                    result = verify_file('/test/path')
                    assert result == False

    def test_verify_file_accessible(self, app):
        """Test verify_file template global with accessible file."""
        with app.app_context():
            verify_file = app.jinja_env.globals['verify_file']
            with patch('modules.routes.os.path.exists', return_value=False):
                with patch('modules.routes.os.access', return_value=True):
                    result = verify_file('/test/path')
                    assert result == True


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch('flask_login.current_user')
    def test_upload_image_invalid_image_data(self, mock_current_user, client, app, db_session, admin_user, test_game):
        """Test uploading invalid image data."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with patch('modules.routes.is_scan_job_running', return_value=False):
            with patch('modules.routes.PILImage.open', side_effect=IOError("Invalid image")):
                test_file = FileStorage(
                    stream=BytesIO(b'invalid image data'),
                    filename='test.jpg',
                    content_type='image/jpeg'
                )
                
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(admin_user.id)
                
                response = client.post(f'/upload_image/{test_game.uuid}', 
                                      data={'file': test_file},
                                      content_type='multipart/form-data')
                assert response.status_code == 400

    @patch('flask_login.current_user')
    def test_delete_image_not_found(self, mock_current_user, client, app, db_session, admin_user):
        """Test deleting non-existent image."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with patch('modules.routes.is_scan_job_running', return_value=False):
            with client.session_transaction() as sess:
                sess['_user_id'] = str(admin_user.id)
            
            response = client.post('/delete_image', 
                                  json={'image_id': 99999})
            assert response.status_code == 404

    @patch('flask_login.current_user')
    def test_delete_folder_permission_error(self, mock_current_user, client, app, db_session, admin_user):
        """Test delete_folder with permission error."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with patch('modules.routes.os.path.exists', return_value=True):
            with patch('modules.routes.os.path.isfile', return_value=True):
                with patch('modules.routes.os.remove', side_effect=PermissionError("Permission denied")):
                    with client.session_transaction() as sess:
                        sess['_user_id'] = str(admin_user.id)
                    
                    response = client.post('/delete_folder', 
                                          json={'folder_path': '/test/file.txt'})
                    assert response.status_code == 403

    @patch('flask_login.current_user')  
    def test_delete_full_game_folder_not_found(self, mock_current_user, client, app, db_session, admin_user, test_game):
        """Test delete_full_game with non-existent folder."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with patch('modules.routes.is_scan_job_running', return_value=False):
            with patch('modules.routes.os.path.isdir', return_value=False):
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(admin_user.id)
                
                response = client.post('/delete_full_game', 
                                      json={'game_uuid': test_game.uuid})
                assert response.status_code == 404

    @patch('flask_login.current_user')
    def test_delete_all_unmatched_folders_db_error(self, mock_current_user, client, app, db_session, admin_user):
        """Test delete_all_unmatched_folders with database error."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        
        with patch.object(db.session, 'commit', side_effect=Exception("DB Error")):
            with client.session_transaction() as sess:
                sess['_user_id'] = str(admin_user.id)
            
            response = client.post('/delete_all_unmatched_folders')
            assert response.status_code == 302  # Should redirect despite error