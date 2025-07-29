import pytest
from unittest.mock import patch, MagicMock, Mock
import os

from modules.utils_scanning import (
    try_add_game, process_game_with_fallback, log_unmatched_folder,
    process_game_updates, process_game_extras, refresh_images_in_background,
    delete_game_images, is_scan_job_running
)


class TestTryAddGame:
    """Test the try_add_game function."""
    
    @patch('modules.utils_scanning.retrieve_and_save_game')
    @patch('modules.utils_scanning.check_existing_game_by_path')
    def test_try_add_game_success_new_game(self, mock_check_existing, mock_retrieve):
        """Test successful addition of a new game."""
        # Setup
        mock_check_existing.return_value = None  # Game doesn't exist
        mock_retrieve.return_value = Mock()  # Game successfully retrieved
        
        # Execute
        result = try_add_game("Test Game", "/path/to/game", "scan123", "lib-uuid")
        
        # Verify
        assert result is not None
        mock_check_existing.assert_called_once_with("/path/to/game")
        mock_retrieve.assert_called_once_with("Test Game", "/path/to/game", "scan123", "lib-uuid")
    
    @patch('modules.utils_scanning.check_existing_game_by_path')
    def test_try_add_game_existing_game_skip_check(self, mock_check_existing):
        """Test skipping existing game when check_exists=False."""
        # Setup
        mock_existing_game = Mock()
        mock_check_existing.return_value = mock_existing_game
        
        # Execute
        result = try_add_game("Test Game", "/path/to/game", "scan123", "lib-uuid", check_exists=False)
        
        # Verify
        assert result == mock_existing_game
        mock_check_existing.assert_not_called()
    
    @patch('modules.utils_scanning.retrieve_and_save_game')
    @patch('modules.utils_scanning.check_existing_game_by_path')
    def test_try_add_game_existing_game_with_check(self, mock_check_existing, mock_retrieve):
        """Test handling existing game when check_exists=True."""
        # Setup
        mock_existing_game = Mock()
        mock_check_existing.return_value = mock_existing_game
        
        # Execute
        result = try_add_game("Test Game", "/path/to/game", "scan123", "lib-uuid", check_exists=True)
        
        # Verify
        assert result == mock_existing_game
        mock_check_existing.assert_called_once_with("/path/to/game")
        mock_retrieve.assert_not_called()


class TestProcessGameWithFallback:
    """Test the process_game_with_fallback function."""
    
    @patch('modules.utils_scanning.try_add_game')
    def test_process_game_with_fallback_success_first_try(self, mock_try_add):
        """Test successful game processing on first attempt."""
        # Setup
        mock_game = Mock()
        mock_try_add.return_value = mock_game
        
        # Execute
        result = process_game_with_fallback("Test Game", "/path/to/game", "scan123", "lib-uuid")
        
        # Verify
        assert result == mock_game
        mock_try_add.assert_called_once_with("Test Game", "/path/to/game", "scan123", "lib-uuid")
    
    @patch('modules.utils_scanning.try_add_game')
    def test_process_game_with_fallback_success_second_try(self, mock_try_add):
        """Test successful game processing on second attempt with cleaned name."""
        # Setup
        mock_try_add.side_effect = [None, Mock()]  # First fails, second succeeds
        
        # Execute
        result = process_game_with_fallback("Test Game (2023)", "/path/to/game", "scan123", "lib-uuid")
        
        # Verify
        assert result is not None
        assert mock_try_add.call_count == 2
        # First call with original name
        mock_try_add.assert_any_call("Test Game (2023)", "/path/to/game", "scan123", "lib-uuid")
        # Second call with cleaned name (year removed)
        mock_try_add.assert_any_call("Test Game", "/path/to/game", "scan123", "lib-uuid")
    
    @patch('modules.utils_scanning.try_add_game')
    def test_process_game_with_fallback_all_attempts_fail(self, mock_try_add):
        """Test game processing when all attempts fail."""
        # Setup
        mock_try_add.return_value = None  # All attempts fail
        
        # Execute
        result = process_game_with_fallback("Test Game", "/path/to/game", "scan123", "lib-uuid")
        
        # Verify
        assert result is None


class TestLogUnmatchedFolder:
    """Test the log_unmatched_folder function."""
    
    @patch('modules.utils_scanning.ScanJob')
    @patch('modules.utils_scanning.db')
    def test_log_unmatched_folder_success(self, mock_db, mock_scan_job):
        """Test successful logging of unmatched folder."""
        # Setup
        mock_scan_job_instance = Mock()
        mock_scan_job.query.filter_by.return_value.first.return_value = mock_scan_job_instance
        
        # Execute
        log_unmatched_folder("scan123", "/path/to/folder", "unmatched", "lib-uuid")
        
        # Verify
        mock_scan_job.query.filter_by.assert_called_once_with(id="scan123")
        mock_db.session.commit.assert_called_once()
    
    @patch('modules.utils_scanning.ScanJob')
    def test_log_unmatched_folder_no_scan_job(self, mock_scan_job):
        """Test logging when scan job is not found."""
        # Setup
        mock_scan_job.query.filter_by.return_value.first.return_value = None
        
        # Execute - Should not raise exception
        log_unmatched_folder("nonexistent", "/path/to/folder", "unmatched")
        
        # Verify
        mock_scan_job.query.filter_by.assert_called_once_with(id="nonexistent")


class TestProcessGameUpdates:
    """Test the process_game_updates function."""
    
    @patch('modules.utils_scanning.os.listdir')
    @patch('modules.utils_scanning.os.path.isdir')
    @patch('modules.utils_scanning.try_add_game')
    def test_process_game_updates_success(self, mock_try_add, mock_isdir, mock_listdir):
        """Test successful processing of game updates."""
        # Setup
        mock_listdir.return_value = ['Update1', 'Update2', 'file.txt']
        mock_isdir.side_effect = lambda path: 'Update' in path  # Only Update folders are dirs
        mock_try_add.return_value = Mock()
        
        # Execute
        process_game_updates("Test Game", "/path/to/game", "/path/to/updates", "lib-uuid")
        
        # Verify
        assert mock_try_add.call_count == 2  # Two update folders processed
        mock_try_add.assert_any_call("Test Game - Update1", "/path/to/updates/Update1", None, "lib-uuid", False)
        mock_try_add.assert_any_call("Test Game - Update2", "/path/to/updates/Update2", None, "lib-uuid", False)
    
    @patch('modules.utils_scanning.os.listdir')
    def test_process_game_updates_no_updates(self, mock_listdir):
        """Test processing when no update folders exist."""
        # Setup
        mock_listdir.return_value = []
        
        # Execute - Should not raise exception
        process_game_updates("Test Game", "/path/to/game", "/path/to/updates", "lib-uuid")
        
        # Verify
        mock_listdir.assert_called_once_with("/path/to/updates")
    
    @patch('modules.utils_scanning.os.listdir')
    def test_process_game_updates_os_error(self, mock_listdir):
        """Test processing when OS error occurs."""
        # Setup
        mock_listdir.side_effect = OSError("Permission denied")
        
        # Execute - Should not raise exception
        process_game_updates("Test Game", "/path/to/game", "/path/to/updates", "lib-uuid")
        
        # Verify
        mock_listdir.assert_called_once_with("/path/to/updates")


class TestProcessGameExtras:
    """Test the process_game_extras function."""
    
    @patch('modules.utils_scanning.os.listdir')
    @patch('modules.utils_scanning.os.path.isdir')
    @patch('modules.utils_scanning.try_add_game')
    def test_process_game_extras_success(self, mock_try_add, mock_isdir, mock_listdir):
        """Test successful processing of game extras."""
        # Setup
        mock_listdir.return_value = ['DLC1', 'DLC2', 'readme.txt']
        mock_isdir.side_effect = lambda path: 'DLC' in path  # Only DLC folders are dirs
        mock_try_add.return_value = Mock()
        
        # Execute
        process_game_extras("Test Game", "/path/to/game", "/path/to/extras", "lib-uuid")
        
        # Verify
        assert mock_try_add.call_count == 2  # Two extra folders processed
        mock_try_add.assert_any_call("Test Game - DLC1", "/path/to/extras/DLC1", None, "lib-uuid", False)
        mock_try_add.assert_any_call("Test Game - DLC2", "/path/to/extras/DLC2", None, "lib-uuid", False)
    
    @patch('modules.utils_scanning.os.listdir')
    def test_process_game_extras_no_extras(self, mock_listdir):
        """Test processing when no extra folders exist."""
        # Setup
        mock_listdir.return_value = []
        
        # Execute - Should not raise exception
        process_game_extras("Test Game", "/path/to/game", "/path/to/extras", "lib-uuid")
        
        # Verify
        mock_listdir.assert_called_once_with("/path/to/extras")


class TestRefreshImagesInBackground:
    """Test the refresh_images_in_background function."""
    
    @patch('modules.utils_scanning.threading.Thread')
    @patch('modules.utils_scanning.download_images_for_game')
    def test_refresh_images_in_background_success(self, mock_download, mock_thread):
        """Test successful background image refresh."""
        # Setup
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        # Execute
        refresh_images_in_background("test-uuid")
        
        # Verify
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()


class TestDeleteGameImages:
    """Test the delete_game_images function."""
    
    @patch('modules.utils_scanning.Image')
    @patch('modules.utils_scanning.db')
    @patch('modules.utils_scanning.os.remove')
    @patch('modules.utils_scanning.current_app')
    def test_delete_game_images_success(self, mock_app, mock_remove, mock_db, mock_image):
        """Test successful deletion of game images."""
        # Setup
        mock_app.config = {'UPLOAD_FOLDER': '/test/upload'}
        mock_image1 = Mock()
        mock_image1.filename = 'image1.jpg'
        mock_image2 = Mock()
        mock_image2.filename = 'image2.jpg'
        mock_image.query.filter_by.return_value.all.return_value = [mock_image1, mock_image2]
        
        # Execute
        delete_game_images("test-uuid")
        
        # Verify
        mock_image.query.filter_by.assert_called_once_with(game_uuid="test-uuid")
        assert mock_remove.call_count == 2  # Two images deleted
        assert mock_db.session.delete.call_count == 2  # Two records deleted
        mock_db.session.commit.assert_called_once()
    
    @patch('modules.utils_scanning.Image')
    def test_delete_game_images_no_images(self, mock_image):
        """Test deletion when no images exist."""
        # Setup
        mock_image.query.filter_by.return_value.all.return_value = []
        
        # Execute - Should not raise exception
        delete_game_images("test-uuid")
        
        # Verify
        mock_image.query.filter_by.assert_called_once_with(game_uuid="test-uuid")


class TestIsScanJobRunning:
    """Test the is_scan_job_running function."""
    
    @patch('modules.utils_scanning.ScanJob')
    def test_is_scan_job_running_true(self, mock_scan_job):
        """Test when scan jobs are running."""
        # Setup
        mock_scan_job.query.filter_by.return_value.count.return_value = 1
        
        # Execute
        result = is_scan_job_running()
        
        # Verify
        assert result is True
        mock_scan_job.query.filter_by.assert_called_once_with(status='running')
    
    @patch('modules.utils_scanning.ScanJob')
    def test_is_scan_job_running_false(self, mock_scan_job):
        """Test when no scan jobs are running."""
        # Setup
        mock_scan_job.query.filter_by.return_value.count.return_value = 0
        
        # Execute
        result = is_scan_job_running()
        
        # Verify
        assert result is False
        mock_scan_job.query.filter_by.assert_called_once_with(status='running')