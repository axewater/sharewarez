import pytest
from unittest.mock import patch, MagicMock, mock_open
from modules.utils_game_core import get_game_by_uuid, remove_from_lib, check_existing_game_by_path
from modules.utils_gamenames import get_game_names_from_folder, get_game_name_by_uuid
from modules.utils_discord import get_library_by_uuid, get_game_name_by_uuid as discord_get_game_name
from modules.utils_auth import load_user


class TestGameCoreFunctions:
    """Test core game management functions."""
    
    @patch('modules.utils_game_core.Game')
    def test_get_game_by_uuid_found(self, mock_game_model):
        """Test get_game_by_uuid when game exists."""
        mock_game = MagicMock()
        mock_game.id = 1
        mock_game.name = "Test Game"
        mock_game.uuid = "test-uuid"
        mock_game.igdb_id = 12345
        
        mock_game_model.query.filter_by.return_value.first.return_value = mock_game
        
        from modules.utils_game_core import get_game_by_uuid
        result = get_game_by_uuid("test-uuid")
        
        assert result == mock_game
        mock_game_model.query.filter_by.assert_called_once_with(uuid="test-uuid")
    
    @patch('modules.utils_game_core.Game')
    def test_get_game_by_uuid_not_found(self, mock_game_model):
        """Test get_game_by_uuid when game doesn't exist."""
        mock_game_model.query.filter_by.return_value.first.return_value = None
        
        from modules.utils_game_core import get_game_by_uuid
        result = get_game_by_uuid("nonexistent-uuid")
        
        assert result is None
        mock_game_model.query.filter_by.assert_called_once_with(uuid="nonexistent-uuid")
    
    @patch('modules.utils_game_core.log_system_event')
    @patch('modules.utils_game_core.delete_game_images')
    @patch('modules.utils_game_core.db')
    @patch('modules.utils_game_core.Game')
    def test_remove_from_lib_success(self, mock_game_model, mock_db, mock_delete_images, mock_log):
        """Test successful game removal from library."""
        mock_game = MagicMock()
        mock_game.uuid = "test-uuid"
        mock_game.name = "Test Game"
        mock_game_model.query.filter_by.return_value.first.return_value = mock_game
        
        from modules.utils_game_core import remove_from_lib
        result = remove_from_lib("test-uuid")
        
        assert result is True
        mock_delete_images.assert_called_once_with("test-uuid")
        mock_db.session.delete.assert_called_once_with(mock_game)
        mock_db.session.commit.assert_called_once()
    
    @patch('modules.utils_game_core.Game')
    def test_remove_from_lib_game_not_found(self, mock_game_model):
        """Test game removal when game doesn't exist."""
        mock_game_model.query.filter_by.return_value.first.return_value = None
        
        from modules.utils_game_core import remove_from_lib
        result = remove_from_lib("nonexistent-uuid")
        
        assert result is False


class TestGameNamesFunctions:
    """Test game name processing functions."""
    
    @patch('os.path.exists')
    @patch('os.access')
    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_get_game_names_from_folder_success(self, mock_isdir, mock_listdir, mock_access, mock_exists):
        """Test successful folder scanning for game names."""
        mock_exists.return_value = True
        mock_access.return_value = True
        mock_listdir.return_value = ['Game.1-GOG', 'Game.2-FLT', 'not_a_folder.txt']
        mock_isdir.side_effect = lambda path: 'not_a_folder.txt' not in path
        
        from modules.utils_gamenames import get_game_names_from_folder
        result = get_game_names_from_folder('/test/path', ['-GOG', '-FLT'], [])
        
        assert len(result) == 2
        assert any(game['name'] == 'Game 1' for game in result)
        assert any(game['name'] == 'Game 2' for game in result)
    
    @patch('modules.utils_gamenames.Game')
    def test_get_game_name_by_uuid_found(self, mock_game_model):
        """Test get_game_name_by_uuid when game exists."""
        mock_game = MagicMock()
        mock_game.name = "Test Game"
        mock_game.uuid = "test-uuid"
        mock_game_model.query.filter_by.return_value.first.return_value = mock_game
        
        from modules.utils_gamenames import get_game_name_by_uuid
        result = get_game_name_by_uuid("test-uuid")
        
        assert result == "Test Game"
        mock_game_model.query.filter_by.assert_called_once_with(uuid="test-uuid")


class TestDiscordUtilsFunctions:
    """Test Discord utility functions."""
    
    @patch('modules.utils_discord.Library')
    def test_get_library_by_uuid_found(self, mock_library_model):
        """Test get_library_by_uuid when library exists."""
        mock_library = MagicMock()
        mock_library.name = "Test Library"
        mock_library.uuid = "test-uuid"
        mock_library_model.query.filter_by.return_value.first.return_value = mock_library
        
        from modules.utils_discord import get_library_by_uuid
        result = get_library_by_uuid("test-uuid")
        
        assert result == mock_library
        mock_library_model.query.filter_by.assert_called_once_with(uuid="test-uuid")
    
    @patch('modules.utils_discord.Game')
    def test_discord_get_game_name_by_uuid_found(self, mock_game_model):
        """Test Discord's get_game_name_by_uuid when game exists."""
        mock_game = MagicMock()
        mock_game.name = "Test Game"
        mock_game.uuid = "test-uuid"
        mock_game_model.query.filter_by.return_value.first.return_value = mock_game
        
        from modules.utils_discord import get_game_name_by_uuid
        result = get_game_name_by_uuid("test-uuid")
        
        assert result == "Test Game"
        mock_game_model.query.filter_by.assert_called_once_with(uuid="test-uuid")


class TestAuthFunctions:
    """Test authentication utility functions."""
    
    @patch('modules.utils_auth.User')
    def test_load_user_found(self, mock_user_model):
        """Test load_user when user exists."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user_model.query.get.return_value = mock_user
        
        from modules.utils_auth import load_user
        result = load_user("1")
        
        assert result == mock_user
        mock_user_model.query.get.assert_called_once_with(1)
    
    @patch('modules.utils_auth.User')
    def test_load_user_not_found(self, mock_user_model):
        """Test load_user when user doesn't exist."""
        mock_user_model.query.get.return_value = None
        
        from modules.utils_auth import load_user
        result = load_user("999")
        
        assert result is None
        mock_user_model.query.get.assert_called_once_with(999)