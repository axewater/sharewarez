import pytest
import os
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timezone
from uuid import uuid4

from modules import create_app, db
from modules.models import (
    Game, Library, LibraryPlatform, UnmatchedFolder, 
    GameUpdate, GameExtra, GlobalSettings, ScanJob, Image
)
from modules.utils_scanning import (
    try_add_game, process_game_with_fallback, log_unmatched_folder,
    process_game_updates, process_game_extras, refresh_images_in_background,
    delete_game_images, is_scan_job_running
)


# Helper functions
def get_or_create_library(db_session, name, platform=LibraryPlatform.PCWIN):
    """Get existing library or create new one with unique name."""
    existing = db_session.query(Library).filter_by(name=name).first()
    if existing:
        return existing
    
    library = Library(
        uuid=str(uuid4()),
        name=name,
        platform=platform
    )
    db_session.add(library)
    db_session.flush()
    return library


def get_or_create_scan_job(db_session, status='Running'):
    """Get existing scan job or create new one."""
    existing = db_session.query(ScanJob).filter_by(status=status).first()
    if existing:
        return existing
    
    scan_job = ScanJob(
        status=status,
        folders_failed=0,
        folders_success=0,
        total_folders=0
    )
    db_session.add(scan_job)
    db_session.flush()
    return scan_job


# Fixtures
@pytest.fixture
def sample_library(db_session):
    """Create a sample library for testing."""
    return get_or_create_library(db_session, 'Test Library')


@pytest.fixture
def sample_scan_job(db_session):
    """Create a sample scan job for testing."""
    return get_or_create_scan_job(db_session)


@pytest.fixture
def sample_global_settings(db_session):
    """Create default global settings for testing."""
    existing = db_session.query(GlobalSettings).first()
    if existing:
        return existing
    
    settings = GlobalSettings(
        use_turbo_image_downloads=False,
        max_concurrent_downloads=5,
        image_download_timeout=30,
        update_folder_name='Updates',
        extras_folder_name='Extras'
    )
    db_session.add(settings)
    db_session.flush()
    return settings


@pytest.fixture
def sample_game(db_session, sample_library):
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
        date_created=datetime.now(timezone.utc),
        date_identified=datetime.now(timezone.utc)
    )
    db_session.add(game)
    db_session.flush()
    return game


@pytest.fixture
def mock_igdb_response():
    """Mock IGDB API response data."""
    return [
        {
            'id': 12345,
            'name': 'Test Game',
            'summary': 'A test game',
            'cover': {
                'id': 54321,
                'url': '//images.igdb.com/igdb/image/upload/t_cover_big/test_cover.jpg'
            },
            'screenshots': [
                {
                    'id': 11111,
                    'url': '//images.igdb.com/igdb/image/upload/t_screenshot_big/screenshot1.jpg'
                },
                {
                    'id': 22222,
                    'url': '//images.igdb.com/igdb/image/upload/t_screenshot_big/screenshot2.jpg'
                }
            ]
        }
    ]


# Test Classes
class TestTryAddGame:
    """Test the try_add_game function."""
    
    @patch('modules.utils_game_core.retrieve_and_save_game')
    def test_try_add_game_success(self, mock_retrieve, db_session, sample_library, sample_scan_job):
        """Test successful game addition."""
        mock_retrieve.return_value = MagicMock(spec=Game)

        result = try_add_game(
            'Test Game',
            '/test/path',
            sample_scan_job.id,
            sample_library.uuid
        )

        assert result is True
        mock_retrieve.assert_called_once_with(
            'Test Game',
            '/test/path',
            sample_scan_job.id,
            sample_library.uuid,
            fetch_hltb=False,
            settings=None
        )
    
    @patch('modules.utils_game_core.retrieve_and_save_game')
    def test_try_add_game_retrieve_fails(self, mock_retrieve, db_session, sample_library, sample_scan_job):
        """Test game addition when retrieve_and_save_game fails."""
        mock_retrieve.return_value = None
        
        result = try_add_game(
            'Test Game', 
            '/test/path', 
            sample_scan_job.id, 
            sample_library.uuid
        )
        
        assert result is False
        mock_retrieve.assert_called_once()
    
    def test_try_add_game_library_not_found(self, db_session, sample_scan_job):
        """Test game addition when library doesn't exist."""
        fake_uuid = str(uuid4())
        
        result = try_add_game(
            'Test Game', 
            '/test/path', 
            sample_scan_job.id, 
            fake_uuid
        )
        
        assert result is False
    
    def test_try_add_game_existing_game_check_exists_true(self, db_session, sample_library, sample_scan_job, sample_game):
        """Test game addition with existing game and check_exists=True."""
        result = try_add_game(
            'Existing Game', 
            sample_game.full_disk_path, 
            sample_scan_job.id, 
            sample_library.uuid,
            check_exists=True
        )
        
        assert result is False
    
    @patch('modules.utils_game_core.retrieve_and_save_game')
    def test_try_add_game_existing_game_check_exists_false(self, mock_retrieve, db_session, sample_library, sample_scan_job, sample_game):
        """Test game addition with existing game and check_exists=False."""
        mock_retrieve.return_value = MagicMock(spec=Game)
        
        result = try_add_game(
            'Existing Game', 
            sample_game.full_disk_path, 
            sample_scan_job.id, 
            sample_library.uuid,
            check_exists=False
        )
        
        assert result is True
        mock_retrieve.assert_called_once()


class TestProcessGameWithFallback:
    """Test the process_game_with_fallback function."""
    
    @patch('modules.utils_scanning.try_add_game')
    def test_process_game_with_fallback_success_first_try(self, mock_try_add, db_session, sample_library, sample_scan_job):
        """Test successful game processing on first try."""
        mock_try_add.return_value = True

        result = process_game_with_fallback(
            'Test Game',
            '/test/path',
            sample_scan_job.id,
            sample_library.uuid
        )

        assert result is True
        mock_try_add.assert_called_once_with(
            'Test Game',
            '/test/path',
            sample_scan_job.id,
            library_uuid=sample_library.uuid,
            check_exists=False,
            fetch_hltb=False,
            settings=None
        )
    
    @patch('modules.utils_scanning.try_add_game')
    def test_process_game_with_fallback_success_with_fallback(self, mock_try_add, db_session, sample_library, sample_scan_job):
        """Test successful game processing with fallback name."""
        mock_try_add.side_effect = [False, True]  # First call fails, second succeeds

        result = process_game_with_fallback(
            'Test Game Extended',
            '/test/path',
            sample_scan_job.id,
            sample_library.uuid
        )

        assert result is True
        assert mock_try_add.call_count == 2
        # Check the fallback name was used
        mock_try_add.assert_any_call(
            'Test Game',
            '/test/path',
            sample_scan_job.id,
            library_uuid=sample_library.uuid,
            check_exists=False,
            fetch_hltb=False,
            settings=None
        )
    
    def test_process_game_with_fallback_existing_game(self, db_session, sample_library, sample_scan_job, sample_game):
        """Test processing when game already exists."""
        result = process_game_with_fallback(
            'Existing Game', 
            sample_game.full_disk_path, 
            sample_scan_job.id, 
            sample_library.uuid
        )
        
        assert result is True
    
    def test_process_game_with_fallback_existing_unmatched_folder(self, db_session, sample_library, sample_scan_job):
        """Test processing when unmatched folder already exists."""
        # Clean any existing unmatched folders first
        db_session.query(UnmatchedFolder).filter_by(folder_path='/test/unmatched/path').delete()
        db_session.flush()
        
        # Create an existing unmatched folder
        unmatched_folder = UnmatchedFolder(
            folder_path='/test/unmatched/path',
            failed_time=datetime.now(timezone.utc),
            content_type='Games',
            library_uuid=sample_library.uuid,
            status='Unmatched'
        )
        db_session.add(unmatched_folder)
        db_session.flush()
        
        # Store original failed count
        original_failed_count = sample_scan_job.folders_failed
        
        result = process_game_with_fallback(
            'Test Game', 
            '/test/unmatched/path', 
            sample_scan_job.id, 
            sample_library.uuid
        )
        
        assert result is False
        # The scan_job object should be updated in memory but not necessarily committed
        # Let's fetch it fresh from the database to check
        fresh_scan_job = db_session.get(ScanJob, sample_scan_job.id)
        assert fresh_scan_job.folders_failed == original_failed_count + 1
    
    @patch('modules.utils_scanning.try_add_game')
    @patch('modules.utils_scanning.log_unmatched_folder')
    def test_process_game_with_fallback_complete_failure(self, mock_log_unmatched, mock_try_add, db_session, sample_library, sample_scan_job):
        """Test processing when all attempts fail."""
        mock_try_add.return_value = False
        
        result = process_game_with_fallback(
            'Test Game Extended Edition', 
            '/test/path', 
            sample_scan_job.id, 
            sample_library.uuid
        )
        
        assert result is False
        # Should try original name plus fallbacks
        assert mock_try_add.call_count > 1
        mock_log_unmatched.assert_called_once_with(
            sample_scan_job.id, 
            '/test/path', 
            'Unmatched', 
            sample_library.uuid
        )


class TestLogUnmatchedFolder:
    """Test the log_unmatched_folder function."""
    
    def test_log_unmatched_folder_new_entry(self, db_session, sample_library):
        """Test logging new unmatched folder."""
        log_unmatched_folder(
            1,
            '/test/unmatched/path',
            'Unmatched',
            sample_library.uuid
        )
        
        unmatched_folder = db_session.query(UnmatchedFolder).filter_by(
            folder_path='/test/unmatched/path'
        ).first()
        
        assert unmatched_folder is not None
        assert unmatched_folder.status == 'Unmatched'
        assert unmatched_folder.library_uuid == sample_library.uuid
        assert unmatched_folder.content_type == 'Games'
    
    def test_log_unmatched_folder_existing_entry(self, db_session, sample_library):
        """Test logging existing unmatched folder does not create duplicate."""
        # Create existing entry
        existing = UnmatchedFolder(
            folder_path='/test/existing/path',
            failed_time=datetime.now(timezone.utc),
            content_type='Games',
            library_uuid=sample_library.uuid,
            status='Unmatched'
        )
        db_session.add(existing)
        db_session.flush()
        
        initial_count = db_session.query(UnmatchedFolder).count()
        
        log_unmatched_folder(
            1,
            '/test/existing/path',
            'Unmatched',
            sample_library.uuid
        )
        
        final_count = db_session.query(UnmatchedFolder).count()
        assert final_count == initial_count


class TestProcessGameUpdates:
    """Test the process_game_updates function."""
    
    @patch('os.path.isdir')
    def test_process_game_updates_success(self, mock_isdir, 
                                        db_session, sample_library, sample_game, sample_global_settings):
        """Test successful game updates processing."""
        mock_isdir.return_value = True
        
        # Mock os.listdir with different return values for different calls
        def listdir_side_effect(path):
            if path == '/test/updates/folder':
                return ['update1', 'update2']
            elif 'update1' in path:
                return ['update_file1.exe']
            elif 'update2' in path:
                return ['update_file2.exe']
            return []
        
        with patch('os.listdir', side_effect=listdir_side_effect), \
             patch('modules.utils_scanning.read_first_nfo_content', return_value='Test NFO content'):
            process_game_updates(
                sample_game.name,
                sample_game.full_disk_path,
                '/test/updates/folder',
                sample_library.uuid
            )
        
        # Check that GameUpdate records were created
        updates = db_session.query(GameUpdate).filter_by(game_uuid=sample_game.uuid).all()
        assert len(updates) == 2
        
        for update in updates:
            assert update.nfo_content == 'Test NFO content'
    
    def test_process_game_updates_game_not_found(self, db_session, sample_library, sample_global_settings):
        """Test processing updates when game doesn't exist."""
        initial_count = db_session.query(GameUpdate).count()
        
        with patch('os.listdir', return_value=[]):
            process_game_updates(
                'Nonexistent Game',
                '/nonexistent/path',
                '/test/updates/folder',
                sample_library.uuid
            )
        
        # Should not create any new updates
        final_count = db_session.query(GameUpdate).count()
        assert final_count == initial_count
    
    def test_process_game_updates_no_settings(self, db_session, sample_library, sample_game):
        """Test processing updates with no global settings."""
        # Clear any existing global settings
        db_session.query(GlobalSettings).delete()
        db_session.flush()
        
        initial_count = db_session.query(GameUpdate).count()
        
        with patch('os.listdir', return_value=[]):
            process_game_updates(
                sample_game.name,
                sample_game.full_disk_path,
                '/test/updates/folder',
                sample_library.uuid
            )
        
        # Should return early due to no settings
        final_count = db_session.query(GameUpdate).count()
        assert final_count == initial_count


class TestProcessGameExtras:
    """Test the process_game_extras function."""
    
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_process_game_extras_success(self, mock_isdir, mock_isfile,
                                       db_session, sample_library, sample_game, sample_global_settings):
        """Test successful game extras processing."""
        mock_isfile.side_effect = lambda path: not path.endswith('ignored.nfo')
        mock_isdir.return_value = False
        
        with patch('os.listdir', return_value=['extra1.txt', 'extra2.pdf', 'ignored.nfo']), \
             patch('modules.utils_scanning.read_first_nfo_content', return_value='Test NFO content'):
            process_game_extras(
                sample_game.name,
                sample_game.full_disk_path,
                '/test/extras/folder',
                sample_library.uuid
            )
        
        # Check that GameExtra records were created (excluding .nfo files)
        extras = db_session.query(GameExtra).filter_by(game_uuid=sample_game.uuid).all()
        assert len(extras) == 2
        
        for extra in extras:
            assert extra.nfo_content == 'Test NFO content'
            assert not extra.file_path.endswith('.nfo')
    
    def test_process_game_extras_game_not_found(self, db_session, sample_library, sample_global_settings):
        """Test processing extras when game doesn't exist."""
        initial_count = db_session.query(GameExtra).count()
        
        with patch('os.listdir', return_value=[]):
            process_game_extras(
                'Nonexistent Game',
                '/nonexistent/path',
                '/test/extras/folder',
                sample_library.uuid
            )
        
        # Should not create any new extras
        final_count = db_session.query(GameExtra).count()
        assert final_count == initial_count


class TestRefreshImagesInBackground:
    """Test the refresh_images_in_background function."""
    
    @patch('modules.utils_scanning.delete_game_images')
    @patch('modules.utils_game_core.process_and_save_image')
    @patch('modules.utils_scanning.make_igdb_api_request')
    def test_refresh_images_in_background_success(self, mock_api, mock_process_image, mock_delete_images,
                                                app, db_session, sample_game, mock_igdb_response):
        """Test successful image refresh."""
        mock_api.return_value = mock_igdb_response
        
        # Commit the game to database so it's visible in other sessions
        db_session.commit()
        
        # Set the config on the app before calling the function
        app.config['IGDB_API_ENDPOINT'] = 'https://api.igdb.com/v4'
        
        refresh_images_in_background(sample_game.uuid)
        
        mock_delete_images.assert_called_once_with(sample_game.uuid)
        mock_api.assert_called_once()
        
        # Should process cover and screenshots
        expected_calls = 3  # 1 cover + 2 screenshots
        assert mock_process_image.call_count == expected_calls
    
    @patch('modules.utils_scanning.make_igdb_api_request')
    def test_refresh_images_in_background_api_error(self, mock_api, app, db_session, sample_game):
        """Test image refresh when API returns error."""
        mock_api.return_value = {'error': 'API Error'}
        
        # Commit the game to database so it's visible in other sessions
        db_session.commit()
        
        # Set the config on the app before calling the function
        app.config['IGDB_API_ENDPOINT'] = 'https://api.igdb.com/v4'
        
        # Should not raise exception
        refresh_images_in_background(sample_game.uuid)
        
        mock_api.assert_called_once()
    
    def test_refresh_images_in_background_game_not_found(self, app, db_session):
        """Test image refresh when game doesn't exist."""
        fake_uuid = str(uuid4())
        
        # Should not raise exception
        refresh_images_in_background(fake_uuid)


class TestDeleteGameImages:
    """Test the delete_game_images function."""
    
    @patch('os.path.exists')
    @patch('os.remove')
    def test_delete_game_images_success(self, mock_remove, mock_exists, app, db_session, sample_game):
        """Test successful image deletion."""
        # Create test images
        image1 = Image(
            game_uuid=sample_game.uuid,
            url='/static/library/images/test1.jpg',
            image_type='cover'
        )
        image2 = Image(
            game_uuid=sample_game.uuid,
            url='/static/library/images/test2.jpg',
            image_type='screenshot'
        )
        db_session.add_all([image1, image2])
        db_session.commit()  # Commit to make visible to other sessions
        
        mock_exists.return_value = True
        
        with app.app_context():
            app.config['IMAGE_SAVE_PATH'] = '/test/images'
            delete_game_images(sample_game.uuid)
        
        assert mock_remove.call_count == 2
        
        # Check images were deleted from database
        remaining_images = db_session.query(Image).filter_by(game_uuid=sample_game.uuid).all()
        assert len(remaining_images) == 0
    
    @patch('os.path.exists')
    @patch('os.remove')
    def test_delete_game_images_file_not_found(self, mock_remove, mock_exists, app, db_session, sample_game):
        """Test image deletion when files don't exist."""
        # Create test image
        image = Image(
            game_uuid=sample_game.uuid,
            url='/static/library/images/missing.jpg',
            image_type='cover'
        )
        db_session.add(image)
        db_session.commit()  # Commit to make visible to other sessions
        
        mock_exists.return_value = False
        
        with app.app_context():
            app.config['IMAGE_SAVE_PATH'] = '/test/images'
            delete_game_images(sample_game.uuid)
        
        mock_remove.assert_not_called()
        
        # Image should still be deleted from database
        remaining_images = db_session.query(Image).filter_by(game_uuid=sample_game.uuid).all()
        assert len(remaining_images) == 0
    
    def test_delete_game_images_game_not_found(self, app, db_session):
        """Test image deletion when game doesn't exist."""
        fake_uuid = str(uuid4())
        
        # Should not raise exception
        with app.app_context():
            delete_game_images(fake_uuid)


class TestIsScanJobRunning:
    """Test the is_scan_job_running function."""
    
    def test_is_scan_job_running_true(self, db_session):
        """Test when there is a running scan job."""
        # Clean up any existing scan jobs first
        db_session.query(ScanJob).delete()
        db_session.flush()
        
        # Create a running scan job
        scan_job = ScanJob(status='Running')
        db_session.add(scan_job)
        db_session.commit()
        
        result = is_scan_job_running()
        assert result is True
    
    def test_is_scan_job_running_false_no_jobs(self, db_session):
        """Test when there are no scan jobs."""
        # Clean up any existing scan jobs
        db_session.query(ScanJob).delete()
        db_session.commit()
        
        result = is_scan_job_running()
        assert result is False
    
    def test_is_scan_job_running_false_no_running_jobs(self, db_session):
        """Test when there are scan jobs but none running."""
        # Clean up any existing scan jobs first
        db_session.query(ScanJob).delete()
        db_session.flush()
        
        # Create a non-running scan job
        scan_job = ScanJob(status='Completed')
        db_session.add(scan_job)
        db_session.commit()
        
        result = is_scan_job_running()
        assert result is False