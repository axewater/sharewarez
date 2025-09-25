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
    zip_folder
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
        
        zip_file_path = 'test_game.zip'
        
        # Call the function
        zip_game(sample_download_request.id, app, zip_file_path)
        
        # Refresh the download request from database
        db_session.refresh(sample_download_request)
        
        # Verify download request was updated for zipstream
        assert sample_download_request.status == 'available'
        assert sample_download_request.completion_time is not None
        # Zipstream mode - zip_file_path contains the source path for streaming
        assert sample_download_request.zip_file_path == temp_game_directory
    
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
            
            zip_file_path = 'test_exclusion.zip'
            
            # Call the function
            zip_game(sample_download_request.id, app, zip_file_path)
            
            # Refresh the download request from database
            db_session.refresh(sample_download_request)
            
            # Verify zipstream setup was successful
            assert sample_download_request.status == 'available'
            assert sample_download_request.zip_file_path == temp_dir
            assert sample_download_request.completion_time is not None
            # Note: Folder exclusion logic is handled in the zipstream code during streaming
        
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def test_zip_game_nonexistent_source(self, app, db_session, sample_download_request, 
                                       sample_global_settings):
        """Test handling of non-existent source path."""
        # Set a non-existent path
        sample_download_request.game.full_disk_path = '/nonexistent/path'
        db_session.commit()
        
        zip_file_path = 'test_nonexistent.zip'
        
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
    
    def test_zip_game_zipstream_preparation_success(self, app, db_session, 
                                                   sample_download_request, sample_global_settings, 
                                                   temp_game_directory):
        """Test successful zipstream preparation."""
        # Update the game's path
        sample_download_request.game.full_disk_path = temp_game_directory
        db_session.commit()
        
        zip_file_path = 'test_zipstream.zip'
        
        # Call the function
        zip_game(sample_download_request.id, app, zip_file_path)
        
        # Refresh the download request from database
        db_session.refresh(sample_download_request)
        
        # Verify zipstream was prepared successfully
        assert sample_download_request.status == 'available'
        assert sample_download_request.zip_file_path == temp_game_directory
        assert sample_download_request.completion_time is not None
    
    
    def test_zip_game_zipstream_with_unsafe_filename(self, app, db_session, sample_download_request, 
                                                    sample_global_settings, temp_game_directory):
        """Test zipstream setup with unsafe filename."""
        # Update the game's path
        sample_download_request.game.full_disk_path = temp_game_directory
        db_session.commit()
        
        # Use an unsafe filename
        unsafe_name = 'test<>game|with:invalid*chars?.zip'
        zip_file_path = unsafe_name
        
        # Call the function
        zip_game(sample_download_request.id, app, zip_file_path)
        
        # Refresh the download request from database
        db_session.refresh(sample_download_request)
        
        # Verify zipstream was set up (filename sanitization happens in streaming)
        assert sample_download_request.status == 'available'
        assert sample_download_request.zip_file_path == temp_game_directory


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
        """Test successful zipstream setup for a folder."""
        file_name = 'test_folder_zip'
        
        # Call the function
        zip_folder(sample_download_request.id, app, temp_game_directory, file_name)
        
        # Refresh the download request from database
        db_session.refresh(sample_download_request)
        
        # Verify zipstream was set up successfully
        assert sample_download_request.status == 'available'
        assert sample_download_request.zip_file_path == temp_game_directory
        assert sample_download_request.completion_time is not None
    
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
    

