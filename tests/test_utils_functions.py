import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open, Mock
from PIL import Image as PILImage
import requests
from wtforms.validators import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from modules.utils_functions import (
    format_size, square_image, get_folder_size_in_bytes, 
    get_folder_size_in_bytes_updates, read_first_nfo_content,
    download_image, comma_separated_urls, website_category_to_string,
    load_release_group_patterns, get_library_count, get_games_count,
    delete_associations_for_game, PLATFORM_IDS
)


class TestFormatSize:
    """Test the format_size function."""
    
    @pytest.mark.parametrize("size_bytes, expected", [
        (0, "0.00 KB"),
        (512, "0.50 KB"),
        (1024, "1.00 KB"),
        (1536, "1.50 KB"),
        (1048576, "1.00 MB"),
        (1073741824, "1.00 GB"),
        (1099511627776, "1.00 TB"),
        (None, "0 MB"),
        (2048, "2.00 KB"),
        (5242880, "5.00 MB")
    ])
    def test_format_size_various_inputs(self, size_bytes, expected):
        """Test format_size with various byte inputs."""
        assert format_size(size_bytes) == expected
    
    def test_format_size_exception_handling(self):
        """Test format_size handles exceptions gracefully."""
        # Test with invalid input that might cause an exception
        result = format_size("invalid")
        assert result == "0 MB"


class TestSquareImage:
    """Test the square_image function."""
    
    def test_square_image_already_square(self):
        """Test square_image with an already square image."""
        # Create a test image
        img = PILImage.new('RGB', (100, 100), color='red')
        result = square_image(img, 100)
        
        assert result.size == (100, 100)
    
    def test_square_image_rectangular(self):
        """Test square_image with a rectangular image."""
        # Create a rectangular image
        img = PILImage.new('RGB', (200, 100), color='blue')
        result = square_image(img, 150)
        
        assert result.size == (150, 150)
    
    def test_square_image_downsize(self):
        """Test square_image with downsizing."""
        img = PILImage.new('RGB', (300, 300), color='green')
        result = square_image(img, 100)
        
        assert result.size == (100, 100)


class TestGetFolderSizeInBytes:
    """Test the get_folder_size_in_bytes function."""
    
    @patch('os.path.exists')
    def test_get_folder_size_nonexistent_path(self, mock_exists):
        """Test get_folder_size_in_bytes with non-existent path."""
        mock_exists.return_value = False
        
        result = get_folder_size_in_bytes("/nonexistent/path")
        assert result == 0
    
    @patch('os.path.getsize')
    @patch('os.path.isfile')
    @patch('os.path.exists')
    def test_get_folder_size_single_file(self, mock_exists, mock_isfile, mock_getsize):
        """Test get_folder_size_in_bytes with a single file."""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_getsize.return_value = 1024
        
        result = get_folder_size_in_bytes("/path/to/file.txt")
        assert result == 1024
    
    @patch('os.access')
    @patch('os.path.isfile')
    @patch('os.path.exists')
    def test_get_folder_size_no_read_permission(self, mock_exists, mock_isfile, mock_access):
        """Test get_folder_size_in_bytes with no read permission."""
        mock_exists.return_value = True
        mock_isfile.return_value = False
        mock_access.return_value = False
        
        result = get_folder_size_in_bytes("/restricted/path")
        assert result == 0
    
    @patch('os.path.getsize')
    @patch('os.path.exists')
    @patch('os.path.islink')
    @patch('os.walk')
    @patch('os.access')
    @patch('os.path.isfile')
    def test_get_folder_size_directory_with_files(self, mock_isfile, mock_access, mock_walk, 
                                                 mock_islink, mock_exists, mock_getsize):
        """Test get_folder_size_in_bytes with a directory containing files."""
        mock_isfile.return_value = False
        mock_access.return_value = True
        mock_walk.return_value = [
            ('/test', ['subdir'], ['file1.txt', 'file2.txt']),
            ('/test/subdir', [], ['file3.txt'])
        ]
        mock_islink.return_value = False
        mock_exists.return_value = True
        mock_getsize.side_effect = [100, 200, 300]  # File sizes
        
        result = get_folder_size_in_bytes("/test")
        assert result == 600


class TestGetFolderSizeInBytesUpdates:
    """Test the get_folder_size_in_bytes_updates function."""
    
    @patch('modules.utils_functions.GlobalSettings')
    @patch('os.path.getsize')
    @patch('os.path.isfile')
    @patch('os.path.exists')
    def test_get_folder_size_updates_single_file(self, mock_exists, mock_isfile, 
                                                mock_getsize, mock_settings):
        """Test get_folder_size_in_bytes_updates with a single file."""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_getsize.return_value = 2048
        
        result = get_folder_size_in_bytes_updates("/path/to/file.zip")
        assert result == 2048
    
    @patch('modules.utils_functions.GlobalSettings')
    @patch('os.path.exists')
    def test_get_folder_size_updates_nonexistent(self, mock_exists, mock_settings):
        """Test get_folder_size_in_bytes_updates with non-existent path."""
        mock_exists.return_value = False
        
        result = get_folder_size_in_bytes_updates("/nonexistent")
        assert result == 0


class TestReadFirstNfoContent:
    """Test the read_first_nfo_content function."""
    
    @patch('os.path.isfile')
    def test_read_nfo_file_path(self, mock_isfile):
        """Test read_first_nfo_content with a file path."""
        mock_isfile.return_value = True
        
        result = read_first_nfo_content("/path/to/file.txt")
        assert result is None
    
    @patch('builtins.open', mock_open(read_data='Test NFO Content\x00with null'))
    @patch('os.listdir')
    @patch('os.path.isfile')
    def test_read_nfo_success(self, mock_isfile, mock_listdir):
        """Test successful NFO file reading."""
        mock_isfile.return_value = False
        mock_listdir.return_value = ['game.nfo', 'other.txt']
        
        result = read_first_nfo_content("/test/path")
        assert result == "Test NFO Contentwith null"
    
    @patch('os.listdir')
    @patch('os.path.isfile')
    def test_read_nfo_no_nfo_files(self, mock_isfile, mock_listdir):
        """Test read_first_nfo_content with no NFO files."""
        mock_isfile.return_value = False
        mock_listdir.return_value = ['file1.txt', 'file2.zip']
        
        result = read_first_nfo_content("/test/path")
        assert result is None
    
    @patch('os.listdir')
    @patch('os.path.isfile')
    def test_read_nfo_directory_error(self, mock_isfile, mock_listdir):
        """Test read_first_nfo_content with directory access error."""
        mock_isfile.return_value = False
        mock_listdir.side_effect = OSError("Permission denied")
        
        result = read_first_nfo_content("/restricted/path")
        assert result is None


class TestDownloadImage:
    """Test the download_image function."""
    
    @patch('requests.get')
    def test_download_image_success(self, mock_get):
        """Test successful image download."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake image data'
        mock_get.return_value = mock_response
        
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('os.path.exists', return_value=True):
                with patch('os.access', return_value=True):
                    download_image('https://example.com/image.jpg', '/save/path/image.jpg')
                    
                    mock_file.assert_called_once_with('/save/path/image.jpg', 'wb')
                    mock_file().write.assert_called_once_with(b'fake image data')
    
    @patch('requests.get')
    def test_download_image_http_prefix(self, mock_get):
        """Test download_image adds https prefix when missing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake image data'
        mock_get.return_value = mock_response
        
        with patch('builtins.open', mock_open()):
            with patch('os.path.exists', return_value=True):
                with patch('os.access', return_value=True):
                    download_image('//example.com/image.jpg', '/save/path/image.jpg')
                    
                    mock_get.assert_called_once_with('https://example.com/image.jpg')
    
    @patch('requests.get')
    def test_download_image_url_transform(self, mock_get):
        """Test download_image transforms thumbnail URLs to original."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake image data'
        mock_get.return_value = mock_response
        
        with patch('builtins.open', mock_open()):
            with patch('os.path.exists', return_value=True):
                with patch('os.access', return_value=True):
                    download_image('https://example.com/t_thumb/image.jpg', '/save/path/image.jpg')
                    
                    mock_get.assert_called_once_with('https://example.com/t_original/image.jpg')
    
    @patch('requests.get')
    def test_download_image_failed_status(self, mock_get):
        """Test download_image with failed HTTP status."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        # Should not raise exception, just print error message
        download_image('https://example.com/notfound.jpg', '/save/path/image.jpg')
        
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_download_image_request_exception(self, mock_get):
        """Test download_image with request exception."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        
        # Should not raise exception, just print error message
        download_image('https://example.com/image.jpg', '/save/path/image.jpg')
        
        mock_get.assert_called_once()
    
    @patch('requests.get')
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_download_image_create_directory(self, mock_exists, mock_makedirs, mock_get):
        """Test download_image creates directory if it doesn't exist."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake image data'
        mock_get.return_value = mock_response
        mock_exists.side_effect = [False, True]  # Directory doesn't exist, then exists after creation
        
        with patch('builtins.open', mock_open()):
            with patch('os.access', return_value=True):
                download_image('https://example.com/image.jpg', '/new/path/image.jpg')
                
                mock_makedirs.assert_called_once_with('/new/path', exist_ok=True)


class TestCommaSeparatedUrls:
    """Test the comma_separated_urls validator function."""
    
    def test_comma_separated_urls_valid(self):
        """Test comma_separated_urls with valid YouTube embed URLs."""
        mock_field = Mock()
        mock_field.data = "https://www.youtube.com/embed/abc123,https://youtube.com/embed/def456"
        
        # Should not raise ValidationError
        comma_separated_urls(None, mock_field)
    
    def test_comma_separated_urls_invalid(self):
        """Test comma_separated_urls with invalid URLs."""
        mock_field = Mock()
        mock_field.data = "https://www.youtube.com/watch?v=abc123,invalid-url"
        
        with pytest.raises(ValidationError):
            comma_separated_urls(None, mock_field)
    
    def test_comma_separated_urls_single_valid(self):
        """Test comma_separated_urls with single valid URL."""
        mock_field = Mock()
        mock_field.data = "https://www.youtube.com/embed/xyz789"
        
        # Should not raise ValidationError
        comma_separated_urls(None, mock_field)


class TestWebsiteCategoryToString:
    """Test the website_category_to_string function."""
    
    @pytest.mark.parametrize("category_id, expected", [
        (1, "official"),
        (2, "wikia"),
        (13, "steam"),
        (17, "gog"),
        (18, "discord"),
        (999, "unknown"),  # Test unknown category
        (0, "unknown")     # Test edge case
    ])
    def test_website_category_mapping(self, category_id, expected):
        """Test website_category_to_string with various category IDs."""
        assert website_category_to_string(category_id) == expected


class TestPlatformIds:
    """Test the PLATFORM_IDS constant."""
    
    def test_platform_ids_structure(self):
        """Test PLATFORM_IDS contains expected platforms."""
        assert "PCWIN" in PLATFORM_IDS
        assert "PS5" in PLATFORM_IDS
        assert "XBOX" in PLATFORM_IDS
        assert PLATFORM_IDS["PCWIN"] == 6
        assert PLATFORM_IDS["PS5"] == 167


class TestLoadReleaseGroupPatterns:
    """Test the load_release_group_patterns function."""
    
    @patch('modules.utils_functions.ReleaseGroup')
    def test_load_release_group_patterns_success(self, mock_release_group):
        """Test successful loading of release group patterns."""
        # Mock release groups
        mock_rg1 = Mock()
        mock_rg1.rlsgroup = "CODEX"
        mock_rg1.rlsgroupcs = "yes"
        
        mock_rg2 = Mock()
        mock_rg2.rlsgroup = "SKIDROW"
        mock_rg2.rlsgroupcs = "no"
        
        mock_release_group.query.filter.return_value.all.return_value = [mock_rg1, mock_rg2]
        
        insensitive, sensitive = load_release_group_patterns()
        
        assert "-CODEX" in insensitive
        assert ".CODEX" in insensitive
        assert "-SKIDROW" in insensitive
        assert ".SKIDROW" in insensitive
        assert len(sensitive) > 0
    
    @patch('modules.utils_functions.ReleaseGroup')
    def test_load_release_group_patterns_sql_error(self, mock_release_group):
        """Test load_release_group_patterns with SQL error."""
        mock_release_group.query.filter.side_effect = SQLAlchemyError("Database error")
        
        insensitive, sensitive = load_release_group_patterns()
        
        assert insensitive == []
        assert sensitive == []


class TestGetLibraryCount:
    """Test the get_library_count function."""
    
    @patch('modules.utils_functions.url_for')
    @patch('modules.utils_functions.Library')
    def test_get_library_count_success(self, mock_library, mock_url_for):
        """Test successful library count retrieval."""
        mock_lib1 = Mock()
        mock_lib1.uuid = "uuid1"
        mock_lib1.name = "Library 1"
        mock_lib1.image_url = "http://example.com/image1.jpg"
        
        mock_lib2 = Mock()
        mock_lib2.uuid = "uuid2"
        mock_lib2.name = "Library 2"
        mock_lib2.image_url = None
        
        mock_library.query.all.return_value = [mock_lib1, mock_lib2]
        mock_url_for.return_value = "/static/default.jpg"
        
        result = get_library_count()
        assert result == 2


class TestGetGamesCount:
    """Test the get_games_count function."""
    
    @patch('modules.utils_functions.Game')
    def test_get_games_count_success(self, mock_game):
        """Test successful games count retrieval."""
        mock_game1 = Mock()
        mock_game1.uuid = "uuid1"
        mock_game1.name = "Game 1"
        
        mock_game2 = Mock()
        mock_game2.uuid = "uuid2"
        mock_game2.name = "Game 2"
        
        mock_game.query.all.return_value = [mock_game1, mock_game2]
        
        result = get_games_count()
        assert result == 2


class TestDeleteAssociationsForGame:
    """Test the delete_associations_for_game function."""
    
    def test_delete_associations_for_game(self):
        """Test deleting associations for a game."""
        mock_game = Mock()
        mock_game.genres = Mock()
        mock_game.platforms = Mock()
        mock_game.game_modes = Mock()
        mock_game.themes = Mock()
        mock_game.player_perspectives = Mock()
        mock_game.multiplayer_modes = Mock()
        
        delete_associations_for_game(mock_game)
        
        # Verify all associations were cleared
        mock_game.genres.clear.assert_called_once()
        mock_game.platforms.clear.assert_called_once()
        mock_game.game_modes.clear.assert_called_once()
        mock_game.themes.clear.assert_called_once()
        mock_game.player_perspectives.clear.assert_called_once()
        mock_game.multiplayer_modes.clear.assert_called_once()


class TestGetFolderSizeErrorHandling:
    """Test error handling in folder size calculation functions."""
    
    @patch('modules.utils_functions.os.walk')
    @patch('modules.utils_functions.os.path.exists')
    def test_get_folder_size_with_permission_error(self, mock_exists, mock_walk):
        """Test folder size calculation with permission error."""
        mock_exists.return_value = True
        mock_walk.side_effect = PermissionError("Permission denied")
        
        # Should not raise exception, return 0 for errors
        result = get_folder_size_in_bytes("/restricted/path")
        assert result == 0
    
    @patch('modules.utils_functions.os.path.exists')
    def test_get_folder_size_nonexistent_path(self, mock_exists):
        """Test folder size calculation with nonexistent path."""
        mock_exists.return_value = False
        
        result = get_folder_size_in_bytes("/nonexistent/path")
        assert result == 0
    
    @patch('modules.utils_functions.os.walk')
    @patch('modules.utils_functions.os.path.exists')
    @patch('modules.utils_functions.os.access')
    def test_get_folder_size_with_inaccessible_subdirs(self, mock_access, mock_exists, mock_walk):
        """Test folder size calculation with inaccessible subdirectories."""
        mock_exists.return_value = True
        mock_access.side_effect = lambda path, mode: '/restricted' not in path
        
        # Mock os.walk to return some directories, including restricted ones
        mock_walk.return_value = [
            ('/test', ['subdir'], ['file1.txt']),
            ('/test/restricted', [], ['file2.txt']),
            ('/test/subdir', [], ['file3.txt'])
        ]
        
        with patch('modules.utils_functions.os.path.getsize', return_value=100):
            with patch('modules.utils_functions.os.path.islink', return_value=False):
                with patch('modules.utils_functions.os.path.join', side_effect=lambda a, b: f"{a}/{b}"):
                    result = get_folder_size_in_bytes("/test")
                    # Should skip restricted directories but process accessible ones
                    assert result > 0


class TestGetFolderSizeUpdatesErrorHandling:
    """Test error handling in get_folder_size_in_bytes_updates function."""
    
    @patch('modules.utils_functions.GlobalSettings')
    @patch('modules.utils_functions.os.path.exists')
    @patch('modules.utils_functions.os.access')
    def test_get_folder_size_updates_no_permissions(self, mock_access, mock_exists, mock_settings):
        """Test folder size calculation with no read permissions."""
        mock_exists.return_value = True
        mock_access.return_value = False
        mock_settings.query.first.return_value = None
        
        result = get_folder_size_in_bytes_updates("/restricted/path")
        assert result == 0
    
    @patch('modules.utils_functions.GlobalSettings')
    @patch('modules.utils_functions.os.walk')
    @patch('modules.utils_functions.os.path.exists')
    @patch('modules.utils_functions.os.access')
    def test_get_folder_size_updates_with_exclusions(self, mock_access, mock_exists, mock_walk, mock_settings):
        """Test folder size calculation with update/extras exclusions."""
        mock_exists.return_value = True
        mock_access.return_value = True
        
        mock_settings_instance = Mock()
        mock_settings_instance.update_folder_name = "Updates"
        mock_settings_instance.extras_folder_name = "Extras"
        mock_settings.query.first.return_value = mock_settings_instance
        
        # Mock directory structure with updates/extras folders
        mock_walk.return_value = [
            ('/game', ['Updates', 'Extras'], ['game.exe']),
            ('/game/Updates', [], ['update1.patch']),
            ('/game/Extras', [], ['soundtrack.mp3'])
        ]
        
        with patch('modules.utils_functions.os.path.getsize', return_value=100):
            with patch('modules.utils_functions.os.path.islink', return_value=False):
                with patch('modules.utils_functions.os.path.join', side_effect=lambda a, b: f"{a}/{b}"):
                    result = get_folder_size_in_bytes_updates("/game")
                    # Should exclude Updates and Extras folders
                    assert result == max(100, 1)  # Only game.exe counted


class TestReadFirstNfoContentErrorHandling:
    """Test error handling in read_first_nfo_content function."""
    
    @patch('modules.utils_functions.os.path.isfile')
    def test_read_first_nfo_content_file_path(self, mock_isfile):
        """Test NFO reading when path is a file."""
        mock_isfile.return_value = True
        
        result = read_first_nfo_content("/path/to/file.exe")
        assert result is None
    
    @patch('modules.utils_functions.os.walk')
    @patch('modules.utils_functions.os.path.isfile')
    def test_read_first_nfo_content_no_nfo_files(self, mock_isfile, mock_walk):
        """Test NFO reading when no NFO files exist."""
        mock_isfile.return_value = False
        mock_walk.return_value = [
            ('/game', [], ['game.exe', 'readme.txt'])
        ]
        
        result = read_first_nfo_content("/game")
        assert result is None
    
    @patch('modules.utils_functions.os.walk')
    @patch('modules.utils_functions.os.path.isfile')
    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    def test_read_first_nfo_content_permission_error(self, mock_open, mock_isfile, mock_walk):
        """Test NFO reading with permission error."""
        mock_isfile.return_value = False
        mock_walk.return_value = [
            ('/game', [], ['game.nfo'])
        ]
        
        result = read_first_nfo_content("/game")
        assert result is None


class TestDownloadImageErrorHandling:
    """Test error handling in download_image function."""
    
    @patch('modules.utils_functions.requests.get')
    def test_download_image_http_error(self, mock_get):
        """Test image download with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Not Found")
        mock_get.return_value = mock_response
        
        result = download_image("http://example.com/notfound.jpg", "/tmp/test.jpg")
        assert result is None
    
    @patch('modules.utils_functions.requests.get')
    def test_download_image_connection_error(self, mock_get):
        """Test image download with connection error."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")
        
        result = download_image("http://example.com/image.jpg", "/tmp/test.jpg")
        assert result is None
    
    @patch('modules.utils_functions.requests.get')
    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    def test_download_image_file_write_error(self, mock_open, mock_get):
        """Test image download with file write error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"fake image data"
        mock_get.return_value = mock_response
        
        result = download_image("http://example.com/image.jpg", "/restricted/test.jpg")
        assert result is None


class TestFormatSizeEdgeCases:
    """Test edge cases in format_size function."""
    
    def test_format_size_zero(self):
        """Test formatting zero size."""
        result = format_size(0)
        assert "0" in result
    
    def test_format_size_negative(self):
        """Test formatting negative size."""
        result = format_size(-100)
        assert "-" in result
    
    def test_format_size_very_large(self):
        """Test formatting very large sizes."""
        # Test TB range
        result = format_size(1024**4)  # 1 TB
        assert "TB" in result
        
        # Test PB range  
        result = format_size(1024**5)  # 1 PB
        assert "PB" in result