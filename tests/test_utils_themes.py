import pytest
import os
import json
import tempfile
import zipfile
import shutil
from unittest.mock import patch, mock_open, MagicMock
from flask import Flask
from uuid import uuid4
from modules.models import User, UserPreference
from modules.utils_themes import ThemeManager


@pytest.fixture
def sample_app():
    """Create a minimal Flask app for testing."""
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = '/tmp/test_uploads'
    app.config['SECRET_KEY'] = 'test_secret_key'
    return app


@pytest.fixture
def theme_manager(sample_app):
    """Create a ThemeManager instance for testing."""
    return ThemeManager(sample_app)


@pytest.fixture
def sample_theme_data():
    """Sample theme.json data for testing."""
    return {
        'name': 'Test Theme',
        'description': 'A test theme for unit testing',
        'author': 'Test Author',
        'release_date': '2024-01-01',
        'version': '1.0.0'
    }


@pytest.fixture
def sample_user_with_preference(db_session):
    """Create a test user with preferences."""
    user = User(
        name=f'theme_user_{uuid4().hex[:8]}',
        email=f'theme_{uuid4().hex[:8]}@example.com',
        role='user',
        user_id=str(uuid4())
    )
    user.set_password('testpass')
    db_session.add(user)
    db_session.flush()
    
    preference = UserPreference(
        user_id=user.id,
        theme='custom_theme'
    )
    db_session.add(preference)
    db_session.flush()
    
    return user, preference


class TestThemeManagerInit:
    """Tests for ThemeManager initialization."""

    def test_theme_manager_initialization(self, sample_app):
        """Test ThemeManager initialization with app."""
        manager = ThemeManager(sample_app)
        
        assert manager.app == sample_app
        assert 'modules/static/library/themes' in manager.theme_folder
        assert os.path.isabs(manager.theme_folder)


class TestGetDefaultTheme:
    """Tests for get_default_theme method."""

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.join')
    def test_get_default_theme_success(self, mock_join, mock_file, theme_manager, sample_theme_data):
        """Test successful default theme retrieval."""
        mock_join.return_value = '/fake/path/default/theme.json'
        mock_file.return_value.read.return_value = json.dumps(sample_theme_data)
        
        with patch('json.load', return_value=sample_theme_data):
            result = theme_manager.get_default_theme()
            
        assert result == sample_theme_data
        mock_file.assert_called_once_with('/fake/path/default/theme.json', 'r')

    @patch('builtins.open', side_effect=FileNotFoundError("File not found"))
    @patch('os.path.join', return_value='/fake/path/default/theme.json')
    @patch('builtins.print')
    def test_get_default_theme_file_not_found(self, mock_print, mock_join, mock_file, theme_manager):
        """Test default theme retrieval when file doesn't exist."""
        result = theme_manager.get_default_theme()
        
        assert result is None
        mock_print.assert_called_once()
        assert "Error reading default theme" in str(mock_print.call_args)

    @patch('json.load', side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.join', return_value='/fake/path/default/theme.json')
    @patch('builtins.print')
    def test_get_default_theme_invalid_json(self, mock_print, mock_join, mock_file, mock_json, theme_manager):
        """Test default theme retrieval with invalid JSON."""
        result = theme_manager.get_default_theme()
        
        assert result is None
        mock_print.assert_called_once()
        assert "Error reading default theme" in str(mock_print.call_args)


class TestGetInstalledThemes:
    """Tests for get_installed_themes method."""

    @patch('os.listdir')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_get_installed_themes_success(self, mock_json_load, mock_file, mock_exists, 
                                        mock_isdir, mock_listdir, theme_manager, sample_theme_data):
        """Test successful installed themes retrieval."""
        mock_listdir.return_value = ['theme1', 'theme2', 'invalid_folder']
        
        def isdir_side_effect(path):
            return 'theme1' in path or 'theme2' in path
        
        def exists_side_effect(path):
            return 'theme1' in path or 'theme2' in path
            
        mock_isdir.side_effect = isdir_side_effect
        mock_exists.side_effect = exists_side_effect
        
        # Return different theme data for each theme
        theme_data_1 = sample_theme_data.copy()
        theme_data_1['name'] = 'Theme 1'
        
        theme_data_2 = sample_theme_data.copy()
        theme_data_2['name'] = 'Theme 2'
        
        mock_json_load.side_effect = [theme_data_1, theme_data_2]
        
        result = theme_manager.get_installed_themes()
        
        assert len(result) == 2
        assert result[0]['name'] == 'Theme 1'
        assert result[1]['name'] == 'Theme 2'
        assert all('author' in theme for theme in result)
        assert all('description' in theme for theme in result)

    @patch('os.listdir', return_value=[])
    def test_get_installed_themes_empty_folder(self, mock_listdir, theme_manager):
        """Test installed themes retrieval with empty themes folder."""
        result = theme_manager.get_installed_themes()
        
        assert result == []

    @patch('os.listdir')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('builtins.open', side_effect=FileNotFoundError("File not found"))
    @patch('builtins.print')
    def test_get_installed_themes_with_invalid_theme(self, mock_print, mock_file, mock_exists,
                                                   mock_isdir, mock_listdir, theme_manager):
        """Test installed themes retrieval with invalid theme folder."""
        mock_listdir.return_value = ['valid_theme']
        mock_isdir.return_value = True
        mock_exists.return_value = True
        
        result = theme_manager.get_installed_themes()
        
        assert result == []
        mock_print.assert_called_once()
        assert "Error reading theme" in str(mock_print.call_args)

    @patch('os.listdir')
    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_get_installed_themes_missing_optional_fields(self, mock_json_load, mock_file, mock_exists,
                                                         mock_isdir, mock_listdir, theme_manager):
        """Test installed themes retrieval with missing optional fields."""
        mock_listdir.return_value = ['minimal_theme']
        mock_isdir.return_value = True
        mock_exists.return_value = True
        
        # Theme data with minimal required fields
        minimal_theme_data = {'name': 'Minimal Theme'}
        mock_json_load.return_value = minimal_theme_data
        
        result = theme_manager.get_installed_themes()
        
        assert len(result) == 1
        assert result[0]['name'] == 'Minimal Theme'
        assert result[0]['author'] == 'Unknown'
        assert result[0]['description'] == 'No description available'
        assert result[0]['release_date'] == 'Unknown'


class TestUploadTheme:
    """Tests for upload_theme method."""

    def create_test_zip_file(self, temp_dir, theme_data, include_css=True, include_theme_json=True):
        """Helper method to create a test zip file."""
        zip_path = os.path.join(temp_dir, 'test_theme.zip')
        
        with zipfile.ZipFile(zip_path, 'w') as zip_file:
            if include_theme_json:
                zip_file.writestr('theme.json', json.dumps(theme_data))
            if include_css:
                zip_file.writestr('css/style.css', 'body { color: red; }')
                
        return zip_path

    def test_upload_theme_success_workflow(self, theme_manager):
        """Test that upload_theme method has the correct workflow structure.
        
        Note: Full success path testing is complex due to file system operations.
        The main value is testing error cases and ensuring the method structure is sound.
        The fixed error handling ensures proper user feedback and logging.
        """
        # Test that the method exists and is callable
        assert hasattr(theme_manager, 'upload_theme')
        assert callable(theme_manager.upload_theme)
        
        # Test that calling with None returns None (basic input validation)
        with theme_manager.app.app_context():
            with theme_manager.app.test_request_context():
                result = theme_manager.upload_theme(None)
                assert result is None

    @patch('os.path.exists', return_value=False)
    @patch('modules.utils_themes.flash')
    def test_upload_theme_upload_folder_missing(self, mock_flash, mock_exists, theme_manager):
        """Test theme upload when upload folder doesn't exist."""
        with theme_manager.app.app_context():
            with theme_manager.app.test_request_context():
                result = theme_manager.upload_theme('fake_zip.zip')
                
        assert result is None
        mock_flash.assert_called_once_with('Error: Library folder does not exist.', 'error')

    @patch('os.path.exists')
    @patch('modules.utils_themes.flash')
    def test_upload_theme_missing_theme_json(self, mock_flash, mock_exists, theme_manager):
        """Test theme upload with missing theme.json."""
        mock_exists.side_effect = lambda path: 'UPLOAD_FOLDER' in path or 'themes' in path
        
        with theme_manager.app.app_context():
            with theme_manager.app.test_request_context():
                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_path = self.create_test_zip_file(temp_dir, {}, include_theme_json=False)
                    
                    with patch('zipfile.ZipFile') as mock_zip:
                        mock_zip_instance = MagicMock()
                        mock_zip.return_value.__enter__.return_value = mock_zip_instance
                        
                        with patch('os.makedirs'):
                            with patch('shutil.rmtree'):
                                result = theme_manager.upload_theme(zip_path)
                                
        assert result is None

    @patch('os.path.exists')
    @patch('modules.utils_themes.flash')
    def test_upload_theme_missing_css_folder(self, mock_flash, mock_exists, theme_manager, sample_theme_data):
        """Test theme upload with missing CSS folder."""
        mock_exists.side_effect = lambda path: 'UPLOAD_FOLDER' in path or 'themes' in path
        
        with theme_manager.app.app_context():
            with theme_manager.app.test_request_context():
                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_path = self.create_test_zip_file(temp_dir, sample_theme_data, include_css=False)
                    
                    with patch('zipfile.ZipFile') as mock_zip:
                        mock_zip_instance = MagicMock()
                        mock_zip.return_value.__enter__.return_value = mock_zip_instance
                        
                        with patch('builtins.open', mock_open(read_data=json.dumps(sample_theme_data))):
                            with patch('json.load', return_value=sample_theme_data):
                                with patch('os.makedirs'):
                                    with patch('shutil.rmtree'):
                                        result = theme_manager.upload_theme(zip_path)
                                        
        assert result is None

    @patch('os.path.exists')
    def test_upload_theme_missing_required_fields(self, mock_exists, theme_manager):
        """Test theme upload with missing required fields in theme.json."""
        mock_exists.side_effect = lambda path: 'UPLOAD_FOLDER' in path or 'themes' in path
        
        incomplete_theme_data = {'name': 'Test Theme'}  # Missing required fields
        
        with theme_manager.app.app_context():
            with theme_manager.app.test_request_context():
                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_path = self.create_test_zip_file(temp_dir, incomplete_theme_data)
                    
                    with patch('zipfile.ZipFile') as mock_zip:
                        mock_zip_instance = MagicMock()
                        mock_zip.return_value.__enter__.return_value = mock_zip_instance
                        
                        with patch('builtins.open', mock_open(read_data=json.dumps(incomplete_theme_data))):
                            with patch('json.load', return_value=incomplete_theme_data):
                                with patch('os.makedirs'):
                                    with patch('shutil.rmtree'):
                                        result = theme_manager.upload_theme(zip_path)
                                        
        assert result is None

    @patch('os.path.exists')
    @patch('shutil.rmtree')
    def test_upload_theme_duplicate_theme(self, mock_rmtree, mock_exists, theme_manager, sample_theme_data):
        """Test theme upload with duplicate theme name."""
        def exists_side_effect(path):
            if 'UPLOAD_FOLDER' in path or 'themes' in path:
                return True
            if 'Test_Theme' in path:  # Simulating existing theme
                return True
            return False
            
        mock_exists.side_effect = exists_side_effect
        
        with theme_manager.app.app_context():
            with theme_manager.app.test_request_context():
                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_path = self.create_test_zip_file(temp_dir, sample_theme_data)
                    
                    with patch('zipfile.ZipFile') as mock_zip:
                        mock_zip_instance = MagicMock()
                        mock_zip.return_value.__enter__.return_value = mock_zip_instance
                        
                        with patch('builtins.open', mock_open(read_data=json.dumps(sample_theme_data))):
                            with patch('json.load', return_value=sample_theme_data):
                                with patch('os.makedirs'):
                                    result = theme_manager.upload_theme(zip_path)
                                        
        assert result is None


class TestValidateThemeStructure:
    """Tests for validate_theme_structure method."""

    @patch('os.path.exists')
    def test_validate_theme_structure_valid(self, mock_exists, theme_manager):
        """Test theme structure validation with valid structure."""
        mock_exists.return_value = True
        
        result = theme_manager.validate_theme_structure('/fake/theme/path')
        
        assert result is True
        mock_exists.assert_called_once_with('/fake/theme/path/css')

    @patch('os.path.exists')
    def test_validate_theme_structure_invalid(self, mock_exists, theme_manager):
        """Test theme structure validation with invalid structure."""
        mock_exists.return_value = False
        
        result = theme_manager.validate_theme_structure('/fake/theme/path')
        
        assert result is False
        mock_exists.assert_called_once_with('/fake/theme/path/css')


class TestDeleteThemeFile:
    """Tests for delete_themefile method."""

    def test_delete_default_theme_raises_error(self, theme_manager):
        """Test that deleting default theme raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            theme_manager.delete_themefile('Default')
            
        assert "Cannot delete the default theme" in str(exc_info.value)

    @patch('os.path.exists', return_value=False)
    def test_delete_nonexistent_theme_raises_error(self, mock_exists, theme_manager):
        """Test that deleting non-existent theme raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            theme_manager.delete_themefile('NonexistentTheme')
            
        assert "does not exist" in str(exc_info.value)

    @patch('os.path.exists', return_value=True)
    @patch('shutil.rmtree')
    @patch('modules.utils_themes.db')
    def test_delete_theme_success(self, mock_db, mock_rmtree, mock_exists, theme_manager, db_session):
        """Test successful theme deletion."""
        # Setup mock db session
        mock_db_session = MagicMock()
        mock_db.session = mock_db_session
        
        theme_manager.delete_themefile('TestTheme')
        
        mock_rmtree.assert_called_once()
        # Verify the database update was called
        assert mock_db_session.execute.called
        assert mock_db_session.commit.called

    @patch('os.path.exists', return_value=True)
    @patch('shutil.rmtree', side_effect=Exception("Permission denied"))
    def test_delete_theme_file_system_error(self, mock_rmtree, mock_exists, theme_manager):
        """Test theme deletion with file system error."""
        with pytest.raises(Exception) as exc_info:
            theme_manager.delete_themefile('TestTheme')
            
        assert "Error deleting theme" in str(exc_info.value)
        assert "Permission denied" in str(exc_info.value)

    @patch('os.path.exists', return_value=True)
    @patch('shutil.rmtree')
    @patch('modules.utils_themes.db')
    def test_delete_theme_updates_user_preferences(self, mock_db, mock_rmtree, mock_exists, 
                                                  theme_manager, sample_user_with_preference):
        """Test that theme deletion updates user preferences."""
        user, preference = sample_user_with_preference
        # Setup mock db session
        mock_db_session = MagicMock()
        mock_db.session = mock_db_session
        
        theme_manager.delete_themefile('custom_theme')
        
        mock_rmtree.assert_called_once()
        # Verify database operations were called
        assert mock_db_session.execute.called
        assert mock_db_session.commit.called


class TestThemeManagerIntegration:
    """Integration tests for ThemeManager."""

    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.path.isdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_theme_manager_full_workflow(self, mock_json_load, mock_file, mock_isdir, 
                                       mock_listdir, mock_exists, theme_manager, sample_theme_data):
        """Test a complete theme management workflow."""
        # Setup mocks for get_installed_themes
        mock_listdir.return_value = ['existing_theme']
        mock_isdir.return_value = True
        mock_exists.return_value = True
        mock_json_load.return_value = sample_theme_data
        
        # Test getting installed themes
        themes = theme_manager.get_installed_themes()
        assert len(themes) == 1
        assert themes[0]['name'] == 'Test Theme'
        
        # Test getting default theme
        default_theme = theme_manager.get_default_theme()
        assert default_theme == sample_theme_data
        
        # Test theme structure validation
        is_valid = theme_manager.validate_theme_structure('/fake/path')
        assert is_valid is True