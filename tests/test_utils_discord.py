import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock, call, ANY
from uuid import uuid4
from datetime import datetime, timezone

from modules import create_app, db
from modules.models import Library, GlobalSettings, Game, GameURL
from modules.platform import LibraryPlatform
from modules.utils_discord import (
    get_folder_size_in_bytes,
    discord_webhook,
    get_library_by_uuid,
    get_game_name_by_uuid,
    update_game_size,
    get_game_by_full_disk_path
)
from sqlalchemy import select, delete




def create_test_library(db_session, name="Test Library"):
    """Helper function to create a test library."""
    library = Library(
        uuid=str(uuid4()),
        name=name,
        image_url="https://example.com/image.jpg",
        platform=LibraryPlatform.PCWIN,
        display_order=0
    )
    db_session.add(library)
    db_session.commit()
    return library


def create_test_game(db_session, library_uuid, name="Test Game", igdb_id=None):
    """Helper function to create a test game."""
    import random
    game = Game(
        uuid=str(uuid4()),
        name=name,
        library_uuid=library_uuid,
        full_disk_path="/path/to/game",
        size=1024,
        igdb_id=igdb_id or random.randint(100000, 999999),  # Random IGDB ID to avoid conflicts
        summary="Test game summary"
    )
    db_session.add(game)
    db_session.commit()
    return game


def create_test_global_settings(db_session, webhook_url="default", notify_enabled=True):
    """Helper function to create test global settings."""
    # Delete any existing settings first for test isolation
    db_session.execute(delete(GlobalSettings))
    db_session.commit()
    
    # Use default URL when webhook_url is "default", otherwise use the provided value (including None)
    webhook_url_value = "https://discord.com/api/webhooks/123456789/abcdef" if webhook_url == "default" else webhook_url
    
    settings = GlobalSettings(
        discord_webhook_url=webhook_url_value,
        discord_notify_new_games=notify_enabled,
        discord_bot_name="TestBot",
        discord_bot_avatar_url="https://example.com/avatar.png",
        site_url="https://test.example.com"
    )
    db_session.add(settings)
    db_session.commit()
    return settings


class TestGetFolderSizeInBytes:
    """Test get_folder_size_in_bytes function."""

    def test_single_file_size(self):
        """Test getting size of a single file."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            test_content = b"Hello, World!"
            temp_file.write(test_content)
            temp_file.flush()
            
            try:
                size = get_folder_size_in_bytes(temp_file.name)
                assert size == len(test_content)
            finally:
                os.unlink(temp_file.name)

    def test_directory_with_multiple_files(self):
        """Test getting size of directory with multiple files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple files
            file1_content = b"File 1 content"
            file2_content = b"File 2 has more content"
            
            file1_path = os.path.join(temp_dir, "file1.txt")
            file2_path = os.path.join(temp_dir, "file2.txt")
            
            with open(file1_path, 'wb') as f1:
                f1.write(file1_content)
            with open(file2_path, 'wb') as f2:
                f2.write(file2_content)
            
            expected_size = len(file1_content) + len(file2_content)
            actual_size = get_folder_size_in_bytes(temp_dir)
            
            assert actual_size == expected_size

    def test_nested_directories(self):
        """Test getting size of nested directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested structure
            nested_dir = os.path.join(temp_dir, "nested")
            os.makedirs(nested_dir)
            
            file1_content = b"Root file"
            file2_content = b"Nested file content"
            
            with open(os.path.join(temp_dir, "root.txt"), 'wb') as f:
                f.write(file1_content)
            with open(os.path.join(nested_dir, "nested.txt"), 'wb') as f:
                f.write(file2_content)
            
            expected_size = len(file1_content) + len(file2_content)
            actual_size = get_folder_size_in_bytes(temp_dir)
            
            assert actual_size == expected_size

    def test_nonexistent_path(self):
        """Test behavior with non-existent path."""
        with patch('os.path.exists', return_value=False):
            with patch('os.path.isfile', return_value=False):
                with patch('os.walk', return_value=[]):
                    size = get_folder_size_in_bytes("/nonexistent/path")
                    assert size == 1  # Should return minimum 1 byte

    def test_minimum_size_one_byte(self):
        """Test that function returns at least 1 byte."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Empty directory should return 1 byte
            size = get_folder_size_in_bytes(temp_dir)
            assert size >= 1


class TestDiscordWebhook:
    """Test discord_webhook function."""

    @patch('modules.utils_discord.get_cover_url')
    @patch('modules.utils_discord.format_size')
    @patch('modules.utils_discord.DiscordWebhook')
    @patch('modules.utils_discord.DiscordEmbed')
    def test_successful_webhook_execution(self, mock_embed_class, mock_webhook_class, 
                                        mock_format_size, mock_get_cover_url, app, db_session, capsys):
        """Test successful Discord webhook execution with all components."""
        with app.app_context():
            # Setup test data
            settings = create_test_global_settings(db_session)
            library = create_test_library(db_session)
            game = create_test_game(db_session, library.uuid)
            
            # Setup mocks
            mock_format_size.return_value = "1.0 KB"
            mock_get_cover_url.return_value = "https://example.com/cover.jpg"
            
            mock_webhook_instance = MagicMock()
            mock_webhook_class.return_value = mock_webhook_instance
            mock_webhook_instance.execute.return_value = "Success response"
            
            mock_embed_instance = MagicMock()
            mock_embed_class.return_value = mock_embed_instance
            
            # Execute function
            discord_webhook(game.uuid)
            
            # Verify webhook was created with correct URL
            mock_webhook_class.assert_called_once_with(url=settings.discord_webhook_url, rate_limit_retry=True)
            
            # Verify embed was created with game details
            mock_embed_class.assert_called_once_with(
                title=game.name,
                description=game.summary,
                url=f"{settings.site_url}/game_details/{game.uuid}",
                color="03b2f8"
            )
            
            # Verify embed methods were called
            mock_embed_instance.set_author.assert_called_once_with(
                name=settings.discord_bot_name,
                url=settings.site_url,
                icon_url=settings.discord_bot_avatar_url
            )
            mock_embed_instance.set_image.assert_called_once_with(url="https://example.com/cover.jpg")
            mock_embed_instance.set_footer.assert_called_once_with(text="This game is now available for download")
            mock_embed_instance.set_timestamp.assert_called_once()
            
            # Verify embed fields
            embed_field_calls = mock_embed_instance.add_embed_field.call_args_list
            assert len(embed_field_calls) == 2
            assert embed_field_calls[0] == call(name="Library", value=library.name)
            assert embed_field_calls[1] == call(name="Size", value="1.0 KB")
            
            # Verify webhook execution
            mock_webhook_instance.add_embed.assert_called_once_with(mock_embed_instance)
            mock_webhook_instance.execute.assert_called_once()

    def test_no_global_settings(self, app, db_session, capsys):
        """Test early return when no global settings exist."""
        with app.app_context():
            # Delete all global settings to simulate none existing
            db_session.execute(delete(GlobalSettings))
            db_session.commit()
            
            discord_webhook("some-uuid")
            
            captured = capsys.readouterr()
            assert "Webhook URL not configured. Exiting." in captured.out

    def test_no_webhook_url(self, app, db_session, capsys):
        """Test early return when webhook URL is not configured."""
        with app.app_context():
            settings = create_test_global_settings(db_session, webhook_url=None)
            
            # Verify that settings were created with None webhook URL
            assert settings.discord_webhook_url is None
            
            discord_webhook("some-uuid")
            
            captured = capsys.readouterr()
            assert "Webhook URL not configured. Exiting." in captured.out

    def test_notifications_disabled(self, app, db_session, capsys):
        """Test early return when notifications are disabled."""
        with app.app_context():
            settings = create_test_global_settings(db_session, notify_enabled=False)
            
            discord_webhook("some-uuid")
            
            captured = capsys.readouterr()
            assert "Disabled for new games. Exiting." in captured.out

    def test_game_not_found(self, app, db_session, capsys):
        """Test early return when game UUID is not found."""
        with app.app_context():
            settings = create_test_global_settings(db_session)
            nonexistent_uuid = str(uuid4())
            
            discord_webhook(nonexistent_uuid)
            
            captured = capsys.readouterr()
            assert f"Game with UUID '{nonexistent_uuid}' could not be found. Exiting." in captured.out

    @patch('modules.utils_discord.get_cover_url')
    @patch('modules.utils_discord.format_size')
    @patch('modules.utils_discord.DiscordWebhook')
    @patch('modules.utils_discord.DiscordEmbed')
    def test_game_with_no_summary(self, mock_embed_class, mock_webhook_class, 
                                mock_format_size, mock_get_cover_url, app, db_session):
        """Test webhook execution with game that has no summary."""
        with app.app_context():
            settings = create_test_global_settings(db_session)
            library = create_test_library(db_session)
            
            # Create game with no summary
            import random
            game = Game(
                uuid=str(uuid4()),
                name="Game No Summary",
                library_uuid=library.uuid,
                full_disk_path="/path/to/game",
                size=1024,
                igdb_id=random.randint(100000, 999999),  # Random IGDB ID to avoid conflicts
                summary=None  # Explicitly None
            )
            db_session.add(game)
            db_session.commit()
            
            mock_format_size.return_value = "1.0 KB"
            mock_get_cover_url.return_value = "https://example.com/cover.jpg"
            
            mock_webhook_instance = MagicMock()
            mock_webhook_class.return_value = mock_webhook_instance
            mock_embed_instance = MagicMock()
            mock_embed_class.return_value = mock_embed_instance
            
            discord_webhook(game.uuid)
            
            # Verify embed was created with empty description for None summary
            mock_embed_class.assert_called_once_with(
                title=game.name,
                description="",  # Should fallback to empty string
                url=f"{settings.site_url}/game_details/{game.uuid}",
                color="03b2f8"
            )

    @patch('modules.utils_discord.get_cover_url')
    @patch('modules.utils_discord.format_size')
    @patch('modules.utils_discord.DiscordWebhook')
    @patch('modules.utils_discord.DiscordEmbed')
    def test_webhook_response_handling_with_redaction(self, mock_embed_class, mock_webhook_class,
                                                    mock_format_size, mock_get_cover_url,
                                                    app, db_session, capsys):
        """Test webhook response sanitization for security."""
        with app.app_context():
            settings = create_test_global_settings(db_session)
            library = create_test_library(db_session)
            game = create_test_game(db_session, library.uuid)
            
            mock_format_size.return_value = "1.0 KB"
            mock_get_cover_url.return_value = "https://example.com/cover.jpg"
            
            # Mock webhook response containing the webhook URL
            mock_webhook_instance = MagicMock()
            mock_webhook_class.return_value = mock_webhook_instance
            response_with_url = f"Response containing {settings.discord_webhook_url} in output"
            mock_webhook_instance.execute.return_value = response_with_url
            
            mock_embed_instance = MagicMock()
            mock_embed_class.return_value = mock_embed_instance
            
            discord_webhook(game.uuid)
            
            captured = capsys.readouterr()
            assert "***WEBHOOK_URL_REDACTED***" in captured.out
            assert settings.discord_webhook_url not in captured.out

    @patch('modules.utils_discord.get_cover_url')
    @patch('modules.utils_discord.format_size')
    @patch('modules.utils_discord.DiscordWebhook')
    @patch('modules.utils_discord.DiscordEmbed')
    def test_no_webhook_response(self, mock_embed_class, mock_webhook_class,
                                mock_format_size, mock_get_cover_url,
                                app, db_session, capsys):
        """Test handling of no webhook response."""
        with app.app_context():
            settings = create_test_global_settings(db_session)
            library = create_test_library(db_session)
            game = create_test_game(db_session, library.uuid)
            
            mock_format_size.return_value = "1.0 KB"
            mock_get_cover_url.return_value = "https://example.com/cover.jpg"
            
            mock_webhook_instance = MagicMock()
            mock_webhook_class.return_value = mock_webhook_instance
            mock_webhook_instance.execute.return_value = None
            
            mock_embed_instance = MagicMock()
            mock_embed_class.return_value = mock_embed_instance
            
            discord_webhook(game.uuid)
            
            captured = capsys.readouterr()
            assert "No response received." in captured.out


class TestGetLibraryByUuid:
    """Test get_library_by_uuid function."""

    def test_library_found(self, app, db_session, capsys):
        """Test successful library retrieval."""
        with app.app_context():
            library = create_test_library(db_session, "Found Library")
            
            result = get_library_by_uuid(library.uuid)
            
            assert result is not None
            assert result.uuid == library.uuid
            assert result.name == "Found Library"
            
            captured = capsys.readouterr()
            assert f"Searching for Library UUID: {library.uuid}" in captured.out
            assert f"Library with name {library.name} and UUID {library.uuid} found" in captured.out

    def test_library_not_found(self, app, db_session, capsys):
        """Test library not found scenario."""
        with app.app_context():
            nonexistent_uuid = str(uuid4())
            
            result = get_library_by_uuid(nonexistent_uuid)
            
            assert result is None
            
            captured = capsys.readouterr()
            assert f"Searching for Library UUID: {nonexistent_uuid}" in captured.out
            assert "Library not found" in captured.out


class TestGetGameNameByUuid:
    """Test get_game_name_by_uuid function."""

    def test_game_found(self, app, db_session, capsys):
        """Test successful game name retrieval."""
        with app.app_context():
            library = create_test_library(db_session)
            game = create_test_game(db_session, library.uuid, "Found Game")
            
            result = get_game_name_by_uuid(game.uuid)
            
            assert result == "Found Game"
            
            captured = capsys.readouterr()
            assert f"Searching for game UUID: {game.uuid}" in captured.out
            assert f"Game with name {game.name} and UUID {game.uuid} found" in captured.out

    def test_game_not_found(self, app, db_session, capsys):
        """Test game not found scenario."""
        with app.app_context():
            nonexistent_uuid = str(uuid4())
            
            result = get_game_name_by_uuid(nonexistent_uuid)
            
            assert result is None
            
            captured = capsys.readouterr()
            assert f"Searching for game UUID: {nonexistent_uuid}" in captured.out
            assert "Game not found" in captured.out


class TestUpdateGameSize:
    """Test update_game_size function."""

    def test_successful_size_update(self, app, db_session):
        """Test successful game size update."""
        with app.app_context():
            library = create_test_library(db_session)
            game = create_test_game(db_session, library.uuid)
            original_size = game.size
            new_size = 2048
            
            result = update_game_size(game.uuid, new_size)
            
            assert result is None  # Function returns None
            
            # Refresh game from database
            updated_game = db_session.execute(select(Game).filter_by(uuid=game.uuid)).scalars().first()
            assert updated_game.size == new_size
            assert updated_game.size != original_size

    def test_update_nonexistent_game(self, app, db_session):
        """Test update with nonexistent game UUID."""
        with app.app_context():
            nonexistent_uuid = str(uuid4())
            
            result = update_game_size(nonexistent_uuid, 2048)
            
            assert result is None  # Function returns None regardless


class TestGetGameByFullDiskPath:
    """Test get_game_by_full_disk_path function."""

    def test_exact_path_match(self, app, db_session):
        """Test finding game by exact full disk path match."""
        with app.app_context():
            # Clean up any games that might have the same path
            from sqlalchemy import delete
            db_session.execute(delete(Game).filter_by(full_disk_path="/exact/path/to/game"))
            db_session.commit()
            
            library = create_test_library(db_session)
            game_path = "/exact/path/to/game"
            game = create_test_game(db_session, library.uuid, "Exact Path Game")
            game.full_disk_path = game_path
            db_session.commit()
            
            result = get_game_by_full_disk_path(game_path)
            
            assert result is not None
            assert result.uuid == game.uuid
            assert result.full_disk_path == game_path

    def test_parent_directory_fallback(self, app, db_session):
        """Test fallback to parent directory when file_path provided."""
        with app.app_context():
            # Clean up any games that might have the same path
            from sqlalchemy import delete
            parent_path = "/path/to/game/subfolder"  # This is what dirname will return
            db_session.execute(delete(Game).filter_by(full_disk_path=parent_path))
            db_session.commit()
            
            library = create_test_library(db_session)
            file_path = "/path/to/game/subfolder/game.exe"
            
            game = create_test_game(db_session, library.uuid, "Parent Path Game")
            game.full_disk_path = parent_path
            db_session.commit()
            
            # Search for non-matching path but provide file_path for fallback
            result = get_game_by_full_disk_path("/non/matching/path", file_path=file_path)
            
            assert result is not None
            assert result.uuid == game.uuid
            assert result.full_disk_path == parent_path

    def test_no_match_found(self, app, db_session):
        """Test when no game matches the path."""
        with app.app_context():
            library = create_test_library(db_session)
            game = create_test_game(db_session, library.uuid)
            
            result = get_game_by_full_disk_path("/completely/different/path")
            
            assert result is None

    def test_no_match_with_file_path(self, app, db_session):
        """Test when no game matches path or parent directory."""
        with app.app_context():
            library = create_test_library(db_session)
            game = create_test_game(db_session, library.uuid)
            
            result = get_game_by_full_disk_path(
                "/completely/different/path", 
                file_path="/another/different/path/file.exe"
            )
            
            assert result is None

    @patch('modules.utils_discord.db.session.execute')
    def test_exception_handling(self, mock_execute, app, capsys):
        """Test exception handling in get_game_by_full_disk_path."""
        with app.app_context():
            # Mock database exception
            mock_execute.side_effect = Exception("Database error")
            
            result = get_game_by_full_disk_path("/some/path")
            
            assert result is None
            
            captured = capsys.readouterr()
            assert "Error finding game by path /some/path: Database error" in captured.out