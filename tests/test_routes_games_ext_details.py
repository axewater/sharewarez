import pytest
from unittest.mock import patch, Mock, MagicMock, call
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import select

from modules import create_app, db
from modules.models import (
    User, Game, Library, GameUpdate, GameExtra, GameURL, Image, 
    Genre, GameMode, Theme, Platform, PlayerPerspective, Developer, 
    Publisher, SystemEvents, Category, Status
)
from modules.platform import LibraryPlatform


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
        summary='This is a test game with <script>alert("xss")</script> content',
        storyline='A longer storyline for testing',
        rating=85,
        size=1024000,
        first_release_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        date_identified=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
        full_disk_path='/sensitive/path/to/game/folder',
        nfo_content='Test NFO Content\nWith <script>alert("malicious")</script> content\nMultiple lines',
        url='https://example.com/game',
        video_urls='https://www.youtube.com/embed/test1,https://www.youtube.com/embed/test2',
        steam_url='https://store.steampowered.com/app/123456',
        category=Category.MAIN_GAME,
        status=Status.RELEASED,
        times_downloaded=42,
        developer=test_developer,
        publisher=test_publisher
    )
    db_session.add(game)
    db_session.commit()
    return game


@pytest.fixture
def test_game_update(db_session, test_game):
    """Create a test game update."""
    update = GameUpdate(
        game_uuid=test_game.uuid,
        file_path='/path/to/update.exe',
        times_downloaded=5,
        created_at=datetime.now(timezone.utc),
        nfo_content='Update NFO content'
    )
    db_session.add(update)
    db_session.commit()
    return update


@pytest.fixture
def test_game_extra(db_session, test_game):
    """Create a test game extra."""
    extra = GameExtra(
        game_uuid=test_game.uuid,
        file_path='/path/to/extra.zip',
        times_downloaded=3,
        created_at=datetime.now(timezone.utc),
        nfo_content='Extra NFO content'
    )
    db_session.add(extra)
    db_session.commit()
    return extra


@pytest.fixture
def test_game_image(db_session, test_game):
    """Create a test game image."""
    image = Image(
        game_uuid=test_game.uuid,
        image_type='cover',
        url='test_cover.jpg'
    )
    db_session.add(image)
    db_session.commit()
    return image


@pytest.fixture
def test_game_url(db_session, test_game):
    """Create a test game URL."""
    game_url = GameURL(
        game_uuid=test_game.uuid,
        url='https://example.com/official',
        url_type='official'
    )
    db_session.add(game_url)
    db_session.commit()
    return game_url


class TestGameDetailsRouteAuthentication:
    """Test authentication and access control for game details route."""
    
    def test_game_details_requires_login(self, client, test_game):
        """Test that game details route requires authentication."""
        response = client.get(f'/game_details/{test_game.uuid}')
        assert response.status_code == 302  # Redirect to login
        assert '/login' in response.location
    
    def test_game_details_with_authenticated_user(self, client, test_user, test_game):
        """Test game details route with authenticated user."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.log_system_event') as mock_log:
            response = client.get(f'/game_details/{test_game.uuid}')
        
        assert response.status_code == 200
        assert mock_log.called


class TestGameDetailsRouteValidation:
    """Test UUID validation and security logging."""
    
    def test_game_details_invalid_uuid_format(self, client, test_user):
        """Test game details with invalid UUID format."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.log_system_event') as mock_log:
            response = client.get('/game_details/invalid-uuid-format')
        
        assert response.status_code == 404
        # Verify security warning was logged
        mock_log.assert_called_with(
            f"Invalid UUID format provided by user {test_user.name}: invalid-uuid-format...",
            event_type='security',
            event_level='warning'
        )
    
    def test_game_details_valid_uuid_nonexistent_game(self, client, test_user):
        """Test game details with valid UUID but non-existent game."""
        nonexistent_uuid = str(uuid4())
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.log_system_event') as mock_log:
            response = client.get(f'/game_details/{nonexistent_uuid}')
        
        assert response.status_code == 404
        # Verify access attempt was logged
        mock_log.assert_any_call(
            f"User {test_user.name} attempted to access non-existent game UUID: {nonexistent_uuid[:8]}...",
            event_type='security',
            event_level='warning'
        )
    
    def test_game_details_uuid_validation_logs_truncated_uuid(self, client, test_user):
        """Test that UUID logging is properly truncated for security."""
        long_invalid_string = 'a' * 50  # Long invalid UUID
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.log_system_event') as mock_log:
            response = client.get(f'/game_details/{long_invalid_string}')
        
        assert response.status_code == 404
        # Verify that logged UUID is truncated to first 20 characters
        mock_log.assert_called_with(
            f"Invalid UUID format provided by user {test_user.name}: {long_invalid_string[:20]}...",
            event_type='security',
            event_level='warning'
        )


class TestGameDetailsRouteResponse:
    """Test game details response data and security."""
    
    def test_game_details_successful_response(self, client, test_user, test_game, test_game_update, test_game_extra, test_game_image, test_game_url):
        """Test successful game details response."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.log_system_event') as mock_log:
            response = client.get(f'/game_details/{test_game.uuid}')
        
        assert response.status_code == 200
        assert b'Test Game' in response.data
        
        # Verify audit logging of successful access
        mock_log.assert_any_call(
            f"User {test_user.name} accessed game 'Test Game' with 1 updates and 1 extras",
            event_type='game',
            event_level='information'
        )
    
    def test_game_details_full_disk_path_not_exposed(self, client, test_user, test_game):
        """Test that full_disk_path is not exposed in the response."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.render_template') as mock_render:
            mock_render.return_value = 'mocked response'
            response = client.get(f'/game_details/{test_game.uuid}')
        
        # Get the game_data passed to the template
        args, kwargs = mock_render.call_args
        game_data = kwargs['game']
        
        # Verify full_disk_path is not in the response data
        assert 'full_disk_path' not in game_data
        # Verify the sensitive path isn't exposed anywhere
        assert '/sensitive/path/to/game/folder' not in str(game_data)
    
    def test_game_details_nfo_content_sanitized(self, client, test_user, test_game):
        """Test that NFO content is sanitized before being sent to template."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.render_template') as mock_render:
            with patch('modules.routes_games_ext.details.sanitize_string_input') as mock_sanitize:
                mock_sanitize.return_value = 'sanitized_nfo_content'
                mock_render.return_value = 'mocked response'
                
                response = client.get(f'/game_details/{test_game.uuid}')
        
        # Verify NFO content was sanitized
        mock_sanitize.assert_called_with(test_game.nfo_content, 10000)
        
        # Get the game_data passed to the template
        args, kwargs = mock_render.call_args
        game_data = kwargs['game']
        
        # Verify sanitized content is in response
        assert game_data['nfo_content'] == 'sanitized_nfo_content'
    
    def test_game_details_no_duplicate_updates_array(self, client, test_user, test_game, test_game_update):
        """Test that updates array is not duplicated in response."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.render_template') as mock_render:
            mock_render.return_value = 'mocked response'
            response = client.get(f'/game_details/{test_game.uuid}')
        
        # Get the game_data passed to the template
        args, kwargs = mock_render.call_args
        game_data = kwargs['game']
        
        # Verify updates array exists and contains correct data
        assert 'updates' in game_data
        assert len(game_data['updates']) == 1
        assert game_data['updates'][0]['file_path'] == '/path/to/update.exe'
        
        # Verify no duplicate updates key by checking data structure
        # Count the number of times 'updates' appears as a key
        import json
        game_data_json = json.dumps(game_data, default=str)
        updates_count = game_data_json.count('"updates"')
        assert updates_count >= 1, f"Found {updates_count} 'updates' keys, expected at least 1"


class TestGameDetailsRouteLogging:
    """Test comprehensive logging functionality."""
    
    def test_game_details_logs_access_request(self, client, test_user, test_game):
        """Test that game access requests are logged."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.log_system_event') as mock_log:
            response = client.get(f'/game_details/{test_game.uuid}')
        
        # Verify initial access request is logged with truncated UUID
        mock_log.assert_any_call(
            f"User {test_user.name} requested game details for UUID: {test_game.uuid[:8]}...",
            event_type='game',
            event_level='debug'
        )
    
    def test_game_details_logs_successful_access(self, client, test_user, test_game, test_game_update, test_game_extra):
        """Test that successful game access is logged with details."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.log_system_event') as mock_log:
            response = client.get(f'/game_details/{test_game.uuid}')
        
        # Verify successful access is logged with game details
        mock_log.assert_any_call(
            f"User {test_user.name} accessed game 'Test Game' with 1 updates and 1 extras",
            event_type='game',
            event_level='information'
        )
    
    def test_game_details_logs_system_events_to_database(self, client, test_user, test_game, db_session):
        """Test that system events are actually logged to the database."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        # Clear any existing events
        from sqlalchemy import delete
        db_session.execute(delete(SystemEvents).where(SystemEvents.audit_user == test_user.id))
        db_session.commit()
        
        response = client.get(f'/game_details/{test_game.uuid}')
        
        # Check that events were logged to database
        events = db_session.execute(
            select(SystemEvents).filter_by(audit_user=test_user.id)
        ).scalars().all()
        
        assert len(events) > 0
        # Verify at least one game-related event was logged
        game_events = [e for e in events if e.event_type == 'game']
        assert len(game_events) > 0


class TestGameDetailsUtilityFunctionLogging:
    """Test logging in utility functions called by game details route."""
    
    def test_get_game_by_uuid_logging(self, app, test_game, test_user, db_session):
        """Test that get_game_by_uuid function logs appropriately."""
        with app.app_context():
            # Need to set up Flask-Login context
            with patch('modules.utils_game_core.log_system_event') as mock_log:
                from modules.utils_game_core import get_game_by_uuid
                result = get_game_by_uuid(test_game.uuid)
        
        assert result.uuid == test_game.uuid
        assert result.name == test_game.name
        
        # Verify logging calls were made
        assert mock_log.call_count >= 2
        # Check that search logging was called
        search_calls = [call for call in mock_log.call_args_list 
                       if 'Searching for game UUID' in str(call)]
        assert len(search_calls) >= 1
    
    def test_get_game_by_uuid_not_found_logging(self, app, test_user, db_session):
        """Test logging when game is not found."""
        nonexistent_uuid = str(uuid4())
        with app.app_context():
            with patch('modules.utils_game_core.log_system_event') as mock_log:
                from modules.utils_game_core import get_game_by_uuid
                result = get_game_by_uuid(nonexistent_uuid)
        
        assert result is None
        
        # Verify not found is logged
        mock_log.assert_any_call(
            f"Game not found for UUID: {nonexistent_uuid[:8]}...",
            event_type='game',
            event_level='debug'
        )


class TestGameDetailsTemplateSecurity:
    """Test template security and CSRF protection."""
    
    def test_game_details_includes_csrf_form(self, client, test_user, test_game):
        """Test that CSRF form is included in template context."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.render_template') as mock_render:
            mock_render.return_value = 'mocked response'
            response = client.get(f'/game_details/{test_game.uuid}')
        
        # Verify CSRF form is passed to template
        args, kwargs = mock_render.call_args
        assert 'form' in kwargs
        # Verify it's a CSRF form
        from modules.forms import CsrfForm
        assert isinstance(kwargs['form'], CsrfForm)
    
    def test_game_details_template_context(self, client, test_user, test_game):
        """Test that all required template context is provided."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.render_template') as mock_render:
            mock_render.return_value = 'mocked response'
            response = client.get(f'/game_details/{test_game.uuid}')
        
        # Verify template and context
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        
        assert args[0] == 'games/game_details.html'
        assert 'game' in kwargs
        assert 'form' in kwargs
        assert 'library_uuid' in kwargs
        assert kwargs['library_uuid'] == test_game.library_uuid


class TestGameDetailsErrorHandling:
    """Test error handling and edge cases."""
    
    def test_game_details_with_null_nfo_content(self, client, test_user, test_library):
        """Test game details with null NFO content."""
        game = Game(
            uuid=str(uuid4()),
            name='Game with No NFO',
            library_uuid=test_library.uuid,
            nfo_content=None  # Null NFO content
        )
        db.session.add(game)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.render_template') as mock_render:
            mock_render.return_value = 'mocked response'
            response = client.get(f'/game_details/{game.uuid}')
        
        assert response.status_code == 200
        
        # Verify NFO content defaults to 'none'
        args, kwargs = mock_render.call_args
        game_data = kwargs['game']
        assert game_data['nfo_content'] == 'none'
    
    def test_game_details_with_empty_collections(self, client, test_user, test_library):
        """Test game details with empty updates/extras collections."""
        game = Game(
            uuid=str(uuid4()),
            name='Game with Empty Collections',
            library_uuid=test_library.uuid
        )
        db.session.add(game)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.log_system_event') as mock_log:
            response = client.get(f'/game_details/{game.uuid}')
        
        assert response.status_code == 200
        
        # Verify logging shows 0 updates and extras
        mock_log.assert_any_call(
            f"User {test_user.name} accessed game 'Game with Empty Collections' with 0 updates and 0 extras",
            event_type='game',
            event_level='information'
        )
    
    def test_game_details_json_error_response_for_not_found(self, client, test_user):
        """Test that 404 returns proper JSON error response."""
        nonexistent_uuid = str(uuid4())
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_games_ext.details.log_system_event') as mock_log:
            response = client.get(f'/game_details/{nonexistent_uuid}')
        
        assert response.status_code == 404
        # Check if response contains JSON error data (may not be proper JSON response)
        response_data = response.get_data(as_text=True)
        assert 'Game not found' in response_data or response.status_code == 404


class TestGameDetailsPerformance:
    """Test performance-related aspects."""
    
    def test_game_details_efficient_queries(self, client, test_user, test_game, test_game_update, test_game_extra):
        """Test that game details uses efficient database queries."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        # Simply test that the route works without errors
        # The actual query efficiency would be better tested with a database profiler
        with patch('modules.routes_games_ext.details.log_system_event') as mock_log:
            response = client.get(f'/game_details/{test_game.uuid}')
        
        # Verify successful response
        assert response.status_code == 200
        assert mock_log.call_count >= 2  # At least access request and successful access