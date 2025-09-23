import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open, call
from PIL import Image as PILImage
import requests
import requests.exceptions
from wtforms.validators import ValidationError

from modules import create_app, db
from modules.models import ReleaseGroup, Library, Game, GlobalSettings, User
from modules.utils_functions import (
    format_size, square_image, get_folder_size_in_bytes, get_folder_size_in_bytes_updates,
    read_first_nfo_content, download_image, comma_separated_urls, website_category_to_string,
    PLATFORM_IDS, load_scanning_filter_patterns, get_library_count, get_games_count,
    delete_associations_for_game, sanitize_string_input, validate_discord_webhook_url,
    validate_discord_bot_name, validate_discord_avatar_url
)


def safe_cleanup_database(db_session):
    """Safely clean up database records respecting foreign key constraints.""" 
    from sqlalchemy import delete
    
    # Clean up in order to respect foreign key constraints
    db_session.execute(delete(User))
    db_session.execute(delete(Game))
    db_session.execute(delete(Library))
    db_session.execute(delete(ReleaseGroup))
    db_session.execute(delete(GlobalSettings))
    db_session.commit()




@pytest.fixture
def sample_libraries(db_session):
    """Create sample libraries for testing."""
    libraries = []
    for i in range(3):
        library = Library(
            uuid=f'test-lib-{i}',
            name=f'Test Library {i}',
            image_url=f'https://example.com/lib{i}.jpg' if i % 2 else None
        )
        db_session.add(library)
        libraries.append(library)
    db_session.commit()
    return libraries


@pytest.fixture
def sample_games(db_session):
    """Create sample games for testing."""
    games = []
    for i in range(5):
        game = Game(
            uuid=f'test-game-{i}',
            name=f'Test Game {i}'
        )
        db_session.add(game)
        games.append(game)
    db_session.commit()
    return games


@pytest.fixture
def sample_release_groups(db_session):
    """Create sample scanning filters for testing."""
    release_groups = []
    
    # Case insensitive scanning filters
    rg1 = ReleaseGroup(filter_pattern='TEST_GROUP_1')
    rg2 = ReleaseGroup(filter_pattern='TEST_GROUP_2')

    # Case sensitive scanning filters
    rg3 = ReleaseGroup(filter_pattern='TEST_GROUP_3', case_sensitive='yes')
    rg4 = ReleaseGroup(filter_pattern='TEST_GROUP_4', case_sensitive='no')
    
    for rg in [rg1, rg2, rg3, rg4]:
        db_session.add(rg)
        release_groups.append(rg)
    
    db_session.commit()
    return release_groups


@pytest.fixture
def sample_global_settings(db_session):
    """Create sample global settings for testing."""
    settings = GlobalSettings(
        update_folder_name='Updates',
        extras_folder_name='Extras'
    )
    db_session.add(settings)
    db_session.commit()
    return settings


class TestFormatSize:
    """Test cases for format_size function."""
    
    def test_format_size_none_input(self):
        """Test format_size with None input."""
        result = format_size(None)
        assert result == '0 MB'
    
    def test_format_size_zero_bytes(self):
        """Test format_size with 0 bytes."""
        result = format_size(0)
        assert result == '0.00 KB'
    
    def test_format_size_kilobytes(self):
        """Test format_size for kilobyte range."""
        result = format_size(1024)  # 1 KB
        assert result == '1.00 KB'
        
        result = format_size(512)  # 0.5 KB
        assert result == '0.50 KB'
    
    def test_format_size_megabytes(self):
        """Test format_size for megabyte range."""
        result = format_size(1024 * 1024)  # 1 MB
        assert result == '1.00 MB'
        
        result = format_size(1536 * 1024)  # 1.5 MB
        assert result == '1.50 MB'
    
    def test_format_size_gigabytes(self):
        """Test format_size for gigabyte range."""
        result = format_size(1024 * 1024 * 1024)  # 1 GB
        assert result == '1.00 GB'
    
    def test_format_size_terabytes(self):
        """Test format_size for terabyte range."""
        result = format_size(1024 * 1024 * 1024 * 1024)  # 1 TB
        assert result == '1.00 TB'
    
    def test_format_size_very_large(self):
        """Test format_size for very large sizes."""
        result = format_size(1024**6)  # 1 EB (exabyte)
        assert result == '1.00 EB'
    
    def test_format_size_exception_handling(self):
        """Test format_size with invalid input that causes exception."""
        # Test with string input that can't be divided
        with patch('builtins.print') as mock_print:
            result = format_size('invalid')
            assert result == '0 MB'
            mock_print.assert_called_once()


class TestSquareImage:
    """Test cases for square_image function."""
    
    @patch('modules.utils_functions.PILImage')
    def test_square_image_already_square(self, mock_pil):
        """Test square_image when image is already square."""
        # Mock image that's already the target size
        mock_image = MagicMock()
        mock_image.size = [100, 100]
        
        result = square_image(mock_image, 100)
        
        mock_image.thumbnail.assert_called_once_with((100, 100))
        assert result == mock_image
    
    @patch('modules.utils_functions.PILImage')
    def test_square_image_needs_padding(self, mock_pil):
        """Test square_image when image needs padding."""
        # Mock image that needs padding
        mock_image = MagicMock()
        mock_image.size = [50, 80]  # Not square, smaller than target
        
        mock_new_image = MagicMock()
        mock_pil.new.return_value = mock_new_image
        
        result = square_image(mock_image, 100)
        
        mock_image.thumbnail.assert_called_once_with((100, 100))
        mock_pil.new.assert_called_once_with('RGB', (100, 100), color='black')
        mock_new_image.paste.assert_called_once()
        assert result == mock_new_image
    
    @patch('modules.utils_functions.PILImage')
    def test_square_image_different_aspect_ratio(self, mock_pil):
        """Test square_image with different aspect ratios."""
        mock_image = MagicMock()
        mock_image.size = [200, 100]  # Wide image
        
        mock_new_image = MagicMock()
        mock_pil.new.return_value = mock_new_image
        
        result = square_image(mock_image, 150)
        
        mock_image.thumbnail.assert_called_once_with((150, 150))
        mock_pil.new.assert_called_once_with('RGB', (150, 150), color='black')


class TestGetFolderSizeInBytes:
    """Test cases for get_folder_size_in_bytes function."""
    
    def test_get_folder_size_nonexistent_path(self):
        """Test get_folder_size_in_bytes with non-existent path."""
        with patch('builtins.print') as mock_print:
            result = get_folder_size_in_bytes('/nonexistent/path')
            assert result == 0
            mock_print.assert_called()
    
    @patch('os.path.isfile')
    @patch('os.path.getsize')
    @patch('os.path.exists')
    def test_get_folder_size_single_file(self, mock_exists, mock_getsize, mock_isfile):
        """Test get_folder_size_in_bytes with single file."""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_getsize.return_value = 1024
        
        result = get_folder_size_in_bytes('/path/to/file.txt')
        assert result == 1024
    
    @patch('os.access')
    @patch('os.path.exists')
    def test_get_folder_size_no_read_permission(self, mock_exists, mock_access):
        """Test get_folder_size_in_bytes with no read permission."""
        mock_exists.return_value = True
        mock_access.return_value = False
        
        with patch('builtins.print') as mock_print:
            result = get_folder_size_in_bytes('/path/no/permission')
            assert result == 0
            mock_print.assert_called()
    
    @patch('os.walk')
    @patch('os.path.getsize')
    @patch('os.path.exists')
    @patch('os.path.isfile')
    @patch('os.access')
    @patch('os.path.islink')
    def test_get_folder_size_normal_folder(self, mock_islink, mock_access, mock_isfile, 
                                           mock_exists, mock_getsize, mock_walk):
        """Test get_folder_size_in_bytes with normal folder structure."""
        mock_exists.return_value = True
        mock_isfile.return_value = False
        mock_access.return_value = True
        mock_islink.return_value = False
        mock_getsize.return_value = 512
        
        # Mock os.walk to return test directory structure
        mock_walk.return_value = [
            ('/test', ['subdir'], ['file1.txt', 'file2.txt']),
            ('/test/subdir', [], ['file3.txt'])
        ]
        
        result = get_folder_size_in_bytes('/test')
        assert result == 512 * 3  # 3 files, 512 bytes each
    
    @patch('os.walk')
    @patch('os.path.exists')
    @patch('os.path.isfile')
    @patch('os.access')
    def test_get_folder_size_with_symlinks(self, mock_access, mock_isfile, mock_exists, mock_walk):
        """Test get_folder_size_in_bytes skips symlinks."""
        mock_exists.return_value = True
        mock_isfile.return_value = False
        mock_access.return_value = True
        
        mock_walk.return_value = [
            ('/test', [], ['file1.txt', 'symlink'])
        ]
        
        def mock_islink_side_effect(path):
            return 'symlink' in path
        
        with patch('os.path.islink', side_effect=mock_islink_side_effect):
            with patch('os.path.getsize', return_value=512) as mock_getsize:
                result = get_folder_size_in_bytes('/test')
                # Should only count file1.txt, not the symlink
                assert mock_getsize.call_count == 1


class TestGetFolderSizeInBytesUpdates:
    """Test cases for get_folder_size_in_bytes_updates function."""
    
    def test_get_folder_size_updates_single_file(self, db_session):
        """Test get_folder_size_in_bytes_updates with single file."""
        with patch('os.path.isfile', return_value=True):
            with patch('os.path.getsize', return_value=2048):
                result = get_folder_size_in_bytes_updates('/path/to/file.txt')
                assert result == 2048
    
    def test_get_folder_size_updates_nonexistent_path(self, db_session):
        """Test get_folder_size_in_bytes_updates with non-existent path."""
        with patch('os.path.exists', return_value=False):
            with patch('builtins.print') as mock_print:
                result = get_folder_size_in_bytes_updates('/nonexistent/path')
                assert result == 0
                mock_print.assert_called()
    
    def test_get_folder_size_updates_with_exclusions(self, db_session, sample_global_settings):
        """Test get_folder_size_in_bytes_updates excludes update/extra folders."""
        mock_walk_data = [
            ('/test', ['Updates', 'Extras', 'normal'], []),
            ('/test/Updates', [], ['update.exe']),
            ('/test/Extras', [], ['bonus.txt']),
            ('/test/normal', [], ['game.exe'])
        ]
        
        with patch('os.path.isfile', return_value=False):
            with patch('os.path.exists', return_value=True):
                with patch('os.access', return_value=True):
                    with patch('os.walk', return_value=mock_walk_data):
                        with patch('os.path.islink', return_value=False):
                            with patch('os.path.getsize', return_value=1024):
                                result = get_folder_size_in_bytes_updates('/test')
                                # Should only count game.exe, not files in Updates/Extras
                                assert result == 1024


class TestReadFirstNfoContent:
    """Test cases for read_first_nfo_content function."""
    
    def test_read_first_nfo_content_file_path(self):
        """Test read_first_nfo_content with file path instead of directory."""
        with patch('os.path.isfile', return_value=True):
            with patch('builtins.print') as mock_print:
                result = read_first_nfo_content('/path/to/file.txt')
                assert result is None
                mock_print.assert_called_with("Path is a file, not a directory. Skipping NFO scan.")
    
    def test_read_first_nfo_content_no_nfo_file(self):
        """Test read_first_nfo_content when no NFO file exists."""
        with patch('os.path.isfile', return_value=False):
            with patch('os.listdir', return_value=['game.exe', 'readme.txt']):
                with patch('builtins.print') as mock_print:
                    result = read_first_nfo_content('/path/to/game')
                    assert result is None
                    assert any('No NFO file found' in str(call) for call in mock_print.call_args_list)
    
    def test_read_first_nfo_content_success(self):
        """Test read_first_nfo_content successfully reading NFO file."""
        nfo_content = "Game Name: Test Game\nRelease Date: 2023\nDescription: A test game"
        
        with patch('os.path.isfile', return_value=False):
            with patch('os.listdir', return_value=['game.nfo', 'game.exe']):
                with patch('builtins.open', mock_open(read_data=nfo_content)):
                    with patch('builtins.print'):
                        result = read_first_nfo_content('/path/to/game')
                        assert result == nfo_content
    
    def test_read_first_nfo_content_with_null_bytes(self):
        """Test read_first_nfo_content removes null bytes from content."""
        nfo_content = "Game\x00Name: Test\x00Game"
        expected_content = "GameName: TestGame"
        
        with patch('os.path.isfile', return_value=False):
            with patch('os.listdir', return_value=['info.nfo']):
                with patch('builtins.open', mock_open(read_data=nfo_content)):
                    with patch('builtins.print'):
                        result = read_first_nfo_content('/path/to/game')
                        assert result == expected_content
    
    def test_read_first_nfo_content_read_error(self):
        """Test read_first_nfo_content handles file read errors."""
        with patch('os.path.isfile', return_value=False):
            with patch('os.listdir', return_value=['game.nfo']):
                with patch('builtins.open', side_effect=IOError("Permission denied")):
                    with patch('builtins.print') as mock_print:
                        result = read_first_nfo_content('/path/to/game')
                        assert result is None
                        # Should print error and continue


class TestDownloadImage:
    """Test cases for download_image function."""
    
    @patch('modules.utils_functions.requests')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('os.access')
    def test_download_image_success(self, mock_access, mock_exists, mock_makedirs, mock_requests):
        """Test successful image download."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'fake_image_data'
        mock_requests.get.return_value = mock_response
        
        # Mock directory operations
        mock_exists.return_value = True
        mock_access.return_value = True
        
        with patch('builtins.open', mock_open()) as mock_file:
            download_image('//example.com/image.jpg', '/path/to/save/image.jpg')
            
            # Verify URL was corrected to HTTPS
            mock_requests.get.assert_called_once_with('https://example.com/image.jpg')
            
            # Verify file was written
            mock_file.assert_called_once_with('/path/to/save/image.jpg', 'wb')
            mock_file().write.assert_called_once_with(b'fake_image_data')
    
    @patch('modules.utils_functions.requests')
    def test_download_image_url_transformation(self, mock_requests):
        """Test URL transformation from thumb to original."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'fake_image_data'
        mock_requests.get.return_value = mock_response
        
        with patch('os.path.exists', return_value=True):
            with patch('os.access', return_value=True):
                with patch('builtins.open', mock_open()):
                    # Test thumb URL transformation
                    download_image('https://example.com/t_thumb/image.jpg', '/path/image.jpg')
                    mock_requests.get.assert_called_with('https://example.com/t_original/image.jpg')
    
    @patch('modules.utils_functions.requests')
    def test_download_image_http_error(self, mock_requests):
        """Test download_image with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests.get.return_value = mock_response
        
        with patch('builtins.print') as mock_print:
            download_image('https://example.com/image.jpg', '/path/image.jpg')
            mock_print.assert_called_with("Failed to download the image. Status Code: 404")
    
    @patch('modules.utils_functions.requests')
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_download_image_create_directory(self, mock_exists, mock_makedirs, mock_requests):
        """Test download_image creates directory when it doesn't exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'fake_image_data'
        mock_requests.get.return_value = mock_response
        
        # Directory doesn't exist initially
        mock_exists.return_value = False
        
        with patch('os.access', return_value=True):
            with patch('builtins.open', mock_open()):
                with patch('builtins.print'):
                    download_image('https://example.com/image.jpg', '/new/path/image.jpg')
                    mock_makedirs.assert_called_once_with('/new/path', exist_ok=True)
    
    @patch('requests.get')
    def test_download_image_request_exception(self, mock_get):
        """Test download_image handles request exceptions."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")
        
        with patch('builtins.print') as mock_print:
            download_image('https://example.com/image.jpg', '/path/image.jpg')
            mock_print.assert_called()


class TestCommaSeparatedUrls:
    """Test cases for comma_separated_urls validator."""
    
    def test_comma_separated_urls_valid_single(self):
        """Test comma_separated_urls with single valid URL."""
        mock_form = MagicMock()
        mock_field = MagicMock()
        mock_field.data = 'https://www.youtube.com/embed/dQw4w9WgXcQ'
        
        # Should not raise an exception
        comma_separated_urls(mock_form, mock_field)
    
    def test_comma_separated_urls_valid_multiple(self):
        """Test comma_separated_urls with multiple valid URLs."""
        mock_form = MagicMock()
        mock_field = MagicMock()
        mock_field.data = 'https://www.youtube.com/embed/dQw4w9WgXcQ,https://youtube.com/embed/abc123,http://www.youtube.com/embed/xyz789'
        
        # Should not raise an exception
        comma_separated_urls(mock_form, mock_field)
    
    def test_comma_separated_urls_invalid_single(self):
        """Test comma_separated_urls with invalid URL."""
        mock_form = MagicMock()
        mock_field = MagicMock()
        mock_field.data = 'https://example.com/video'
        
        with pytest.raises(ValidationError) as exc_info:
            comma_separated_urls(mock_form, mock_field)
        
        assert 'invalid' in str(exc_info.value)
    
    def test_comma_separated_urls_mixed_valid_invalid(self):
        """Test comma_separated_urls with mix of valid and invalid URLs."""
        mock_form = MagicMock()
        mock_field = MagicMock()
        mock_field.data = 'https://www.youtube.com/embed/valid,https://example.com/invalid'
        
        with pytest.raises(ValidationError):
            comma_separated_urls(mock_form, mock_field)
    
    def test_comma_separated_urls_empty_string(self):
        """Test comma_separated_urls with empty string."""
        mock_form = MagicMock()
        mock_field = MagicMock()
        mock_field.data = ''
        
        with pytest.raises(ValidationError):
            comma_separated_urls(mock_form, mock_field)


class TestWebsiteCategoryToString:
    """Test cases for website_category_to_string function."""
    
    def test_website_category_to_string_known_ids(self):
        """Test website_category_to_string with known category IDs."""
        assert website_category_to_string(1) == "official"
        assert website_category_to_string(4) == "facebook"
        assert website_category_to_string(7) == "website"  # Test the newly added category ID 7
        assert website_category_to_string(9) == "youtube"
        assert website_category_to_string(13) == "steam"
        assert website_category_to_string(18) == "discord"
    
    def test_website_category_to_string_unknown_id(self):
        """Test website_category_to_string with unknown category ID."""
        assert website_category_to_string(999) == "website"
        assert website_category_to_string(0) == "website"
        assert website_category_to_string(-1) == "website"
    
    def test_website_category_to_string_none_input(self):
        """Test website_category_to_string with None input."""
        assert website_category_to_string(None) == "website"
        
    def test_website_category_to_string_with_url_fallback(self):
        """Test website_category_to_string with URL pattern matching fallback."""
        # Test unknown category ID but recognizable URL patterns
        assert website_category_to_string(999, "https://store.steampowered.com/app/123") == "steam"
        assert website_category_to_string(0, "https://www.gog.com/game/example") == "gog"
        assert website_category_to_string(-1, "https://youtube.com/watch?v=abc") == "youtube"
        assert website_category_to_string(999, "https://twitter.com/example") == "twitter"
        assert website_category_to_string(999, "https://some-unknown-site.com") == "website"
        
    def test_website_category_to_string_known_id_with_url(self):
        """Test that known category IDs take precedence over URL patterns."""
        # Should return mapped value, not URL-based detection
        assert website_category_to_string(13, "https://youtube.com/example") == "steam"  # 13 = steam
        assert website_category_to_string(4, "https://twitter.com/example") == "facebook"  # 4 = facebook


class TestPlatformIds:
    """Test cases for PLATFORM_IDS constant."""
    
    def test_platform_ids_contains_expected_platforms(self):
        """Test PLATFORM_IDS contains expected platforms."""
        assert "PCWIN" in PLATFORM_IDS
        assert "PS5" in PLATFORM_IDS
        assert "XBOX" in PLATFORM_IDS
        assert "SNES" in PLATFORM_IDS
        
    def test_platform_ids_values(self):
        """Test specific PLATFORM_IDS values."""
        assert PLATFORM_IDS["PCWIN"] == 6
        assert PLATFORM_IDS["PS5"] == 167
        assert PLATFORM_IDS["XSX"] == 169
        assert PLATFORM_IDS["OTHER"] is None


class TestLoadScanningFilterPatterns:
    """Test cases for load_scanning_filter_patterns function."""
    
    def test_load_scanning_filter_patterns_success(self, db_session, sample_release_groups):
        """Test load_scanning_filter_patterns with sample data."""
        insensitive, sensitive = load_scanning_filter_patterns()
        
        # Check insensitive patterns (all groups get both - and . prefixes)
        assert "-TEST_GROUP_1" in insensitive
        assert ".TEST_GROUP_1" in insensitive
        assert "-TEST_GROUP_2" in insensitive
        assert ".TEST_GROUP_2" in insensitive

        # Check sensitive patterns
        sensitive_dict = {pattern: case_sensitive for pattern, case_sensitive in sensitive}

        # TEST_GROUP_3 has case_sensitive='yes' so should be case sensitive
        assert ("-TEST_GROUP_3", True) in sensitive
        assert (".TEST_GROUP_3", True) in sensitive

        # TEST_GROUP_4 has case_sensitive='no' so should not be case sensitive
        assert ("-TEST_GROUP_4", False) in sensitive
        assert (".TEST_GROUP_4", False) in sensitive
    
    def test_load_scanning_filter_patterns_empty_db(self, db_session):
        """Test load_scanning_filter_patterns with empty database."""
        # Mock empty database response
        with patch('modules.utils_functions.db.session.execute') as mock_execute:
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_execute.return_value.scalars.return_value = mock_scalars
            
            insensitive, sensitive = load_scanning_filter_patterns()
            assert insensitive == []
            assert sensitive == []
    
    def test_load_scanning_filter_patterns_db_error(self, db_session):
        """Test load_scanning_filter_patterns handles database errors."""
        from sqlalchemy.exc import SQLAlchemyError
        with patch('modules.utils_functions.db.session.execute', side_effect=SQLAlchemyError("DB Error")):
            with patch('builtins.print') as mock_print:
                insensitive, sensitive = load_scanning_filter_patterns()
                assert insensitive == []
                assert sensitive == []
                mock_print.assert_called()


class TestGetLibraryCount:
    """Test cases for get_library_count function."""
    
    def test_get_library_count_with_libraries(self, db_session, app):
        """Test get_library_count with sample libraries."""
        # Mock sample libraries response
        mock_libraries = [
            MagicMock(uuid='lib1', name='Lib 1', image_url='url1'),
            MagicMock(uuid='lib2', name='Lib 2', image_url=None),
            MagicMock(uuid='lib3', name='Lib 3', image_url='url3')
        ]
        
        with app.app_context():
            with patch('modules.utils_functions.db.session.execute') as mock_execute:
                with patch('modules.utils_functions.url_for', return_value='/static/default.jpg') as mock_url_for:
                    mock_scalars = MagicMock()
                    mock_scalars.all.return_value = mock_libraries
                    mock_execute.return_value.scalars.return_value = mock_scalars
                    
                    count = get_library_count()
                    assert count == 3
    
    def test_get_library_count_empty_db(self, db_session):
        """Test get_library_count with no libraries."""
        # Mock empty database response
        with patch('modules.utils_functions.db.session.execute') as mock_execute:
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_execute.return_value.scalars.return_value = mock_scalars
            
            count = get_library_count()
            assert count == 0
    
    def test_get_library_count_prints_result(self, db_session):
        """Test get_library_count prints the count."""
        # Mock sample libraries response
        mock_libraries = [MagicMock(), MagicMock(), MagicMock()]
        
        with patch('modules.utils_functions.db.session.execute') as mock_execute:
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = mock_libraries
            mock_execute.return_value.scalars.return_value = mock_scalars
            
            with patch('builtins.print') as mock_print:
                count = get_library_count()
                mock_print.assert_called_with("Returning 3 libraries.")


class TestGetGamesCount:
    """Test cases for get_games_count function."""
    
    def test_get_games_count_with_games(self, db_session):
        """Test get_games_count with sample games."""
        # Mock sample games response
        mock_games = [
            MagicMock(uuid='game1', name='Game 1'),
            MagicMock(uuid='game2', name='Game 2'),
            MagicMock(uuid='game3', name='Game 3'),
            MagicMock(uuid='game4', name='Game 4'),
            MagicMock(uuid='game5', name='Game 5')
        ]
        
        with patch('modules.utils_functions.db.session.execute') as mock_execute:
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = mock_games
            mock_execute.return_value.scalars.return_value = mock_scalars
            
            count = get_games_count()
            assert count == 5
    
    def test_get_games_count_empty_db(self, db_session):
        """Test get_games_count with no games."""
        # Mock empty database response  
        with patch('modules.utils_functions.db.session.execute') as mock_execute:
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_execute.return_value.scalars.return_value = mock_scalars
            
            count = get_games_count()
            assert count == 0
    
    def test_get_games_count_prints_result(self, db_session):
        """Test get_games_count prints the count."""
        # Mock sample games response
        mock_games = [MagicMock() for _ in range(5)]
        
        with patch('modules.utils_functions.db.session.execute') as mock_execute:
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = mock_games
            mock_execute.return_value.scalars.return_value = mock_scalars
            
            with patch('builtins.print') as mock_print:
                count = get_games_count()
                mock_print.assert_called_with("Returning 5 games.")


class TestDeleteAssociationsForGame:
    """Test cases for delete_associations_for_game function."""
    
    def test_delete_associations_for_game(self, db_session):
        """Test delete_associations_for_game clears associations."""
        # Create a mock game with associations
        mock_game = MagicMock()
        mock_game.genres = MagicMock()
        mock_game.platforms = MagicMock()
        mock_game.game_modes = MagicMock()
        mock_game.themes = MagicMock()
        mock_game.player_perspectives = MagicMock()
        mock_game.multiplayer_modes = MagicMock()
        
        delete_associations_for_game(mock_game)
        
        # Verify all associations were cleared
        mock_game.genres.clear.assert_called_once()
        mock_game.platforms.clear.assert_called_once()
        mock_game.game_modes.clear.assert_called_once()
        mock_game.themes.clear.assert_called_once()
        mock_game.player_perspectives.clear.assert_called_once()
        mock_game.multiplayer_modes.clear.assert_called_once()


class TestSanitizeStringInput:
    """Test cases for sanitize_string_input function."""
    
    def test_sanitize_string_input_none_input(self):
        """Test sanitize_string_input with None input."""
        result = sanitize_string_input(None, 100)
        assert result == ''
    
    def test_sanitize_string_input_empty_string(self):
        """Test sanitize_string_input with empty string."""
        result = sanitize_string_input('', 100)
        assert result == ''
    
    def test_sanitize_string_input_normal_string(self):
        """Test sanitize_string_input with normal string."""
        result = sanitize_string_input('  Hello World  ', 100)
        assert result == 'Hello World'
    
    def test_sanitize_string_input_html_escaping(self):
        """Test sanitize_string_input escapes HTML by default."""
        result = sanitize_string_input('<script>alert("xss")</script>', 100)
        assert '&lt;script&gt;' in result
        assert '&lt;/script&gt;' in result
    
    def test_sanitize_string_input_allow_html(self):
        """Test sanitize_string_input allows HTML when specified."""
        html_input = '<b>Bold text</b>'
        result = sanitize_string_input(html_input, 100, allow_html=True)
        assert result == html_input
    
    def test_sanitize_string_input_length_limit(self):
        """Test sanitize_string_input enforces length limit."""
        long_string = 'a' * 200
        result = sanitize_string_input(long_string, 50)
        assert len(result) == 50
        assert result == 'a' * 50
    
    def test_sanitize_string_input_non_string_input(self):
        """Test sanitize_string_input converts non-string input."""
        result = sanitize_string_input(12345, 100)
        assert result == '12345'


class TestValidateDiscordWebhookUrl:
    """Test cases for validate_discord_webhook_url function."""
    
    def test_validate_discord_webhook_url_valid(self):
        """Test validate_discord_webhook_url with valid URL."""
        valid_url = 'https://discord.com/api/webhooks/123456789/abcdef'
        is_valid, result = validate_discord_webhook_url(valid_url)
        assert is_valid is True
        assert result == valid_url
    
    def test_validate_discord_webhook_url_valid_discordapp(self):
        """Test validate_discord_webhook_url with valid discordapp.com URL."""
        valid_url = 'https://discordapp.com/api/webhooks/123456789/abcdef'
        is_valid, result = validate_discord_webhook_url(valid_url)
        assert is_valid is True
        assert result == valid_url
    
    def test_validate_discord_webhook_url_empty(self):
        """Test validate_discord_webhook_url with empty URL."""
        is_valid, error = validate_discord_webhook_url('')
        assert is_valid is False
        assert error == "Webhook URL is required"
    
    def test_validate_discord_webhook_url_none(self):
        """Test validate_discord_webhook_url with None URL."""
        is_valid, error = validate_discord_webhook_url(None)
        assert is_valid is False
        assert error == "Webhook URL is required"
    
    def test_validate_discord_webhook_url_not_https(self):
        """Test validate_discord_webhook_url with HTTP URL."""
        http_url = 'http://discord.com/api/webhooks/123456789/abcdef'
        is_valid, error = validate_discord_webhook_url(http_url)
        assert is_valid is False
        assert error == "Webhook URL must use HTTPS"
    
    def test_validate_discord_webhook_url_not_discord(self):
        """Test validate_discord_webhook_url with non-Discord URL."""
        non_discord_url = 'https://example.com/webhook'
        is_valid, error = validate_discord_webhook_url(non_discord_url)
        assert is_valid is False
        assert error == "URL must be a valid Discord webhook URL"
    
    def test_validate_discord_webhook_url_invalid_format(self):
        """Test validate_discord_webhook_url with invalid URL format."""
        invalid_url = 'not-a-url'
        is_valid, error = validate_discord_webhook_url(invalid_url)
        assert is_valid is False
        assert error == "Invalid URL format"
    
    def test_validate_discord_webhook_url_too_long(self):
        """Test validate_discord_webhook_url with URL too long gets truncated."""
        long_url = 'https://discord.com/api/webhooks/' + 'a' * 600
        is_valid, result = validate_discord_webhook_url(long_url, max_length=512)
        # The URL should be truncated to max_length, not rejected
        assert is_valid is True
        assert len(result) == 512


class TestValidateDiscordBotName:
    """Test cases for validate_discord_bot_name function."""
    
    def test_validate_discord_bot_name_valid(self):
        """Test validate_discord_bot_name with valid name."""
        valid_name = 'My Bot 2023'
        is_valid, result = validate_discord_bot_name(valid_name)
        assert is_valid is True
        assert result == valid_name
    
    def test_validate_discord_bot_name_empty(self):
        """Test validate_discord_bot_name with empty name."""
        is_valid, error = validate_discord_bot_name('')
        assert is_valid is False
        assert error == "Bot name is required"
    
    def test_validate_discord_bot_name_none(self):
        """Test validate_discord_bot_name with None name."""
        is_valid, error = validate_discord_bot_name(None)
        assert is_valid is False
        assert error == "Bot name is required"
    
    def test_validate_discord_bot_name_valid_characters(self):
        """Test validate_discord_bot_name with valid characters."""
        valid_name = 'Bot_Name-2023.v1'
        is_valid, result = validate_discord_bot_name(valid_name)
        assert is_valid is True
        assert result == valid_name
    
    def test_validate_discord_bot_name_invalid_characters(self):
        """Test validate_discord_bot_name with invalid characters."""
        invalid_name = 'Bot@Name#2023!'
        is_valid, error = validate_discord_bot_name(invalid_name)
        assert is_valid is False
        assert "can only contain" in error
    
    def test_validate_discord_bot_name_too_long(self):
        """Test validate_discord_bot_name with name too long gets truncated."""
        long_name = 'a' * 150
        is_valid, result = validate_discord_bot_name(long_name, max_length=100)
        # The name should be truncated to max_length, not rejected
        assert is_valid is True
        assert len(result) == 100
    
    def test_validate_discord_bot_name_strips_whitespace(self):
        """Test validate_discord_bot_name strips whitespace."""
        name_with_spaces = '  Bot Name  '
        is_valid, result = validate_discord_bot_name(name_with_spaces)
        assert is_valid is True
        assert result == 'Bot Name'


class TestValidateDiscordAvatarUrl:
    """Test cases for validate_discord_avatar_url function."""
    
    def test_validate_discord_avatar_url_valid(self):
        """Test validate_discord_avatar_url with valid URL."""
        valid_url = 'https://example.com/avatar.png'
        is_valid, result = validate_discord_avatar_url(valid_url)
        assert is_valid is True
        assert result == valid_url
    
    def test_validate_discord_avatar_url_empty(self):
        """Test validate_discord_avatar_url with empty URL (optional field)."""
        is_valid, result = validate_discord_avatar_url('')
        assert is_valid is True
        assert result == ''
    
    def test_validate_discord_avatar_url_none(self):
        """Test validate_discord_avatar_url with None URL (optional field)."""
        is_valid, result = validate_discord_avatar_url(None)
        assert is_valid is True
        assert result == ''
    
    def test_validate_discord_avatar_url_not_https(self):
        """Test validate_discord_avatar_url with HTTP URL."""
        http_url = 'http://example.com/avatar.png'
        is_valid, error = validate_discord_avatar_url(http_url)
        assert is_valid is False
        assert error == "Avatar URL must use HTTPS"
    
    def test_validate_discord_avatar_url_invalid_format(self):
        """Test validate_discord_avatar_url with invalid URL format."""
        invalid_url = 'not-a-url'
        is_valid, error = validate_discord_avatar_url(invalid_url)
        assert is_valid is False
        assert error == "Invalid URL format"
    
    def test_validate_discord_avatar_url_too_long(self):
        """Test validate_discord_avatar_url with URL too long gets truncated."""
        long_url = 'https://example.com/' + 'a' * 600 + '.png'
        is_valid, result = validate_discord_avatar_url(long_url, max_length=512)
        # The URL should be truncated to max_length, not rejected
        assert is_valid is True
        assert len(result) == 512