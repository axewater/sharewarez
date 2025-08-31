import pytest
import os
import tempfile
import threading
import time
from datetime import datetime, UTC
from unittest.mock import patch, MagicMock, mock_open, call
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from werkzeug.utils import secure_filename

from modules import create_app, db
from modules.models import (
    Game, Image, Library, GlobalSettings, Developer, Publisher, 
    Genre, Theme, GameMode, Platform, PlayerPerspective, GameURL, 
    ScanJob, Category, Status
)
from modules.platform import LibraryPlatform
from modules.utils_game_core import (
    category_mapping, status_mapping, create_game_instance, 
    check_existing_game_by_path, check_existing_game_by_igdb_id,
    store_image_url_for_download, smart_process_images_for_game,
    download_images_for_game, download_images_for_game_turbo,
    process_and_save_image, download_single_image_worker,
    retrieve_and_save_game, fetch_and_store_game_urls,
    enumerate_companies, get_game_by_uuid, remove_from_lib,
    delete_game, download_pending_images, start_background_image_downloader,
    turbo_download_images, start_turbo_background_downloader,
    find_missing_images_for_library, queue_missing_images_for_download,
    process_missing_images_for_scan
)


def safe_cleanup_database(db_session):
    """Safely clean up database records respecting foreign key constraints."""
    from sqlalchemy import delete
    
    # Clean up in order to respect foreign key constraints
    db_session.execute(delete(Image))
    db_session.execute(delete(GameURL))
    db_session.execute(delete(Game))
    db_session.execute(delete(Library))
    db_session.execute(delete(Developer))
    db_session.execute(delete(Publisher))
    db_session.execute(delete(Genre))
    db_session.execute(delete(Theme))
    db_session.execute(delete(GameMode))
    db_session.execute(delete(Platform))
    db_session.execute(delete(PlayerPerspective))
    db_session.execute(delete(ScanJob))
    db_session.commit()



@pytest.fixture
def sample_platform(db_session):
    """Create a sample platform for testing."""
    platform = Platform(name='Test Platform')
    db_session.add(platform)
    db_session.flush()
    return platform


@pytest.fixture
def sample_library(db_session):
    """Create a sample library for testing."""
    library = Library(
        uuid=str(uuid4()),
        name='Test Library',
        platform=LibraryPlatform.PCWIN
    )
    db_session.add(library)
    db_session.flush()
    return library


@pytest.fixture
def sample_game(db_session, sample_library, sample_global_settings):
    """Create a sample game for testing."""
    import random
    unique_id = random.randint(100000, 999999)
    game = Game(
        uuid=str(uuid4()),
        library_uuid=sample_library.uuid,
        igdb_id=unique_id,
        name='Test Game',
        full_disk_path=f'/test/game/path/{unique_id}',
        size=1024000,
        date_created=datetime.now(UTC),
        date_identified=datetime.now(UTC)
    )
    db_session.add(game)
    db_session.flush()
    return game


@pytest.fixture
def sample_image(db_session, sample_game, sample_global_settings):
    """Create a sample image for testing."""
    image = Image(
        game_uuid=sample_game.uuid,
        image_type='cover',
        url='test_cover.jpg',
        igdb_image_id='54321',
        download_url='https://example.com/image.jpg',
        is_downloaded=False
    )
    db_session.add(image)
    db_session.flush()
    return image


@pytest.fixture
def sample_global_settings(db_session):
    """Create sample global settings for testing."""
    # Delete any existing settings first to avoid multiple results
    from sqlalchemy import delete
    db_session.execute(delete(GlobalSettings))
    db_session.flush()
    
    settings = GlobalSettings(
        use_turbo_image_downloads=False,
        turbo_download_threads=4,
        discord_webhook_url='https://discord.com/api/webhooks/test',
        discord_notify_new_games=True
    )
    db_session.add(settings)
    db_session.flush()
    return settings


@pytest.fixture
def mock_igdb_response():
    """Mock IGDB API response data."""
    return [{
        'id': 12345,
        'name': 'Test Game',
        'summary': 'A test game',
        'url': 'https://igdb.com/games/test-game',
        'first_release_date': 1640995200,  # 2022-01-01
        'aggregated_rating': 85.5,
        'aggregated_rating_count': 100,
        'rating': 88.2,
        'rating_count': 50,
        'slug': 'test-game',
        'status': 1,  # Released
        'category': 0,  # Main game
        'total_rating': 87.0,
        'total_rating_count': 150,
        'cover': 98765,
        'screenshots': [11111, 22222],
        'videos': [{'video_id': 'abc123'}],
        'genres': [{'name': 'Action'}],
        'themes': [{'name': 'Horror'}],
        'game_modes': [{'name': 'Single player'}],
        'platforms': [{'name': 'PC (Microsoft Windows)'}],
        'player_perspectives': [{'name': 'First person'}],
        'involved_companies': [1, 2, 3]
    }]


@pytest.fixture
def mock_company_response():
    """Mock IGDB company response data."""
    return [
        {'company': {'name': 'Test Developer'}, 'developer': True, 'publisher': False, 'game': 12345},
        {'company': {'name': 'Test Publisher'}, 'developer': False, 'publisher': True, 'game': 12345}
    ]


class TestDataMappings:
    """Test the IGDB API mapping dictionaries."""
    
    def test_category_mapping_values(self):
        """Test category mapping contains expected values."""
        assert category_mapping[0] == Category.MAIN_GAME
        assert category_mapping[1] == Category.DLC_ADDON
        assert category_mapping[2] == Category.EXPANSION
        assert category_mapping[8] == Category.REMAKE
        assert category_mapping[9] == Category.REMASTER
        
    def test_status_mapping_values(self):
        """Test status mapping contains expected values."""
        assert status_mapping[1] == Status.RELEASED
        assert status_mapping[2] == Status.ALPHA
        assert status_mapping[3] == Status.BETA
        assert status_mapping[4] == Status.EARLY_ACCESS
        assert status_mapping[6] == Status.OFFLINE
        assert status_mapping[7] == Status.CANCELLED
        
    def test_category_mapping_completeness(self):
        """Test category mapping covers all expected keys."""
        expected_keys = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
        assert set(category_mapping.keys()) == set(expected_keys)
        
    def test_status_mapping_completeness(self):
        """Test status mapping covers expected keys."""
        expected_keys = [1, 2, 3, 4, 6, 7]
        assert set(status_mapping.keys()) == set(expected_keys)


# TODO(human) - Add the remaining test classes here

class TestCoreGameCreationFunctions:
    """Test core game creation and lookup functions."""
    
    @patch('modules.utils_game_core.fetch_and_store_game_urls')
    def test_create_game_instance_success(self, mock_fetch_urls, db_session, sample_library, mock_igdb_response, sample_global_settings):
        """Test successful game instance creation."""
        game_data = mock_igdb_response[0]
        full_disk_path = '/test/game/path'
        folder_size_bytes = 1024000
        
        result = create_game_instance(game_data, full_disk_path, folder_size_bytes, sample_library.uuid)
        
        assert result is not None
        assert result.name == 'Test Game'
        assert result.igdb_id == 12345
        assert result.library_uuid == sample_library.uuid
        assert result.full_disk_path == full_disk_path
        assert result.size == folder_size_bytes
        assert result.category == Category.MAIN_GAME
        assert result.status == Status.RELEASED
    
    def test_create_game_instance_invalid_data(self, db_session, sample_library, sample_global_settings):
        """Test game instance creation with invalid data."""
        result = create_game_instance("not a dict", '/path', 1024, sample_library.uuid)
        assert result is None
    
    def test_create_game_instance_library_not_found(self, db_session, sample_global_settings):
        """Test game instance creation with non-existent library."""
        game_data = {'id': 123, 'name': 'Test Game'}
        result = create_game_instance(game_data, '/path', 1024, 'non-existent-uuid')
        assert result is None
    
    def test_check_existing_game_by_path_found(self, db_session, sample_game, sample_global_settings):
        """Test finding existing game by path."""
        result = check_existing_game_by_path(sample_game.full_disk_path)
        assert result is not None
        assert result.uuid == sample_game.uuid
    
    def test_check_existing_game_by_path_not_found(self, db_session, sample_global_settings):
        """Test not finding game by path."""
        result = check_existing_game_by_path('/non/existent/path')
        assert result is None
    
    def test_check_existing_game_by_igdb_id_found(self, db_session, sample_game, sample_global_settings):
        """Test finding existing game by IGDB ID."""
        result = check_existing_game_by_igdb_id(sample_game.igdb_id)
        assert result is not None
        assert result.uuid == sample_game.uuid
    
    def test_check_existing_game_by_igdb_id_not_found(self, db_session, sample_global_settings):
        """Test not finding game by IGDB ID."""
        result = check_existing_game_by_igdb_id(99999)
        assert result is None


class TestImageProcessingFunctions:
    """Test image processing and download functions."""
    
    @patch('modules.utils_game_core.make_igdb_api_request')
    def test_store_image_url_for_download_cover(self, mock_api, db_session, sample_game, sample_global_settings):
        """Test storing cover image URL for download."""
        mock_api.return_value = [{'url': '//images.igdb.com/igdb/image/upload/t_thumb/test.jpg'}]
        
        store_image_url_for_download(sample_game.uuid, 98765, 'cover')
        
        # Check image was stored in database
        images = db_session.query(Image).filter_by(game_uuid=sample_game.uuid).all()
        assert len(images) == 1
        assert images[0].image_type == 'cover'
        assert images[0].igdb_image_id == '98765'
        assert images[0].download_url == 'https://images.igdb.com/igdb/image/upload/t_original/test.jpg'
        assert images[0].is_downloaded is False
    
    @patch('modules.utils_game_core.make_igdb_api_request')
    def test_store_image_url_for_download_screenshot(self, mock_api, db_session, sample_game, sample_global_settings):
        """Test storing screenshot image URL for download."""
        mock_api.return_value = [{'url': '//images.igdb.com/igdb/image/upload/t_thumb/screenshot.jpg'}]
        
        store_image_url_for_download(sample_game.uuid, 11111, 'screenshot')
        
        images = db_session.query(Image).filter_by(game_uuid=sample_game.uuid).all()
        assert len(images) == 1
        assert images[0].image_type == 'screenshot'
        assert images[0].igdb_image_id == '11111'
        assert images[0].download_url == 'https://images.igdb.com/igdb/image/upload/t_original/screenshot.jpg'
    
    @patch('modules.utils_game_core.make_igdb_api_request')
    def test_store_image_url_for_download_api_failure(self, mock_api, db_session, sample_game, sample_global_settings):
        """Test handling API failure when storing image URL."""
        mock_api.return_value = {'error': 'API Error'}
        
        store_image_url_for_download(sample_game.uuid, 98765, 'cover')
        
        images = db_session.query(Image).filter_by(game_uuid=sample_game.uuid).all()
        assert len(images) == 0