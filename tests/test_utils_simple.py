import pytest
from unittest.mock import patch, Mock

# Test simple utility modules without complex dependencies


class TestUtilsAuth:
    """Test utils_auth module functions."""
    
    @patch('modules.utils_auth.check_password_hash')
    @patch('modules.utils_auth.User')
    def test_authenticate_user_success(self, mock_user, mock_check_password):
        """Test successful user authentication."""
        from modules.utils_auth import authenticate_user
        
        mock_user_instance = Mock()
        mock_user_instance.username = "testuser"
        mock_user.query.filter_by.return_value.first.return_value = mock_user_instance
        mock_check_password.return_value = True
        
        result = authenticate_user("testuser", "password")
        assert result == mock_user_instance
    
    @patch('modules.utils_auth.User')
    def test_authenticate_user_not_found(self, mock_user):
        """Test user authentication when user not found."""
        from modules.utils_auth import authenticate_user
        
        mock_user.query.filter_by.return_value.first.return_value = None
        
        result = authenticate_user("nonexistent", "password")
        assert result is None


class TestUtilsFilename:
    """Test utils_filename module functions."""
    
    def test_clean_filename_basic(self):
        """Test basic filename cleaning."""
        from modules.utils_filename import clean_filename
        
        result = clean_filename("Test Game: Special Edition")
        assert ":" not in result
        assert len(result) > 0
    
    def test_clean_filename_special_chars(self):
        """Test filename cleaning with special characters."""
        from modules.utils_filename import clean_filename
        
        result = clean_filename("Game|Name<>?*")
        # Should remove problematic characters
        assert all(char not in result for char in "|<>?*")
    
    def test_clean_filename_empty(self):
        """Test filename cleaning with empty string."""
        from modules.utils_filename import clean_filename
        
        result = clean_filename("")
        assert isinstance(result, str)


class TestUtilsUptime:
    """Test utils_uptime module functions."""
    
    @patch('modules.utils_uptime.psutil.boot_time')
    def test_get_system_uptime_success(self, mock_boot_time):
        """Test successful system uptime retrieval."""
        from modules.utils_uptime import get_system_uptime
        import time
        
        # Mock boot time to 1 hour ago
        mock_boot_time.return_value = time.time() - 3600
        
        result = get_system_uptime()
        assert result > 0
        assert result < 7200  # Should be around 1 hour
    
    @patch('modules.utils_uptime.psutil.boot_time')
    def test_get_system_uptime_error(self, mock_boot_time):
        """Test system uptime with error."""
        from modules.utils_uptime import get_system_uptime
        
        mock_boot_time.side_effect = Exception("Error")
        
        result = get_system_uptime()
        assert result == 0
    
    def test_format_uptime_seconds(self):
        """Test uptime formatting for seconds."""
        from modules.utils_uptime import format_uptime
        
        result = format_uptime(45)
        assert "45 seconds" in result
    
    def test_format_uptime_hours(self):
        """Test uptime formatting for hours."""
        from modules.utils_uptime import format_uptime
        
        result = format_uptime(7200)  # 2 hours
        assert "2 hours" in result
    
    def test_format_uptime_days(self):
        """Test uptime formatting for days."""
        from modules.utils_uptime import format_uptime
        
        result = format_uptime(172800)  # 2 days
        assert "2 days" in result


class TestUtilsGamenames:
    """Test utils_gamenames module functions."""
    
    def test_clean_game_name_basic(self):
        """Test basic game name cleaning."""
        from modules.utils_gamenames import clean_game_name
        
        result = clean_game_name("Test Game (2023)")
        assert "2023" not in result
        assert "Test Game" in result
    
    def test_clean_game_name_brackets(self):
        """Test game name cleaning with brackets."""
        from modules.utils_gamenames import clean_game_name
        
        result = clean_game_name("Game [Region] (Year)")
        # Should remove bracketed content
        assert "[" not in result
        assert "]" not in result
        assert "(" not in result
        assert ")" not in result
    
    def test_clean_game_name_multiple_brackets(self):
        """Test game name cleaning with multiple brackets."""
        from modules.utils_gamenames import clean_game_name
        
        result = clean_game_name("Game (USA) [v1.1] (2023)")
        assert "Game" in result
        assert "USA" not in result
        assert "v1.1" not in result
        assert "2023" not in result


class TestUtilsPlatform:
    """Test platform module functions."""
    
    def test_get_platform_enum_windows(self):
        """Test getting platform enum for Windows."""
        from modules.platform import get_platform_enum
        
        result = get_platform_enum("Windows")
        assert result is not None
    
    def test_get_platform_enum_linux(self):
        """Test getting platform enum for Linux.""" 
        from modules.platform import get_platform_enum
        
        result = get_platform_enum("Linux")
        assert result is not None
    
    def test_get_platform_enum_invalid(self):
        """Test getting platform enum for invalid platform."""
        from modules.platform import get_platform_enum
        
        result = get_platform_enum("InvalidPlatform")
        # Should return default or None
        assert result is None or str(result)


class TestUtilsDiscord:
    """Test basic discord utilities."""
    
    @patch('modules.utils_discord.requests.post')
    @patch('modules.utils_discord.GlobalSettings')
    def test_discord_webhook_success(self, mock_settings, mock_post):
        """Test successful Discord webhook."""
        from modules.utils_discord import discord_webhook
        
        mock_settings_instance = Mock()
        mock_settings_instance.discord_webhook_url = "https://discord.com/api/webhooks/test"
        mock_settings.query.first.return_value = mock_settings_instance
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = discord_webhook("Test message")
        assert result is True
    
    @patch('modules.utils_discord.GlobalSettings')
    def test_discord_webhook_no_settings(self, mock_settings):
        """Test Discord webhook with no settings."""
        from modules.utils_discord import discord_webhook
        
        mock_settings.query.first.return_value = None
        
        result = discord_webhook("Test message")
        assert result is False
    
    @patch('modules.utils_discord.requests.post')
    @patch('modules.utils_discord.GlobalSettings')
    def test_discord_webhook_http_error(self, mock_settings, mock_post):
        """Test Discord webhook with HTTP error."""
        from modules.utils_discord import discord_webhook
        
        mock_settings_instance = Mock()
        mock_settings_instance.discord_webhook_url = "https://discord.com/api/webhooks/test"
        mock_settings.query.first.return_value = mock_settings_instance
        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = Exception("Bad Request")
        mock_post.return_value = mock_response
        
        result = discord_webhook("Test message")
        assert result is False