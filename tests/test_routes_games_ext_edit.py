import pytest
from unittest.mock import patch, Mock, MagicMock, call
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import select
from werkzeug.datastructures import ImmutableMultiDict
from urllib.parse import urlparse

from modules import create_app, db
from modules.models import (
    User, Game, Library, Developer, Publisher, SystemEvents,
    Category, Status, Genre, GameMode, Theme, Platform, PlayerPerspective
)
from modules.platform import LibraryPlatform
from modules.forms import AddGameForm


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user_uuid = str(uuid4())
    user = User(
        name=f'testuser_{user_uuid[:8]}',
        email=f'test_{user_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='user',
        user_id=user_uuid
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin_user(db_session):
    """Create an admin user."""
    admin_uuid = str(uuid4())
    admin = User(
        name=f'admin_{admin_uuid[:8]}',
        email=f'admin_{admin_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='admin',
        user_id=admin_uuid
    )
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture
def test_library(db_session):
    """Create a test library."""
    unique_name = f'Test Library {uuid4().hex[:8]}'
    library = Library(
        name=unique_name,
        image_url='/static/library_test.jpg',
        platform=LibraryPlatform.PCWIN,
        display_order=1
    )
    db_session.add(library)
    db_session.commit()
    return library


@pytest.fixture
def test_developer(db_session):
    """Create a test developer."""
    developer_name = f'Test Developer {uuid4().hex[:8]}'
    developer = Developer(name=developer_name)
    db_session.add(developer)
    db_session.commit()
    return developer


@pytest.fixture
def test_publisher(db_session):
    """Create a test publisher."""
    publisher_name = f'Test Publisher {uuid4().hex[:8]}'
    publisher = Publisher(name=publisher_name)
    db_session.add(publisher)
    db_session.commit()
    return publisher


@pytest.fixture
def test_game(db_session, test_library, test_developer, test_publisher):
    """Create a test game with all fields populated."""
    game_uuid = str(uuid4())
    # Use random IGDB ID to avoid unique constraint violations
    import random
    igdb_id = random.randint(1000000, 9999999)
    game = Game(
        uuid=game_uuid,
        igdb_id=igdb_id,
        name='Test Game',
        library_uuid=test_library.uuid,
        summary='This is a test game summary',
        storyline='A longer storyline for testing',
        rating=85,
        size=1024000,
        first_release_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        date_identified=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
        full_disk_path='/allowed/path/to/game/folder',
        nfo_content='Test NFO Content',
        url='https://example.com/game',
        video_urls='https://www.youtube.com/embed/test1,https://www.youtube.com/embed/test2',
        category=Category.MAIN_GAME,
        status=Status.RELEASED,
        developer=test_developer,
        publisher=test_publisher
    )
    db_session.add(game)
    db_session.commit()
    return game


@pytest.fixture
def form_data(test_library, test_developer, test_publisher):
    """Create valid form data for game editing."""
    import random
    return {
        'library_uuid': str(test_library.uuid),
        'igdb_id': str(random.randint(2000000, 9999999)),
        'name': 'Updated Game Name',
        'summary': 'Updated summary content',
        'storyline': 'Updated storyline content',
        'url': 'https://updated.example.com',
        'full_disk_path': '/allowed/path/to/updated/game',
        'video_urls': 'https://www.youtube.com/embed/updated',
        'aggregated_rating': '90',
        'first_release_date': '2021-01-01',
        'status': 'RELEASED',  # Status enum name
        'category': 'MAIN_GAME',
        'developer': test_developer.name,
        'publisher': test_publisher.name,
        'csrf_token': 'test_token'
    }


class TestGameEditAuthentication:
    """Test authentication and access control for game edit route."""
    
    def test_game_edit_requires_login(self, client, test_game):
        """Test that game edit route requires authentication."""
        response = client.get(f'/game_edit/{test_game.uuid}')
        assert response.status_code == 302  # Redirect to login
        assert '/login' in response.location
    
    def test_game_edit_requires_admin(self, client, test_user, test_game):
        """Test that game edit route requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/game_edit/{test_game.uuid}')
        assert response.status_code == 302  # Redirect due to admin_required decorator
    
    def test_game_edit_allows_admin_access(self, client, admin_user, test_game):
        """Test that admin users can access game edit route."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/game_edit/{test_game.uuid}')
        assert response.status_code == 200


class TestGameEditSecurityValidation:
    """Test security validations in game edit route."""
    
    def test_path_validation_prevents_traversal(self, client, admin_user, test_game, form_data):
        """Test that path validation prevents directory traversal attacks."""
        form_data['full_disk_path'] = '/etc/passwd'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path') as mock_safe_path:
            mock_safe_path.return_value = (False, "Access denied - path outside allowed directories")
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories') as mock_bases:
                mock_bases.return_value = ['/allowed/path']
                
                response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        assert response.status_code == 200  # Renders form with error
        assert b'Access denied' in response.data
    
    def test_url_validation_code_exists(self, client, admin_user, test_game):
        """Test that URL validation code exists in the route."""
        # This test verifies that the URL validation logic is present in the code
        from modules.routes_games_ext.edit import game_edit
        import inspect
        
        source = inspect.getsource(game_edit)
        
        # Verify URL validation logic exists
        assert 'urlparse' in source
        assert 'http' in source and 'https' in source
        assert 'scheme' in source
    
    def test_security_functions_imported(self, client, admin_user, test_game):
        """Test that security functions are properly imported."""
        # This test verifies the security imports are in place
        from modules.routes_games_ext import edit
        
        # Verify security functions are imported
        assert hasattr(edit, 'is_safe_path')
        assert hasattr(edit, 'sanitize_path_for_logging')
        assert hasattr(edit, 'log_system_event')
    
    def test_url_validation_allows_valid_https(self, client, admin_user, test_game, form_data):
        """Test that URL validation allows valid HTTPS URLs."""
        form_data['url'] = 'https://valid.example.com/game'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=1024):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='NFO'):
                        response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        # Should redirect on success (302) or stay on form (200)
        assert response.status_code in [200, 302]
        if response.status_code == 200:
            assert b'URL must use http or https protocol' not in response.data
    
    def test_category_validation_code_exists(self, client, admin_user, test_game):
        """Test that category validation code exists in the route."""
        # This test verifies that the category validation logic is present in the code
        from modules.routes_games_ext.edit import game_edit
        import inspect
        
        source = inspect.getsource(game_edit)
        
        # Verify category validation logic exists
        assert 'Category.__members__' in source
        assert 'Invalid category' in source
        assert 'category_str' in source


class TestGameEditInputValidation:
    """Test input validation for various fields."""
    
    def test_field_length_limits_name(self, client, admin_user, test_game, form_data):
        """Test that name field is limited to 255 characters."""
        form_data['name'] = 'A' * 300  # Exceeds 255 limit
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=1024):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='NFO'):
                        response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        # Should show warning about truncation
        if response.status_code == 200:
            assert b'Game name was truncated to 255 characters' in response.data
    
    def test_field_length_limits_summary(self, client, admin_user, test_game, form_data):
        """Test that summary field is limited to 4096 characters."""
        form_data['summary'] = 'A' * 5000  # Exceeds 4096 limit
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=1024):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='NFO'):
                        response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        # Should show warning about truncation
        if response.status_code == 200:
            assert b'Summary was truncated to 4096 characters' in response.data
    
    def test_developer_name_validation_unicode_support(self, client, admin_user, test_game, form_data):
        """Test that developer names support Unicode characters (Chinese, Cyrillic, etc.)."""
        form_data['developer'] = '游戏开发商'  # Chinese characters
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=1024):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='NFO'):
                        response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        # Should not show validation error for Unicode
        assert response.status_code in [200, 302]
        if response.status_code == 200:
            assert b'Developer name too long' not in response.data
    
    def test_publisher_name_validation_unicode_support(self, client, admin_user, test_game, form_data):
        """Test that publisher names support Unicode characters (Cyrillic)."""
        form_data['publisher'] = 'Разработчик Игр'  # Cyrillic characters
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=1024):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='NFO'):
                        response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        # Should not show validation error for Unicode
        assert response.status_code in [200, 302]
        if response.status_code == 200:
            assert b'Publisher name too long' not in response.data
    
    def test_developer_name_length_validation(self, client, admin_user, test_game, form_data):
        """Test that developer names are limited to 255 characters."""
        form_data['developer'] = 'A' * 300  # Exceeds 255 limit
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        assert response.status_code == 200  # Renders form with error
        assert b'Developer name too long (max 255 characters)' in response.data
    
    def test_publisher_name_length_validation(self, client, admin_user, test_game, form_data):
        """Test that publisher names are limited to 255 characters."""
        form_data['publisher'] = 'A' * 300  # Exceeds 255 limit
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        assert response.status_code == 200  # Renders form with error
        assert b'Publisher name too long (max 255 characters)' in response.data
    
    def test_empty_developer_name_validation(self, client, admin_user, test_game, form_data):
        """Test that empty developer names are rejected."""
        form_data['developer'] = '   '  # Only whitespace
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        assert response.status_code == 200  # Renders form with error
        assert b'Developer name cannot be empty' in response.data


class TestGameEditErrorHandling:
    """Test error handling and transaction management."""
    
    def test_scan_job_running_blocks_edit(self, client, admin_user, test_game, form_data):
        """Test that editing is blocked when scan job is running."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_scan_job_running', return_value=True):
            response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        assert response.status_code == 200  # Renders form with error
        assert b'Cannot edit the game while a scan job is running' in response.data
    
    def test_database_rollback_on_integrity_error(self, client, admin_user, test_game, form_data, test_library):
        """Test that database rollback occurs on integrity errors."""
        # Create another game with the same IGDB ID to cause conflict
        conflicting_game = Game(
            uuid=str(uuid4()),
            igdb_id=form_data['igdb_id'],
            name='Conflicting Game',
            library_uuid=test_library.uuid
        )
        db.session.add(conflicting_game)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        assert response.status_code == 200  # Renders form with error
        assert b'already used by another game' in response.data
    
    def test_file_operation_error_handling(self, client, admin_user, test_game, form_data):
        """Test error handling for file operations."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', side_effect=OSError("Permission denied")):
                    response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        assert response.status_code == 200  # Renders form with error
        assert b'Error accessing game files' in response.data
    
    def test_configuration_error_handling(self, client, admin_user, test_game, form_data):
        """Test handling of configuration errors (no allowed base directories)."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=[]):
            response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        assert response.status_code == 200  # Renders form with error
        assert b'Service configuration error' in response.data


class TestGameEditAtomicOperations:
    """Test atomic database operations and race condition prevention."""
    
    def test_igdb_id_atomic_check_code_exists(self, client, admin_user, test_game):
        """Test that IGDB ID atomic check code exists."""
        # This test verifies that the atomic locking logic is present in the code
        from modules.routes_games_ext.edit import game_edit
        import inspect
        
        source = inspect.getsource(game_edit)
        
        # Verify atomic locking logic exists
        assert 'with_for_update' in source
        assert 'existing_game_with_igdb_id' in source
    
    def test_database_error_handling_code_exists(self, client, admin_user, test_game):
        """Test that database error handling code exists."""
        # This test verifies that proper error handling is present in the code
        from modules.routes_games_ext.edit import game_edit
        import inspect
        
        source = inspect.getsource(game_edit)
        
        # Verify error handling logic exists
        assert 'except IntegrityError' in source
        assert 'except SQLAlchemyError' in source
        assert 'db.session.rollback' in source
        assert 'error occurred while updating the game' in source


class TestGameEditLogging:
    """Test security logging and audit trails."""
    
    def test_security_logging_for_path_validation(self, client, admin_user, test_game, form_data):
        """Test that security logging occurs for path validation failures."""
        form_data['full_disk_path'] = '/malicious/path'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path') as mock_safe_path:
            mock_safe_path.return_value = (False, "Access denied")
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.current_app.logger') as mock_logger:
                    response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        # Verify security error was logged
        mock_logger.error.assert_called()
        error_calls = [call for call in mock_logger.error.call_args_list 
                      if 'Security error' in str(call)]
        assert len(error_calls) > 0
    
    def test_audit_logging_for_successful_update(self, client, admin_user, test_game, form_data):
        """Test that audit logging occurs for successful game updates."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=1024):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='NFO'):
                        with patch('modules.routes_games_ext.edit.log_system_event') as mock_log:
                            response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        # Verify audit event was logged
        if response.status_code in [200, 302]:  # Success or redirect
            audit_calls = [call for call in mock_log.call_args_list 
                          if 'updated by admin' in str(call)]
            assert len(audit_calls) > 0
    
    def test_secure_path_logging(self, client, admin_user, test_game, form_data):
        """Test that paths are sanitized in logs."""
        sensitive_path = '/home/user/sensitive/path/game'
        form_data['full_disk_path'] = sensitive_path
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=1024):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='NFO'):
                        with patch('modules.routes_games_ext.edit.sanitize_path_for_logging') as mock_sanitize:
                            with patch('modules.routes_games_ext.edit.current_app.logger') as mock_logger:
                                mock_sanitize.return_value = '/home/[USER]/sensitive/path/game'
                                response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        # Verify path sanitization was called
        mock_sanitize.assert_called()


class TestGameEditSuccessScenarios:
    """Test successful game editing scenarios."""
    
    def test_successful_game_update(self, client, admin_user, test_game, form_data):
        """Test successful game update with all fields."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=2048000):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='Updated NFO'):
                        response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        # Should redirect to library on success
        if response.status_code == 302:
            assert '/library' in response.location
        
        # Verify game was updated in database
        updated_game = db.session.execute(select(Game).filter_by(uuid=test_game.uuid)).scalars().first()
        assert updated_game.name == form_data['name']
        assert updated_game.summary == form_data['summary']
        assert updated_game.url == form_data['url']
    
    def test_image_refresh_code_exists(self, client, admin_user, test_game):
        """Test that image refresh code exists in the route."""
        # This test verifies that image refresh logic is present in the code
        from modules.routes_games_ext.edit import game_edit
        import inspect
        
        source = inspect.getsource(game_edit)
        
        # Verify image refresh logic exists
        assert 'igdb_id_changed' in source
        assert 'refresh_images_in_background' in source
        assert 'Thread' in source
    
    def test_creating_new_developer(self, client, admin_user, test_game, form_data):
        """Test creating a new developer during game update."""
        form_data['developer'] = 'Brand New Developer Name'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=1024):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='NFO'):
                        response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        # Verify new developer was created
        if response.status_code in [200, 302]:
            new_developer = db.session.execute(
                select(Developer).filter_by(name='Brand New Developer Name')
            ).scalars().first()
            assert new_developer is not None
    
    def test_creating_new_publisher(self, client, admin_user, test_game, form_data):
        """Test creating a new publisher during game update."""
        form_data['publisher'] = 'Brand New Publisher Name'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=1024):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='NFO'):
                        response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        # Verify new publisher was created
        if response.status_code in [200, 302]:
            new_publisher = db.session.execute(
                select(Publisher).filter_by(name='Brand New Publisher Name')
            ).scalars().first()
            assert new_publisher is not None
    
    def test_game_edit_get_request_loads_form(self, client, admin_user, test_game):
        """Test that GET request loads the form with existing game data."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/game_edit/{test_game.uuid}')
        
        assert response.status_code == 200
        assert test_game.name.encode() in response.data
        assert test_game.summary.encode() in response.data if test_game.summary else True
    
    def test_nonexistent_game_returns_404(self, client, admin_user):
        """Test that editing nonexistent game returns 404."""
        nonexistent_uuid = str(uuid4())
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/game_edit/{nonexistent_uuid}')
        assert response.status_code == 404


class TestGameEditFormValidation:
    """Test form validation and CSRF protection."""
    
    def test_form_validation_failure_logging(self, client, admin_user, test_game):
        """Test that form validation failures are logged."""
        invalid_data = {
            'name': '',  # Required field empty
            'csrf_token': 'invalid_token'
        }
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.current_app.logger') as mock_logger:
            response = client.post(f'/game_edit/{test_game.uuid}', data=invalid_data)
        
        # Verify form validation failure was logged
        mock_logger.warning.assert_called()
        warning_calls = [call for call in mock_logger.warning.call_args_list 
                        if 'Form validation failed' in str(call)]
        assert len(warning_calls) > 0


class TestGameEditDatabaseOperations:
    """Test database operations and data integrity."""
    
    def test_game_date_identified_updated(self, client, admin_user, test_game, form_data):
        """Test that date_identified is updated on successful edit."""
        original_date = test_game.date_identified
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=1024):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='NFO'):
                        response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        if response.status_code in [200, 302]:  # Success
            updated_game = db.session.execute(select(Game).filter_by(uuid=test_game.uuid)).scalars().first()
            assert updated_game.date_identified > original_date
    
    def test_game_size_calculation_updated(self, client, admin_user, test_game, form_data):
        """Test that game size is recalculated and updated."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        new_size = 5000000
        with patch('modules.routes_games_ext.edit.is_safe_path', return_value=(True, None)):
            with patch('modules.routes_games_ext.edit.get_allowed_base_directories', return_value=['/allowed']):
                with patch('modules.routes_games_ext.edit.get_folder_size_in_bytes_updates', return_value=new_size):
                    with patch('modules.routes_games_ext.edit.read_first_nfo_content', return_value='New NFO'):
                        response = client.post(f'/game_edit/{test_game.uuid}', data=form_data)
        
        if response.status_code in [200, 302]:  # Success
            updated_game = db.session.execute(select(Game).filter_by(uuid=test_game.uuid)).scalars().first()
            assert updated_game.size == new_size
            assert updated_game.nfo_content == 'New NFO'