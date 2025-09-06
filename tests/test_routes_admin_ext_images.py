# tests/test_routes_admin_ext_images.py
import pytest
from unittest.mock import patch, MagicMock, mock_open
from flask import json
from modules.models import Image, Game, Library, LibraryPlatform, User
from uuid import uuid4
import os


@pytest.fixture(scope='function', autouse=True)
def clean_database(db_session):
    """Clean database before each test to ensure isolation."""
    from sqlalchemy import text
    
    # Disable foreign key checks temporarily and truncate tables
    # This is PostgreSQL specific
    db_session.execute(text("TRUNCATE TABLE images RESTART IDENTITY CASCADE"))
    db_session.execute(text("TRUNCATE TABLE games RESTART IDENTITY CASCADE"))  
    db_session.execute(text("TRUNCATE TABLE libraries RESTART IDENTITY CASCADE"))
    
    # Clean up association tables that might have foreign key constraints
    db_session.execute(text("TRUNCATE TABLE game_genre_association RESTART IDENTITY CASCADE"))
    db_session.execute(text("TRUNCATE TABLE game_theme_association RESTART IDENTITY CASCADE")) 
    db_session.execute(text("TRUNCATE TABLE game_game_mode_association RESTART IDENTITY CASCADE"))
    db_session.execute(text("TRUNCATE TABLE user_favorites RESTART IDENTITY CASCADE"))
    
    db_session.commit()


@pytest.fixture
def regular_user(db_session):
    """Create a regular test user."""
    user_uuid = str(uuid4())
    user = User(
        name=f'testuser_{user_uuid[:8]}',
        email=f'test_{user_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='user',
        user_id=user_uuid,
        avatarpath='newstyle/avatar_default.jpg',
        invite_quota=5
    )
    user.set_password('testpassword123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin_user(db_session):
    """Create a test admin user."""
    user_uuid = str(uuid4())
    user = User(
        name=f'adminuser_{user_uuid[:8]}',
        email=f'admin_{user_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='admin',
        user_id=user_uuid,
        avatarpath='newstyle/avatar_default.jpg',
        invite_quota=10
    )
    user.set_password('adminpassword123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_library(db_session):
    """Create a sample library for testing."""
    library = Library(
        name='Test Library',
        platform=LibraryPlatform.PCWIN,
        display_order=1
    )
    db_session.add(library)
    db_session.flush()
    return library


@pytest.fixture
def sample_game(db_session, sample_library):
    """Create a sample game for testing."""
    import random
    game = Game(
        library_uuid=sample_library.uuid,
        name='Test Game',
        igdb_id=random.randint(100000, 999999)  # Generate unique IGDB ID
    )
    db_session.add(game)
    db_session.flush()
    return game


class TestImageQueueRoute:
    """Tests for the image_queue template rendering route."""
    
    def test_image_queue_requires_login(self, client):
        """Test that image_queue route requires authentication."""
        response = client.get('/admin/image_queue')
        assert response.status_code == 302  # Redirect to login

    def test_image_queue_requires_admin(self, client, regular_user):
        """Test that image_queue route requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/image_queue')
        assert response.status_code == 302  # Redirected by admin_required

    def test_image_queue_renders_template_for_admin(self, client, admin_user):
        """Test that image_queue route renders template for admin user."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/image_queue')
        assert response.status_code == 200
        assert b'admin_manage_image_queue.html' in response.data or b'Image Queue' in response.data


class TestImageQueueStatsAPI:
    """Tests for the image_queue_stats API endpoint."""
    
    def test_image_queue_stats_requires_login(self, client):
        """Test that image_queue_stats API requires authentication."""
        response = client.get('/admin/api/image_queue_stats')
        assert response.status_code == 302

    def test_image_queue_stats_requires_admin(self, client, regular_user):
        """Test that image_queue_stats API requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/api/image_queue_stats')
        assert response.status_code == 302

    def test_image_queue_stats_empty_database(self, client, admin_user, db_session):
        """Test image queue stats with empty database."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/api/image_queue_stats')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['total_images'] == 0
        assert data['pending_images'] == 0
        assert data['downloaded_images'] == 0
        assert data['pending_covers'] == 0
        assert data['pending_screenshots'] == 0
        assert data['download_percentage'] == 0
        assert data['recent_downloads'] == []

    def test_image_queue_stats_with_images(self, client, admin_user, db_session, sample_library, sample_game):
        """Test image queue stats with sample images."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create sample images
        cover_pending = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=False
        )
        
        cover_downloaded = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover2.jpg',
            url='cover2.jpg',
            is_downloaded=True
        )
        
        screenshot_pending = Image(
            game_uuid=sample_game.uuid,
            image_type='screenshot',
            download_url='https://example.com/screenshot.jpg',
            url='screenshot.jpg',
            is_downloaded=False
        )
        
        db_session.add_all([cover_pending, cover_downloaded, screenshot_pending])
        db_session.flush()

        response = client.get('/admin/api/image_queue_stats')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['total_images'] == 3
        assert data['pending_images'] == 2
        assert data['downloaded_images'] == 1
        assert data['pending_covers'] == 1
        assert data['pending_screenshots'] == 1
        assert data['download_percentage'] == 33.3

    def test_image_queue_stats_recent_downloads(self, client, admin_user, db_session, sample_library, sample_game):
        """Test recent downloads in image queue stats."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create downloaded image
        downloaded_image = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=True
        )
        
        db_session.add(downloaded_image)
        db_session.flush()

        response = client.get('/admin/api/image_queue_stats')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data['recent_downloads']) == 1
        assert data['recent_downloads'][0]['game_name'] == sample_game.name
        assert data['recent_downloads'][0]['image_type'] == 'cover'
        assert 'created_at' in data['recent_downloads'][0]

    def test_image_queue_stats_handles_exception(self, client, admin_user, db_session, monkeypatch):
        """Test image queue stats handles database exceptions."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Mock the func.count to throw an exception
        with patch('modules.routes_admin_ext.images.func.count') as mock_count:
            mock_count.side_effect = Exception("Database error")
            
            response = client.get('/admin/api/image_queue_stats')
            assert response.status_code == 500
            
            data = json.loads(response.data)
            assert 'error' in data


class TestImageQueueListAPI:
    """Tests for the image_queue_list API endpoint."""
    
    def test_image_queue_list_requires_login(self, client):
        """Test that image_queue_list API requires authentication."""
        response = client.get('/admin/api/image_queue_list')
        assert response.status_code == 302

    def test_image_queue_list_requires_admin(self, client, regular_user):
        """Test that image_queue_list API requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/api/image_queue_list')
        assert response.status_code == 302

    def test_image_queue_list_empty_database(self, client, admin_user, db_session):
        """Test image queue list with empty database."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/api/image_queue_list')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['images'] == []
        assert data['pagination']['total'] == 0

    def test_image_queue_list_with_images(self, client, admin_user, db_session, sample_library, sample_game):
        """Test image queue list with sample images."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create sample images
        cover_image = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=False
        )
        
        screenshot_image = Image(
            game_uuid=sample_game.uuid,
            image_type='screenshot',
            download_url='https://example.com/screenshot.jpg',
            url='screenshot.jpg',
            is_downloaded=True
        )
        
        db_session.add_all([cover_image, screenshot_image])
        db_session.flush()

        response = client.get('/admin/api/image_queue_list')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data['images']) == 2
        assert data['pagination']['total'] == 2
        
        # Check first image details
        first_image = data['images'][0]
        assert first_image['game_name'] == sample_game.name
        assert first_image['image_type'] in ['cover', 'screenshot']
        assert 'created_at' in first_image

    def test_image_queue_list_status_filter_pending(self, client, admin_user, db_session, sample_library, sample_game):
        """Test image queue list with status filter for pending."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create pending and downloaded images
        pending_image = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=False
        )
        
        downloaded_image = Image(
            game_uuid=sample_game.uuid,
            image_type='screenshot',
            download_url='https://example.com/screenshot.jpg',
            url='screenshot.jpg',
            is_downloaded=True
        )
        
        db_session.add_all([pending_image, downloaded_image])
        db_session.flush()

        response = client.get('/admin/api/image_queue_list?status=pending')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data['images']) == 1
        assert data['images'][0]['is_downloaded'] is False

    def test_image_queue_list_status_filter_downloaded(self, client, admin_user, db_session, sample_library, sample_game):
        """Test image queue list with status filter for downloaded."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create pending and downloaded images
        pending_image = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=False
        )
        
        downloaded_image = Image(
            game_uuid=sample_game.uuid,
            image_type='screenshot',
            download_url='https://example.com/screenshot.jpg',
            url='screenshot.jpg',
            is_downloaded=True
        )
        
        db_session.add_all([pending_image, downloaded_image])
        db_session.flush()

        response = client.get('/admin/api/image_queue_list?status=downloaded')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data['images']) == 1
        assert data['images'][0]['is_downloaded'] is True

    def test_image_queue_list_type_filter(self, client, admin_user, db_session, sample_library, sample_game):
        """Test image queue list with image type filter."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create cover and screenshot images
        cover_image = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=False
        )
        
        screenshot_image = Image(
            game_uuid=sample_game.uuid,
            image_type='screenshot',
            download_url='https://example.com/screenshot.jpg',
            url='screenshot.jpg',
            is_downloaded=False
        )
        
        db_session.add_all([cover_image, screenshot_image])
        db_session.flush()

        response = client.get('/admin/api/image_queue_list?type=cover')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data['images']) == 1
        assert data['images'][0]['image_type'] == 'cover'

    def test_image_queue_list_pagination(self, client, admin_user, db_session, sample_library, sample_game):
        """Test image queue list pagination."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create multiple images
        for i in range(25):
            image = Image(
                game_uuid=sample_game.uuid,
                image_type='cover',
                download_url=f'https://example.com/image{i}.jpg',
                url=f'image{i}.jpg',
                is_downloaded=False
            )
            db_session.add(image)
        
        db_session.flush()

        # Test first page
        response = client.get('/admin/api/image_queue_list?page=1&per_page=10')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data['images']) == 10
        assert data['pagination']['page'] == 1
        assert data['pagination']['total'] == 25
        assert data['pagination']['has_next'] is True
        assert data['pagination']['has_prev'] is False

        # Test second page
        response = client.get('/admin/api/image_queue_list?page=2&per_page=10')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data['images']) == 10
        assert data['pagination']['page'] == 2
        assert data['pagination']['has_prev'] is True


class TestDownloadImagesAPI:
    """Tests for the download_images API endpoint."""
    
    def test_download_images_requires_login(self, client):
        """Test that download_images API requires authentication."""
        response = client.post('/admin/api/download_images')
        assert response.status_code == 302

    def test_download_images_requires_admin(self, client, regular_user):
        """Test that download_images API requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/api/download_images')
        assert response.status_code == 302

    def test_download_specific_images_success(self, client, admin_user, db_session, sample_library, sample_game):
        """Test downloading specific images successfully."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create pending image
        pending_image = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=False
        )
        
        db_session.add(pending_image)
        db_session.flush()

        with patch('modules.utils_functions.download_image') as mock_download, \
             patch('os.path.join') as mock_join, \
             patch('modules.routes_admin_ext.images.current_app') as mock_app:
            
            mock_app.config = {'IMAGE_SAVE_PATH': '/test/path'}
            mock_join.return_value = '/test/path/cover.jpg'
            mock_download.return_value = True
            
            response = client.post('/admin/api/download_images', 
                                 json={'image_ids': [pending_image.id]})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['downloaded'] == 1
            
            # Check image was marked as downloaded
            db_session.refresh(pending_image)
            assert pending_image.is_downloaded is True

    def test_download_specific_images_not_found(self, client, admin_user, db_session):
        """Test downloading non-existent image IDs."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/api/download_images', 
                             json={'image_ids': [99999]})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['downloaded'] == 0

    def test_download_specific_images_already_downloaded(self, client, admin_user, db_session, sample_library, sample_game):
        """Test downloading already downloaded images."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create already downloaded image
        downloaded_image = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=True
        )
        
        db_session.add(downloaded_image)
        db_session.flush()

        response = client.post('/admin/api/download_images', 
                             json={'image_ids': [downloaded_image.id]})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['downloaded'] == 0

    @patch('modules.utils_game_core.download_pending_images')
    def test_batch_download_success(self, mock_batch_download, client, admin_user):
        """Test batch downloading images."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        mock_batch_download.return_value = 5
        
        response = client.post('/admin/api/download_images', 
                             json={'batch_size': 10})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['downloaded'] == 5
        
        mock_batch_download.assert_called_once()

    def test_download_images_no_parameters(self, client, admin_user):
        """Test download_images with no valid parameters."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/api/download_images', json={})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'No valid parameters' in data['message']

    def test_download_images_handles_exception(self, client, admin_user, db_session, sample_library, sample_game):
        """Test download_images handles exceptions gracefully."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create pending image
        pending_image = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=False
        )
        
        db_session.add(pending_image)
        db_session.flush()

        with patch('modules.utils_functions.download_image') as mock_download:
            mock_download.side_effect = Exception("Download failed")
            
            response = client.post('/admin/api/download_images', 
                                 json={'image_ids': [pending_image.id]})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['downloaded'] == 0


class TestDeleteImageAPI:
    """Tests for the delete_image API endpoint."""
    
    def test_delete_image_requires_login(self, client):
        """Test that delete_image API requires authentication."""
        response = client.delete('/admin/api/delete_image/1')
        assert response.status_code == 302

    def test_delete_image_requires_admin(self, client, regular_user):
        """Test that delete_image API requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.delete('/admin/api/delete_image/1')
        assert response.status_code == 302

    def test_delete_image_not_found(self, client, admin_user, db_session):
        """Test deleting non-existent image."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.delete('/admin/api/delete_image/99999')
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Image not found' in data['message']

    def test_delete_image_success_not_downloaded(self, client, admin_user, db_session, sample_library, sample_game):
        """Test successfully deleting a non-downloaded image."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create pending image
        pending_image = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=False
        )
        
        db_session.add(pending_image)
        db_session.flush()
        image_id = pending_image.id

        response = client.delete(f'/admin/api/delete_image/{image_id}')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'deleted successfully' in data['message']
        
        # Verify image was deleted from database
        deleted_image = db_session.get(Image, image_id)
        assert deleted_image is None

    def test_delete_image_success_with_file_removal(self, client, admin_user, db_session, sample_library, sample_game):
        """Test successfully deleting a downloaded image with file removal."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create downloaded image
        downloaded_image = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=True
        )
        
        db_session.add(downloaded_image)
        db_session.flush()
        image_id = downloaded_image.id

        with patch('os.path.exists') as mock_exists, \
             patch('os.remove') as mock_remove, \
             patch('modules.routes_admin_ext.images.current_app') as mock_app:
            
            mock_app.config = {'IMAGE_SAVE_PATH': '/test/path'}
            mock_exists.return_value = True
            
            response = client.delete(f'/admin/api/delete_image/{image_id}')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Verify file removal was attempted
            mock_remove.assert_called_once()

    def test_delete_image_handles_exception(self, client, admin_user, db_session, sample_library, sample_game):
        """Test delete_image handles database exceptions."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create image
        test_image = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover.jpg',
            url='cover.jpg',
            is_downloaded=False
        )
        
        db_session.add(test_image)
        db_session.flush()
        image_id = test_image.id

        with patch('modules.db.session.delete') as mock_delete:
            mock_delete.side_effect = Exception("Database error")
            
            response = client.delete(f'/admin/api/delete_image/{image_id}')
            assert response.status_code == 500
            
            data = json.loads(response.data)
            assert data['success'] is False


class TestRetryFailedImagesAPI:
    """Tests for the retry_failed_images API endpoint."""
    
    def test_retry_failed_images_requires_login(self, client):
        """Test that retry_failed_images API requires authentication."""
        response = client.post('/admin/api/retry_failed_images')
        assert response.status_code == 302

    def test_retry_failed_images_requires_admin(self, client, regular_user):
        """Test that retry_failed_images API requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/api/retry_failed_images')
        assert response.status_code == 302

    def test_retry_failed_images_no_failed_images(self, client, admin_user, db_session):
        """Test retry with no failed images."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/api/retry_failed_images')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['retried'] == 0

    def test_retry_failed_images_success(self, client, admin_user, db_session, sample_library, sample_game):
        """Test successfully retrying failed images."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create failed images (not downloaded but have download_url)
        failed_image1 = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover1.jpg',
            url='cover1.jpg',
            is_downloaded=False
        )
        
        failed_image2 = Image(
            game_uuid=sample_game.uuid,
            image_type='screenshot',
            download_url='https://example.com/screenshot.jpg',
            url='screenshot.jpg',
            is_downloaded=False
        )
        
        db_session.add_all([failed_image1, failed_image2])
        db_session.flush()

        with patch('modules.utils_functions.download_image') as mock_download, \
             patch('modules.routes_admin_ext.images.current_app') as mock_app:
            
            mock_app.config = {'IMAGE_SAVE_PATH': '/test/path'}
            mock_download.return_value = True
            
            response = client.post('/admin/api/retry_failed_images')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['retried'] == 2
            
            # Check images were marked as downloaded
            db_session.refresh(failed_image1)
            db_session.refresh(failed_image2)
            assert failed_image1.is_downloaded is True
            assert failed_image2.is_downloaded is True

    def test_retry_failed_images_partial_success(self, client, admin_user, db_session, sample_library, sample_game):
        """Test retry with some images failing."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create failed images
        failed_image1 = Image(
            game_uuid=sample_game.uuid,
            image_type='cover',
            download_url='https://example.com/cover1.jpg',
            url='cover1.jpg',
            is_downloaded=False
        )
        
        failed_image2 = Image(
            game_uuid=sample_game.uuid,
            image_type='screenshot',
            download_url='https://example.com/screenshot.jpg',
            url='screenshot.jpg',
            is_downloaded=False
        )
        
        db_session.add_all([failed_image1, failed_image2])
        db_session.flush()

        with patch('modules.utils_functions.download_image') as mock_download, \
             patch('modules.routes_admin_ext.images.current_app') as mock_app:
            
            mock_app.config = {'IMAGE_SAVE_PATH': '/test/path'}
            # First call succeeds, second fails
            mock_download.side_effect = [True, Exception("Download failed")]
            
            response = client.post('/admin/api/retry_failed_images')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['retried'] == 1

    def test_retry_failed_images_handles_exception(self, client, admin_user, db_session, monkeypatch):
        """Test retry_failed_images handles database exceptions."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Mock the select function to throw an exception
        with patch('modules.routes_admin_ext.images.select') as mock_select:
            mock_select.side_effect = Exception("Database error")
            
            response = client.post('/admin/api/retry_failed_images')
            assert response.status_code == 500
            
            data = json.loads(response.data)
            assert data['success'] is False


class TestClearDownloadedQueueAPI:
    """Tests for the clear_downloaded_queue API endpoint."""
    
    def test_clear_downloaded_queue_requires_login(self, client):
        """Test that clear_downloaded_queue API requires authentication."""
        response = client.post('/admin/api/clear_downloaded_queue')
        assert response.status_code == 302

    def test_clear_downloaded_queue_requires_admin(self, client, regular_user):
        """Test that clear_downloaded_queue API requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/api/clear_downloaded_queue')
        assert response.status_code == 302

    def test_clear_downloaded_queue_success(self, client, admin_user, db_session, sample_library, sample_game):
        """Test clearing downloaded queue (counting only)."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create downloaded images
        for i in range(3):
            downloaded_image = Image(
                game_uuid=sample_game.uuid,
                image_type='cover',
                download_url=f'https://example.com/cover{i}.jpg',
                url=f'cover{i}.jpg',
                is_downloaded=True
            )
            db_session.add(downloaded_image)
        
        db_session.flush()

        response = client.post('/admin/api/clear_downloaded_queue')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'downloaded images cleared' in data['message']

    def test_clear_downloaded_queue_handles_exception(self, client, admin_user, db_session, monkeypatch):
        """Test clear_downloaded_queue handles database exceptions."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Mock the func.count to throw an exception
        with patch('modules.routes_admin_ext.images.func.count') as mock_count:
            mock_count.side_effect = Exception("Database error")
            
            response = client.post('/admin/api/clear_downloaded_queue')
            assert response.status_code == 500
            
            data = json.loads(response.data)
            assert data['success'] is False


class TestBackgroundDownloaderAPI:
    """Tests for background downloader API endpoints."""
    
    def test_start_background_downloader_requires_login(self, client):
        """Test that start_background_downloader API requires authentication."""
        response = client.post('/admin/api/start_background_downloader')
        assert response.status_code == 302

    def test_start_background_downloader_requires_admin(self, client, regular_user):
        """Test that start_background_downloader API requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/api/start_background_downloader')
        assert response.status_code == 302

    @patch('modules.utils_game_core.start_background_image_downloader')
    def test_start_background_downloader_success(self, mock_start_downloader, client, admin_user):
        """Test successfully starting background downloader."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        mock_thread = MagicMock()
        mock_start_downloader.return_value = mock_thread
        
        response = client.post('/admin/api/start_background_downloader')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'Background image downloader started' in data['message']
        
        mock_start_downloader.assert_called_once_with(interval_seconds=60)

    @patch('modules.utils_game_core.start_background_image_downloader')
    def test_start_background_downloader_handles_exception(self, mock_start_downloader, client, admin_user):
        """Test start_background_downloader handles exceptions."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        mock_start_downloader.side_effect = Exception("Failed to start")
        
        response = client.post('/admin/api/start_background_downloader')
        assert response.status_code == 500
        
        data = json.loads(response.data)
        assert data['success'] is False


class TestTurboDownloadAPI:
    """Tests for turbo download API endpoints."""
    
    def test_turbo_download_requires_login(self, client):
        """Test that turbo_download API requires authentication."""
        response = client.post('/admin/api/turbo_download')
        assert response.status_code == 302

    def test_turbo_download_requires_admin(self, client, regular_user):
        """Test that turbo_download API requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/api/turbo_download')
        assert response.status_code == 302

    def test_turbo_download_success_default_params(self, client, admin_user, monkeypatch):
        """Test turbo download with default parameters."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        def mock_turbo_download(*args, **kwargs):
            return {
                'downloaded': 15,
                'failed': 2,
                'message': 'Turbo download completed'
            }
        
        monkeypatch.setattr('modules.utils_game_core.turbo_download_images', mock_turbo_download)
        
        response = client.post('/admin/api/turbo_download', 
                             json={},  # Send empty JSON to set proper content type
                             content_type='application/json')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['downloaded'] == 15
        assert data['failed'] == 2
        assert data['message'] == 'Turbo download completed'

    def test_turbo_download_success_custom_params(self, client, admin_user, monkeypatch):
        """Test turbo download with custom parameters."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        def mock_turbo_download(*args, **kwargs):
            return {
                'downloaded': 25,
                'failed': 0,
                'message': 'Custom turbo download completed'
            }
        
        monkeypatch.setattr('modules.utils_game_core.turbo_download_images', mock_turbo_download)
        
        response = client.post('/admin/api/turbo_download', 
                             json={'batch_size': 50, 'max_workers': 8})
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['downloaded'] == 25
        assert data['failed'] == 0

    @patch('modules.utils_game_core.turbo_download_images')
    def test_turbo_download_handles_exception(self, mock_turbo_download, client, admin_user):
        """Test turbo_download handles exceptions."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        mock_turbo_download.side_effect = Exception("Turbo download failed")
        
        response = client.post('/admin/api/turbo_download')
        assert response.status_code == 500
        
        data = json.loads(response.data)
        assert data['success'] is False

    def test_start_turbo_downloader_requires_login(self, client):
        """Test that start_turbo_downloader API requires authentication."""
        response = client.post('/admin/api/start_turbo_downloader')
        assert response.status_code == 302

    def test_start_turbo_downloader_requires_admin(self, client, regular_user):
        """Test that start_turbo_downloader API requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/api/start_turbo_downloader')
        assert response.status_code == 302

    def test_start_turbo_downloader_success_default_params(self, client, admin_user, monkeypatch):
        """Test start turbo downloader with default parameters."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        def mock_start_turbo(*args, **kwargs):
            return MagicMock()  # Return a mock thread object
        
        monkeypatch.setattr('modules.utils_game_core.start_turbo_background_downloader', mock_start_turbo)
        
        response = client.post('/admin/api/start_turbo_downloader',
                             json={},  # Send empty JSON to set proper content type
                             content_type='application/json')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'TURBO background downloader started' in data['message']
        assert '4 workers' in data['message']
        assert '50 batch size' in data['message']
        assert '30s interval' in data['message']

    @patch('modules.utils_game_core.start_turbo_background_downloader')
    def test_start_turbo_downloader_success_custom_params(self, mock_start_turbo, client, admin_user):
        """Test start turbo downloader with custom parameters."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        mock_thread = MagicMock()
        mock_start_turbo.return_value = mock_thread
        
        custom_params = {
            'max_workers': 8,
            'batch_size': 100,
            'interval': 15
        }
        
        response = client.post('/admin/api/start_turbo_downloader', json=custom_params)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert '8 workers' in data['message']
        assert '100 batch size' in data['message']
        assert '15s interval' in data['message']
        
        mock_start_turbo.assert_called_once_with(
            interval_seconds=15,
            max_workers=8,
            batch_size=100
        )

    @patch('modules.utils_game_core.start_turbo_background_downloader')
    def test_start_turbo_downloader_handles_exception(self, mock_start_turbo, client, admin_user):
        """Test start_turbo_downloader handles exceptions."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        mock_start_turbo.side_effect = Exception("Failed to start turbo downloader")
        
        response = client.post('/admin/api/start_turbo_downloader')
        assert response.status_code == 500
        
        data = json.loads(response.data)
        assert data['success'] is False