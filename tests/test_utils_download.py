import pytest
import os
import tempfile
import zipfile
import shutil
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone
from uuid import uuid4

from modules import create_app, db
from modules.models import DownloadRequest, Game, User, GlobalSettings, Library, LibraryPlatform
from modules.utils_download import (
    zip_game, 
    update_download_request, 
    zip_folder, 
    get_zip_storage_stats
)


def safe_cleanup_database(db_session):
    """Safely clean up database records respecting foreign key constraints.""" 
    from sqlalchemy import delete
    
    db_session.execute(delete(DownloadRequest))
    db_session.execute(delete(Game))
    db_session.execute(delete(User))
    db_session.execute(delete(GlobalSettings))
    db_session.execute(delete(Library))
    db_session.commit()




@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    user = User(
        name=f'testuser_{uuid4().hex[:8]}',
        email=f'test_{uuid4().hex[:8]}@example.com',
        password_hash='hashed_password',
        role='user',
        user_id=str(uuid4())
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_library(db_session):
    """Create a sample library for testing."""
    library = Library(
        name='Test Library',
        platform=LibraryPlatform.PCWIN
    )
    db_session.add(library)
    db_session.commit()
    return library


@pytest.fixture
def sample_game(db_session, sample_library):
    """Create a sample game for testing."""
    game = Game(
        name='Test Game',
        full_disk_path='/tmp/test_game_folder',
        library_uuid=sample_library.uuid
    )
    db_session.add(game)
    db_session.commit()
    return game


@pytest.fixture
def sample_global_settings(db_session):
    """Create sample global settings for testing."""
    settings = GlobalSettings(
        update_folder_name='updates',
        extras_folder_name='extras'
    )
    db_session.add(settings)
    db_session.commit()
    return settings


@pytest.fixture
def sample_download_request(db_session, sample_user, sample_game):
    """Create a sample download request for testing."""
    download_request = DownloadRequest(
        user_id=sample_user.id,
        game_uuid=sample_game.uuid,
        status='pending',
        zip_file_path=None
    )
    db_session.add(download_request)
    db_session.commit()
    return download_request


@pytest.fixture
def temp_game_directory():
    """Create a temporary game directory structure for testing."""
    temp_dir = tempfile.mkdtemp()
    
    # Create main game files
    with open(os.path.join(temp_dir, 'game.exe'), 'w') as f:
        f.write('fake game executable')
    
    with open(os.path.join(temp_dir, 'config.cfg'), 'w') as f:
        f.write('game configuration')
        
    with open(os.path.join(temp_dir, 'readme.txt'), 'w') as f:
        f.write('game readme')
    
    # Create updates folder (should be excluded)
    updates_dir = os.path.join(temp_dir, 'updates')
    os.makedirs(updates_dir)
    with open(os.path.join(updates_dir, 'patch.exe'), 'w') as f:
        f.write('game patch')
    
    # Create extras folder (should be excluded)
    extras_dir = os.path.join(temp_dir, 'extras')
    os.makedirs(extras_dir)
    with open(os.path.join(extras_dir, 'bonus.txt'), 'w') as f:
        f.write('bonus content')
    
    # Create a subfolder with files that should be included
    sub_dir = os.path.join(temp_dir, 'data')
    os.makedirs(sub_dir)
    with open(os.path.join(sub_dir, 'game.dat'), 'w') as f:
        f.write('game data file')
    
    yield temp_dir
    
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


class TestZipGame:
    """Test cases for the zip_game function."""
    
    def test_zip_game_success(self, app, db_session, sample_download_request, 
                             sample_global_settings, temp_game_directory):
        """Test successful zipping of a game folder."""
        # Update the game's full_disk_path to our temp directory
        sample_download_request.game.full_disk_path = temp_game_directory
        db_session.commit()
        
        zip_file_path = os.path.join(app.config['ZIP_SAVE_PATH'], 'test_game.zip')
        
        # Call the function
        zip_game(sample_download_request.id, app, zip_file_path)
        
        # Refresh the download request from database
        db_session.refresh(sample_download_request)
        
        # Verify the zip file was created
        assert os.path.exists(zip_file_path)
        
        # Verify download request was updated
        assert sample_download_request.status == 'available'
        assert sample_download_request.zip_file_path == zip_file_path
        assert sample_download_request.completion_time is not None
        
        # Verify zip file contents
        with zipfile.ZipFile(zip_file_path, 'r') as zipf:
            file_list = zipf.namelist()
            # Should include main files and subfolder files
            assert 'game.exe' in file_list
            assert 'config.cfg' in file_list
            assert 'readme.txt' in file_list
            assert 'data/game.dat' in file_list
            # Should NOT include updates or extras folders
            assert not any('updates/' in name for name in file_list)
            assert not any('extras/' in name for name in file_list)
    
    def test_zip_game_excludes_folders_case_variations(self, app, db_session, 
                                                     sample_download_request, sample_global_settings):
        """Test that update/extras folders are excluded with different capitalizations."""
        temp_dir = tempfile.mkdtemp()
        try:
            # Create folders with different capitalizations
            for folder_name in ['updates', 'Updates', 'UPDATES', 'extras', 'Extras', 'EXTRAS']:
                folder_path = os.path.join(temp_dir, folder_name)
                os.makedirs(folder_path)
                with open(os.path.join(folder_path, 'test.txt'), 'w') as f:
                    f.write('test content')
            
            # Create a main game file
            with open(os.path.join(temp_dir, 'game.exe'), 'w') as f:
                f.write('game content')
            
            # Update the game's path
            sample_download_request.game.full_disk_path = temp_dir
            db_session.commit()
            
            zip_file_path = os.path.join(app.config['ZIP_SAVE_PATH'], 'test_exclusion.zip')
            
            # Call the function
            zip_game(sample_download_request.id, app, zip_file_path)
            
            # Verify zip file contents
            with zipfile.ZipFile(zip_file_path, 'r') as zipf:
                file_list = zipf.namelist()
                # Should only include the main game file
                assert 'game.exe' in file_list
                # Should not include any excluded folders
                excluded_patterns = ['updates/', 'Updates/', 'UPDATES/', 'extras/', 'Extras/', 'EXTRAS/']
                for pattern in excluded_patterns:
                    assert not any(pattern in name for name in file_list), f"Found {pattern} in {file_list}"
        
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def test_zip_game_nonexistent_source(self, app, db_session, sample_download_request, 
                                       sample_global_settings):
        """Test handling of non-existent source path."""
        # Set a non-existent path
        sample_download_request.game.full_disk_path = '/nonexistent/path'
        db_session.commit()
        
        zip_file_path = os.path.join(app.config['ZIP_SAVE_PATH'], 'test_nonexistent.zip')
        
        # Call the function
        zip_game(sample_download_request.id, app, zip_file_path)
        
        # Refresh the download request from database
        db_session.refresh(sample_download_request)
        
        # Verify download request was marked as failed
        assert sample_download_request.status == 'failed'
        assert 'Error: File Not Found' in sample_download_request.zip_file_path
        assert sample_download_request.completion_time is not None
    
    def test_zip_game_source_is_file(self, app, db_session, sample_download_request, 
                                   sample_global_settings):
        """Test handling when source path is already a file."""
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.exe')
        temp_file.write(b'game executable content')
        temp_file.close()
        
        try:
            # Set the game path to the file
            sample_download_request.game.full_disk_path = temp_file.name
            db_session.commit()
            
            # Call the function (zip_file_path parameter becomes the direct file path)
            zip_game(sample_download_request.id, app, temp_file.name)
            
            # Refresh the download request from database
            db_session.refresh(sample_download_request)
            
            # Verify download request provides direct link
            assert sample_download_request.status == 'available'
            assert sample_download_request.zip_file_path == temp_file.name
            assert sample_download_request.completion_time is not None
            
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
    
    @patch('modules.utils_download.zipfile.ZipFile')
    def test_zip_game_zip_creation_error(self, mock_zipfile, app, db_session, 
                                       sample_download_request, sample_global_settings, 
                                       temp_game_directory):
        """Test error handling during zip creation."""
        # Mock ZipFile to raise an exception
        mock_zipfile.side_effect = Exception('Zip creation failed')
        
        # Update the game's path
        sample_download_request.game.full_disk_path = temp_game_directory
        db_session.commit()
        
        zip_file_path = os.path.join(app.config['ZIP_SAVE_PATH'], 'test_error.zip')
        
        # Call the function
        zip_game(sample_download_request.id, app, zip_file_path)
        
        # Refresh the download request from database
        db_session.refresh(sample_download_request)
        
        # Verify download request was marked as failed
        assert sample_download_request.status == 'failed'
        assert 'Error: Zip creation failed' in sample_download_request.zip_file_path
        assert sample_download_request.completion_time is not None
    
    def test_zip_game_creates_directory(self, app, db_session, sample_download_request, 
                                      sample_global_settings, temp_game_directory):
        """Test that ZIP_SAVE_PATH directory is created if it doesn't exist."""
        # Remove the ZIP_SAVE_PATH directory
        if os.path.exists(app.config['ZIP_SAVE_PATH']):
            shutil.rmtree(app.config['ZIP_SAVE_PATH'])
        
        # Update the game's path
        sample_download_request.game.full_disk_path = temp_game_directory
        db_session.commit()
        
        zip_file_path = os.path.join(app.config['ZIP_SAVE_PATH'], 'test_create_dir.zip')
        
        # Call the function
        zip_game(sample_download_request.id, app, zip_file_path)
        
        # Verify directory was created and zip file exists
        assert os.path.exists(app.config['ZIP_SAVE_PATH'])
        assert os.path.exists(zip_file_path)
    
    def test_zip_game_filename_sanitization(self, app, db_session, sample_download_request, 
                                          sample_global_settings, temp_game_directory):
        """Test that zip file names are properly sanitized."""
        # Update the game's path
        sample_download_request.game.full_disk_path = temp_game_directory
        db_session.commit()
        
        # Use an unsafe filename
        unsafe_name = 'test<>game|with:invalid*chars?.zip'
        zip_file_path = os.path.join(app.config['ZIP_SAVE_PATH'], unsafe_name)
        
        # Call the function
        zip_game(sample_download_request.id, app, zip_file_path)
        
        # Refresh the download request from database
        db_session.refresh(sample_download_request)
        
        # Verify the filename was sanitized
        assert sample_download_request.status == 'available'
        # The actual path should be sanitized (no invalid characters)
        assert '<' not in sample_download_request.zip_file_path
        assert '>' not in sample_download_request.zip_file_path
        assert '|' not in sample_download_request.zip_file_path
        assert ':' not in os.path.basename(sample_download_request.zip_file_path)
        assert '*' not in sample_download_request.zip_file_path
        assert '?' not in sample_download_request.zip_file_path


class TestUpdateDownloadRequest:
    """Test cases for the update_download_request function."""
    
    def test_update_download_request_basic_update(self, db_session, sample_download_request):
        """Test basic status and file path update."""
        original_time = sample_download_request.completion_time
        file_path = '/test/path/game.zip'
        
        # Call the function
        update_download_request(sample_download_request, 'available', file_path)
        
        # Verify updates
        assert sample_download_request.status == 'available'
        assert sample_download_request.zip_file_path == file_path
        assert sample_download_request.completion_time != original_time
        assert sample_download_request.completion_time is not None
    
    def test_update_download_request_with_file_size(self, db_session, sample_download_request):
        """Test update with file size parameter."""
        file_path = '/test/path/game.zip'
        file_size = 1048576  # 1MB
        
        # Call the function
        update_download_request(sample_download_request, 'available', file_path, file_size)
        
        # Verify updates including file size
        assert sample_download_request.status == 'available'
        assert sample_download_request.zip_file_path == file_path
        assert sample_download_request.download_size == file_size
        assert sample_download_request.completion_time is not None
    
    def test_update_download_request_failed_status(self, db_session, sample_download_request):
        """Test updating to failed status with error message."""
        error_message = 'Error: File not found'
        
        # Call the function
        update_download_request(sample_download_request, 'failed', error_message)
        
        # Verify failed status update
        assert sample_download_request.status == 'failed'
        assert sample_download_request.zip_file_path == error_message
        assert sample_download_request.completion_time is not None
    
    def test_update_download_request_processing_status(self, db_session, sample_download_request):
        """Test updating to processing status."""
        file_path = '/test/path/game_processing.zip'
        
        # Call the function
        update_download_request(sample_download_request, 'processing', file_path)
        
        # Verify processing status update
        assert sample_download_request.status == 'processing'
        assert sample_download_request.zip_file_path == file_path
        assert sample_download_request.completion_time is not None


class TestZipFolder:
    """Test cases for the zip_folder function."""
    
    def test_zip_folder_success(self, app, db_session, sample_download_request, temp_game_directory):
        """Test successful zipping of a folder."""
        file_name = 'test_folder_zip'
        
        # Call the function
        zip_folder(sample_download_request.id, app, temp_game_directory, file_name)
        
        # Refresh the download request from database
        db_session.refresh(sample_download_request)
        
        # Verify the zip file was created
        expected_zip_path = os.path.join(app.config['ZIP_SAVE_PATH'], f'{file_name}.zip')
        assert os.path.exists(expected_zip_path)
        
        # Verify download request was updated
        assert sample_download_request.status == 'available'
        assert sample_download_request.zip_file_path == expected_zip_path
        assert sample_download_request.download_size > 0  # Should have file size
        assert sample_download_request.completion_time is not None
        
        # Verify zip file contents
        with zipfile.ZipFile(expected_zip_path, 'r') as zipf:
            file_list = zipf.namelist()
            # Should include all files (no exclusion logic in zip_folder)
            assert len(file_list) > 0
    
    def test_zip_folder_source_is_file(self, app, db_session, sample_download_request):
        """Test handling when source location is a single file."""
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
        temp_file.write(b'test file content')
        temp_file.close()
        
        try:
            file_name = 'test_single_file'
            
            # Call the function
            zip_folder(sample_download_request.id, app, temp_file.name, file_name)
            
            # Refresh the download request from database
            db_session.refresh(sample_download_request)
            
            # Verify download request provides direct link (no zipping for single files)
            assert sample_download_request.status == 'available'
            assert sample_download_request.zip_file_path == temp_file.name
            assert sample_download_request.completion_time is not None
            
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
    
    def test_zip_folder_nonexistent_source(self, app, db_session, sample_download_request):
        """Test handling of non-existent source location."""
        nonexistent_path = '/nonexistent/folder'
        file_name = 'test_nonexistent'
        
        # Call the function
        zip_folder(sample_download_request.id, app, nonexistent_path, file_name)
        
        # Refresh the download request from database
        db_session.refresh(sample_download_request)
        
        # Verify download request was marked as failed
        assert sample_download_request.status == 'failed'
        assert 'Error: File Not Found' in sample_download_request.zip_file_path
        assert sample_download_request.completion_time is not None
    
    def test_zip_folder_creates_directory(self, app, db_session, sample_download_request, temp_game_directory):
        """Test that ZIP_SAVE_PATH directory is created if it doesn't exist."""
        # Remove the ZIP_SAVE_PATH directory
        if os.path.exists(app.config['ZIP_SAVE_PATH']):
            shutil.rmtree(app.config['ZIP_SAVE_PATH'])
        
        file_name = 'test_create_dir_folder'
        
        # Call the function
        zip_folder(sample_download_request.id, app, temp_game_directory, file_name)
        
        # Verify directory was created and zip file exists
        assert os.path.exists(app.config['ZIP_SAVE_PATH'])
        expected_zip_path = os.path.join(app.config['ZIP_SAVE_PATH'], f'{file_name}.zip')
        assert os.path.exists(expected_zip_path)
    
    @patch('modules.utils_download.zipfile.ZipFile')
    def test_zip_folder_zip_creation_error(self, mock_zipfile, app, db_session, 
                                         sample_download_request, temp_game_directory):
        """Test error handling during zip creation."""
        # Mock ZipFile to raise an exception
        mock_zipfile.side_effect = Exception('Folder zip creation failed')
        
        file_name = 'test_folder_error'
        
        # Call the function
        zip_folder(sample_download_request.id, app, temp_game_directory, file_name)
        
        # Refresh the download request from database
        db_session.refresh(sample_download_request)
        
        # Verify download request was marked as failed
        assert sample_download_request.status == 'failed'
        assert 'Error: Folder zip creation failed' in sample_download_request.zip_file_path
        assert sample_download_request.completion_time is not None


class TestGetZipStorageStats:
    """Test cases for the get_zip_storage_stats function."""
    
    def test_get_zip_storage_stats_empty_directory(self, app):
        """Test statistics for empty zip directory."""
        with app.app_context():
            # Ensure directory exists but is empty
            zip_path = app.config['ZIP_SAVE_PATH']
            if not os.path.exists(zip_path):
                os.makedirs(zip_path)
            
            # Clear any existing files
            for file in os.listdir(zip_path):
                os.remove(os.path.join(zip_path, file))
            
            count, size1, size2 = get_zip_storage_stats()
            
            assert count == 0
            assert size1 == 0
            assert size2 == 0
    
    def test_get_zip_storage_stats_nonexistent_directory(self, app):
        """Test statistics when zip directory doesn't exist."""
        with app.app_context():
            # Ensure directory doesn't exist
            zip_path = app.config['ZIP_SAVE_PATH']
            if os.path.exists(zip_path):
                shutil.rmtree(zip_path)
            
            count, size1, size2 = get_zip_storage_stats()
            
            assert count == 0
            assert size1 == 0
            assert size2 == 0
    
    def test_get_zip_storage_stats_with_zip_files(self, app):
        """Test statistics with actual zip files."""
        with app.app_context():
            zip_path = app.config['ZIP_SAVE_PATH']
            if not os.path.exists(zip_path):
                os.makedirs(zip_path)
            
            # Create test zip files with known content
            zip_files = []
            expected_sizes = []
            
            for i in range(3):
                zip_file_path = os.path.join(zip_path, f'test_{i}.zip')
                with zipfile.ZipFile(zip_file_path, 'w') as zipf:
                    test_content = f'Test content for zip {i}' * 10  # Make content different sizes
                    zipf.writestr(f'test_{i}.txt', test_content)
                
                zip_files.append(zip_file_path)
                expected_sizes.append(os.path.getsize(zip_file_path))
            
            try:
                count, size1, size2 = get_zip_storage_stats()
                
                assert count == 3
                assert size1 == sum(expected_sizes)
                assert size2 == sum(expected_sizes)  # Both size values should be the same
                assert size1 > 0  # Should have actual size
                
            finally:
                # Cleanup
                for zip_file in zip_files:
                    if os.path.exists(zip_file):
                        os.remove(zip_file)
    
    def test_get_zip_storage_stats_filters_non_zip_files(self, app):
        """Test that non-zip files are properly filtered out."""
        with app.app_context():
            zip_path = app.config['ZIP_SAVE_PATH']
            if not os.path.exists(zip_path):
                os.makedirs(zip_path)
            
            # Create one zip file and several non-zip files
            zip_file_path = os.path.join(zip_path, 'test.zip')
            with zipfile.ZipFile(zip_file_path, 'w') as zipf:
                zipf.writestr('test.txt', 'Test content')
            
            non_zip_files = []
            for ext in ['.txt', '.exe', '.dat', '.log']:
                file_path = os.path.join(zip_path, f'test{ext}')
                with open(file_path, 'w') as f:
                    f.write('Non-zip content')
                non_zip_files.append(file_path)
            
            try:
                count, size1, size2 = get_zip_storage_stats()
                
                # Should only count the one zip file
                assert count == 1
                assert size1 == os.path.getsize(zip_file_path)
                assert size2 == os.path.getsize(zip_file_path)
                
            finally:
                # Cleanup
                if os.path.exists(zip_file_path):
                    os.remove(zip_file_path)
                for non_zip_file in non_zip_files:
                    if os.path.exists(non_zip_file):
                        os.remove(non_zip_file)
    
    def test_get_zip_storage_stats_case_insensitive_zip_detection(self, app):
        """Test that .ZIP files are detected (case insensitive)."""
        with app.app_context():
            zip_path = app.config['ZIP_SAVE_PATH']
            if not os.path.exists(zip_path):
                os.makedirs(zip_path)
            
            # Create zip files with different case extensions
            zip_extensions = ['.zip', '.ZIP', '.Zip', '.zIp']
            zip_files = []
            
            for i, ext in enumerate(zip_extensions):
                zip_file_path = os.path.join(zip_path, f'test_{i}{ext}')
                with zipfile.ZipFile(zip_file_path, 'w') as zipf:
                    zipf.writestr(f'test_{i}.txt', f'Test content {i}')
                zip_files.append(zip_file_path)
            
            try:
                count, size1, size2 = get_zip_storage_stats()
                
                # Should count all zip files regardless of case
                assert count == len(zip_extensions)
                total_expected_size = sum(os.path.getsize(zf) for zf in zip_files)
                assert size1 == total_expected_size
                assert size2 == total_expected_size
                
            finally:
                # Cleanup
                for zip_file in zip_files:
                    if os.path.exists(zip_file):
                        os.remove(zip_file)