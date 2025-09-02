import pytest
import json
from unittest.mock import patch, mock_open, MagicMock
from sqlalchemy import delete
from modules import create_app, db
from modules.models import GlobalSettings
from modules.utils_processors import get_loc, get_global_settings
from modules import app_version


class TestGetLoc:
    """Tests for get_loc function."""
    
    def test_get_loc_success(self):
        """Test successful loading of localization file."""
        mock_data = {
            "heading": "Test Heading",
            "label": "Test Label",
            "section": {
                "title": "Test Title",
                "message": "Test Message"
            }
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            result = get_loc('discover')
        
        assert result == mock_data
        assert result['heading'] == 'Test Heading'
        assert result['section']['title'] == 'Test Title'
    
    def test_get_loc_with_utf8_content(self):
        """Test loading localization file with UTF-8 characters."""
        mock_data = {
            "heading": "Découvrir",
            "message": "Café résumé naïve"
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data, ensure_ascii=False))):
            result = get_loc('french_page')
        
        assert result == mock_data
        assert result['heading'] == 'Découvrir'
        assert result['message'] == 'Café résumé naïve'
    
    def test_get_loc_file_not_found(self):
        """Test handling when localization file doesn't exist."""
        with patch('builtins.open', side_effect=FileNotFoundError("No such file")):
            with pytest.raises(FileNotFoundError):
                get_loc('nonexistent_page')
    
    def test_get_loc_invalid_json(self):
        """Test handling of invalid JSON in localization file."""
        invalid_json = '{"heading": "Test", "invalid": json}'
        
        with patch('builtins.open', mock_open(read_data=invalid_json)):
            with pytest.raises(json.JSONDecodeError):
                get_loc('invalid_json_page')
    
    def test_get_loc_empty_file(self):
        """Test handling of empty localization file."""
        with patch('builtins.open', mock_open(read_data='')):
            with pytest.raises(json.JSONDecodeError):
                get_loc('empty_page')
    
    def test_get_loc_correct_file_path(self):
        """Test that correct file path is used."""
        mock_data = {"test": "data"}
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))) as mock_file:
            get_loc('test_page')
            mock_file.assert_called_once_with(
                'modules/static/localization/en/test_page.json', 
                'r', 
                encoding='utf8'
            )


class TestGetGlobalSettings:
    """Tests for get_global_settings function."""
    
    def test_get_global_settings_no_record(self, app, db_session):
        """Test get_global_settings when no GlobalSettings record exists."""
        with app.app_context():
            # Clear any existing settings first
            db_session.execute(delete(GlobalSettings))
            db_session.flush()
            
            result = get_global_settings()
        
        # Should return default values
        expected_defaults = {
            'show_logo': True,
            'show_help_button': True,
            'enable_web_links': True,
            'enable_server_status': True,
            'enable_newsletter': True,
            'show_version': True,
            'enable_delete_game_on_disk': True,
            'enable_game_updates': True,
            'enable_game_extras': True,
            'app_version': app_version
        }
        
        assert result == expected_defaults
        assert result['app_version'] == app_version
    
    def test_get_global_settings_empty_settings(self, app, db_session):
        """Test get_global_settings with GlobalSettings record but null settings."""
        with app.app_context():
            # Clear any existing settings first
            db_session.execute(delete(GlobalSettings))
            db_session.flush()
            
            # Create GlobalSettings record with no settings
            settings_record = GlobalSettings(settings=None)
            db_session.add(settings_record)
            db_session.flush()
            
            result = get_global_settings()
        
        # Should return default values
        expected_defaults = {
            'show_logo': True,
            'show_help_button': True,
            'enable_web_links': True,
            'enable_server_status': True,
            'enable_newsletter': True,
            'show_version': True,
            'enable_delete_game_on_disk': True,
            'enable_game_updates': True,
            'enable_game_extras': True,
            'app_version': app_version
        }
        
        assert result == expected_defaults
    
    def test_get_global_settings_partial_settings(self, app, db_session):
        """Test get_global_settings with partial settings that merge with defaults."""
        with app.app_context():
            # Clear existing settings first
            db_session.execute(delete(GlobalSettings))
            db_session.flush()
            
            # Create GlobalSettings record with partial settings
            partial_settings = {
                'showSystemLogo': False,
                'enableWebLinksOnDetailsPage': False,
                'enableServerStatusFeature': False
            }
            settings_record = GlobalSettings(settings=partial_settings)
            db_session.add(settings_record)
            db_session.flush()
            
            result = get_global_settings()
        
        # Should merge partial settings with defaults based on function behavior
        assert result['show_logo'] is False  # From partial settings via settings.get()
        assert result['enable_web_links'] is False  # From partial settings via settings.get()
        assert result['enable_server_status'] is False  # From partial settings via settings_record.settings.get()
        assert result['show_help_button'] is True  # From defaults (not overridden) via settings.get()
        assert result['enable_newsletter'] is False  # Default from settings_record.settings.get() since not in partial_settings
        assert result['app_version'] == app_version
    
    def test_get_global_settings_complete_settings(self, app, db_session):
        """Test get_global_settings with complete custom settings."""
        with app.app_context():
            # Clear existing settings first
            db_session.execute(delete(GlobalSettings))
            db_session.flush()
            
            # Create GlobalSettings record with complete custom settings
            custom_settings = {
                'showSystemLogo': False,
                'showHelpButton': False,
                'enableWebLinksOnDetailsPage': False,
                'enableServerStatusFeature': False,
                'enableNewsletterFeature': False,
                'showVersion': False,
                'enableDeleteGameOnDisk': False,
                'enableGameUpdates': False,
                'enableGameExtras': False
            }
            settings_record = GlobalSettings(settings=custom_settings)
            db_session.add(settings_record)
            db_session.flush()
            
            result = get_global_settings()
        
        # Should use custom settings based on function behavior
        assert result['show_logo'] is False  # settings.get('showSystemLogo')
        assert result['show_help_button'] is False  # settings.get('showHelpButton')
        assert result['enable_web_links'] is False  # settings.get('enableWebLinksOnDetailsPage')
        assert result['enable_server_status'] is False  # settings_record.settings.get('enableServerStatusFeature', False)
        assert result['enable_newsletter'] is False  # settings_record.settings.get('enableNewsletterFeature', False)
        assert result['show_version'] is False  # settings_record.settings.get('showVersion', False)
        assert result['enable_delete_game_on_disk'] is False  # settings_record.settings.get('enableDeleteGameOnDisk', True)
        assert result['enable_game_updates'] is False  # settings_record.settings.get('enableGameUpdates', True)
        assert result['enable_game_extras'] is False  # settings_record.settings.get('enableGameExtras', True)
        assert result['app_version'] == app_version
    
    def test_get_global_settings_includes_app_version(self, app, db_session):
        """Test that app_version is always included in result."""
        with app.app_context():
            # Clear existing settings first
            db_session.execute(delete(GlobalSettings))
            db_session.flush()
            
            # Test with no settings record
            result = get_global_settings()
            assert 'app_version' in result
            assert result['app_version'] == app_version
            
            # Test with settings record
            settings_record = GlobalSettings(settings={'showSystemLogo': True})
            db_session.add(settings_record)
            db_session.flush()
            
            result = get_global_settings()
            assert 'app_version' in result
            assert result['app_version'] == app_version
    
    def test_get_global_settings_return_keys(self, app, db_session):
        """Test that all expected keys are present in return value."""
        with app.app_context():
            # Clear existing settings first
            db_session.execute(delete(GlobalSettings))
            db_session.flush()
            
            result = get_global_settings()
        
        expected_keys = {
            'show_logo',
            'show_help_button', 
            'enable_web_links',
            'enable_server_status',
            'enable_newsletter',
            'show_version',
            'enable_delete_game_on_disk',
            'enable_game_updates',
            'enable_game_extras',
            'app_version'
        }
        
        assert set(result.keys()) == expected_keys
    
    def test_get_global_settings_duplicate_defaults_handling(self, app, db_session):
        """Test that duplicate keys in default_settings are handled correctly."""
        # The function has duplicate keys in default_settings dict
        # This test ensures the function handles this gracefully
        with app.app_context():
            # Clear existing settings first
            db_session.execute(delete(GlobalSettings))
            db_session.flush()
            
            result = get_global_settings()
        
        # Should not cause errors and return valid result
        assert isinstance(result, dict)
        assert len(result) == 10  # Should have exactly 10 keys
        assert all(key in result for key in [
            'show_logo', 'show_help_button', 'enable_web_links',
            'enable_server_status', 'enable_newsletter', 'show_version',
            'enable_delete_game_on_disk', 'enable_game_updates',
            'enable_game_extras', 'app_version'
        ])
    
    def test_get_global_settings_boolean_types(self, app, db_session):
        """Test that all settings (except app_version) return boolean values."""
        with app.app_context():
            # Clear existing settings first
            db_session.execute(delete(GlobalSettings))
            db_session.flush()
            
            result = get_global_settings()
        
        for key, value in result.items():
            if key != 'app_version':
                assert isinstance(value, bool), f"Key '{key}' should be boolean, got {type(value)}"
        
        assert isinstance(result['app_version'], str)
    
    @pytest.fixture
    def sample_global_settings(self, db_session):
        """Create sample GlobalSettings for testing."""
        settings = GlobalSettings(
            settings={
                'showSystemLogo': True,
                'enableWebLinksOnDetailsPage': True,
                'enableServerStatusFeature': True
            }
        )
        db_session.add(settings)
        db_session.flush()
        return settings
    
    def test_get_global_settings_with_fixture(self, app, db_session):
        """Test get_global_settings using fixture data pattern."""
        with app.app_context():
            # Clear existing settings first
            db_session.execute(delete(GlobalSettings))
            db_session.flush()
            
            # Create fresh fixture-like settings
            fixture_settings = GlobalSettings(
                settings={
                    'showSystemLogo': True,
                    'enableWebLinksOnDetailsPage': True,
                    'enableServerStatusFeature': True
                }
            )
            db_session.add(fixture_settings)
            db_session.flush()
            
            result = get_global_settings()
        
        assert result['show_logo'] is True
        assert result['enable_web_links'] is True  
        assert result['enable_server_status'] is True
        assert result['app_version'] == app_version