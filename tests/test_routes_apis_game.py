"""
Unit tests for modules.routes_apis.game

Tests the game API endpoints including search, screenshots, game movement,
and IGDB ID generation functionality.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from uuid import uuid4

from modules.models import User, Game, Library, Image, LibraryPlatform


def safe_cleanup_database(db_session):
    """Safely clean up database records respecting foreign key constraints."""
    from sqlalchemy import delete
    from modules.models import SystemEvents
    
    # Clean up in order of dependencies
    db_session.execute(delete(SystemEvents))
    db_session.execute(delete(Image))
    db_session.execute(delete(Game))
    db_session.execute(delete(Library))
    db_session.execute(delete(User))
    db_session.commit()


@pytest.fixture
def regular_user(db_session):
    """Create a test regular user."""
    user_uuid = str(uuid4())
    user = User(
        name=f'regularuser_{user_uuid[:8]}',
        email=f'regular_{user_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='user',
        user_id=user_uuid,
        avatarpath='newstyle/avatar_default.jpg',
        invite_quota=5
    )
    user.set_password('regularpassword123')
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
def target_library(db_session):
    """Create a target library for move operations."""
    library = Library(
        name='Target Library', 
        platform=LibraryPlatform.PCWIN
    )
    db_session.add(library)
    db_session.commit()
    return library


@pytest.fixture
def sample_games(db_session, sample_library):
    """Create sample games for testing."""
    # Clear existing games first
    from sqlalchemy import delete
    db_session.execute(delete(Game))
    db_session.commit()
    
    games = [
        Game(
            name='Test Action Game',
            full_disk_path='/tmp/test_action_game',
            library_uuid=sample_library.uuid,
            igdb_id=100001
        ),
        Game(
            name='Test Adventure Game',
            full_disk_path='/tmp/test_adventure_game',
            library_uuid=sample_library.uuid,
            igdb_id=100002
        ),
        Game(
            name='Test RPG Game',
            full_disk_path='/tmp/test_rpg_game',
            library_uuid=sample_library.uuid,
            igdb_id=2000000425  # Custom IGDB ID
        )
    ]
    for game in games:
        db_session.add(game)
    db_session.commit()
    
    yield games
    
    # Cleanup
    db_session.execute(delete(Game))
    db_session.commit()


@pytest.fixture
def sample_images(db_session, sample_games):
    """Create sample images for testing."""
    # Clear existing images first
    from sqlalchemy import delete
    db_session.execute(delete(Image))
    db_session.commit()
    
    images = [
        Image(
            game_uuid=sample_games[0].uuid,
            url='screenshot1.jpg',
            image_type='screenshot'
        ),
        Image(
            game_uuid=sample_games[0].uuid,
            url='screenshot2.jpg',
            image_type='screenshot'
        ),
        Image(
            game_uuid=sample_games[0].uuid,
            url='cover.jpg',
            image_type='cover'
        ),
        Image(
            game_uuid=sample_games[1].uuid,
            url='screenshot3.jpg',
            image_type='screenshot'
        )
    ]
    for image in images:
        db_session.add(image)
    db_session.commit()
    
    yield images
    
    # Cleanup
    db_session.execute(delete(Image))
    db_session.commit()


class TestGameSearchAPI:
    """Test the search API endpoint."""
    
    def test_search_requires_login(self, client):
        """Test that /api/search requires user login."""
        response = client.get('/api/search?query=test')
        assert response.status_code == 302  # Redirect to login
    
    def test_search_success_with_results(self, client, regular_user, sample_games):
        """Test successful search with results."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/search?query=Action')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['name'] == 'Test Action Game'
        assert 'id' in data[0]
        assert 'uuid' in data[0]
        assert 'name' in data[0]
    
    def test_search_success_multiple_results(self, client, regular_user, sample_games):
        """Test search returning multiple results."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/search?query=Test')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 3
        
        # Check all games are returned
        game_names = [item['name'] for item in data]
        assert 'Test Action Game' in game_names
        assert 'Test Adventure Game' in game_names
        assert 'Test RPG Game' in game_names
    
    def test_search_no_results(self, client, regular_user, sample_games):
        """Test search with no matching results."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/search?query=NonexistentGame')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_search_empty_query(self, client, regular_user):
        """Test search with empty query."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/search?query=')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_search_no_query_parameter(self, client, regular_user):
        """Test search without query parameter."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/search')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_search_query_too_long(self, client, regular_user):
        """Test search with query that exceeds length limit."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        long_query = 'a' * 101  # Exceeds 100 character limit
        response = client.get(f'/api/search?query={long_query}')
        assert response.status_code == 400
        
        data = response.get_json()
        assert 'error' in data
        assert 'Search term too long' in data['error']
    
    def test_search_case_insensitive(self, client, regular_user, sample_games):
        """Test that search is case insensitive."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/search?query=action')
        assert response.status_code == 200
        
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'Test Action Game'


class TestGameScreenshotsAPI:
    """Test the game screenshots API endpoint."""
    
    def test_screenshots_requires_login(self, client, sample_games):
        """Test that /api/game_screenshots requires user login."""
        response = client.get(f'/api/game_screenshots/{sample_games[0].uuid}')
        assert response.status_code == 302  # Redirect to login
    
    def test_screenshots_success_with_images(self, client, regular_user, sample_games, sample_images):
        """Test successful retrieval of game screenshots."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/api/game_screenshots/{sample_games[0].uuid}')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 2  # Only screenshots, not cover
        
        # Check that URLs are properly formatted
        for url in data:
            assert isinstance(url, str)
            assert '/static/library/images/' in url
            assert url.endswith('.jpg')
    
    def test_screenshots_no_screenshots(self, client, regular_user, sample_games, sample_images):
        """Test screenshots endpoint for game with no screenshots."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # Use game[2] which has no images
        response = client.get(f'/api/game_screenshots/{sample_games[2].uuid}')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_screenshots_nonexistent_game(self, client, regular_user):
        """Test screenshots endpoint for nonexistent game."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        fake_uuid = str(uuid4())
        response = client.get(f'/api/game_screenshots/{fake_uuid}')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestMoveGameToLibraryAPI:
    """Test the move game to library API endpoint."""
    
    def test_move_game_requires_login(self, client):
        """Test that /api/move_game_to_library requires user login."""
        response = client.post('/api/move_game_to_library', json={})
        assert response.status_code == 302  # Redirect to login
    
    def test_move_game_success(self, client, regular_user, sample_games, target_library):
        """Test successful game move operation."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        game_uuid = str(sample_games[0].uuid)
        target_library_uuid = str(target_library.uuid)
        
        response = client.post('/api/move_game_to_library', json={
            'game_uuid': game_uuid,
            'target_library_uuid': target_library_uuid
        })
        
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert 'moved to Target Library' in data['message']
    
    def test_move_game_missing_parameters(self, client, regular_user):
        """Test move game with missing parameters."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # Missing target_library_uuid
        response = client.post('/api/move_game_to_library', json={
            'game_uuid': str(uuid4())
        })
        
        assert response.status_code == 400
        
        data = response.get_json()
        assert data['success'] is False
        assert 'Missing required parameters' in data['message']
    
    def test_move_game_invalid_json(self, client, regular_user):
        """Test move game with invalid JSON."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/move_game_to_library', 
                             data='invalid json',
                             content_type='application/json')
        
        assert response.status_code == 500
        
        data = response.get_json()
        assert data['success'] is False
    
    def test_move_game_nonexistent_game(self, client, regular_user, target_library):
        """Test move operation with nonexistent game."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        fake_game_uuid = str(uuid4())
        target_library_uuid = str(target_library.uuid)
        
        response = client.post('/api/move_game_to_library', json={
            'game_uuid': fake_game_uuid,
            'target_library_uuid': target_library_uuid
        })
        
        assert response.status_code == 404
        
        data = response.get_json()
        assert data['success'] is False
        assert 'Game or target library not found' in data['message']
    
    def test_move_game_nonexistent_library(self, client, regular_user, sample_games):
        """Test move operation with nonexistent target library."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        game_uuid = str(sample_games[0].uuid)
        fake_library_uuid = str(uuid4())
        
        response = client.post('/api/move_game_to_library', json={
            'game_uuid': game_uuid,
            'target_library_uuid': fake_library_uuid
        })
        
        assert response.status_code == 404
        
        data = response.get_json()
        assert data['success'] is False
        assert 'Game or target library not found' in data['message']
    
    @patch('modules.routes_apis.game.log_system_event')
    def test_move_game_logging(self, mock_log, client, regular_user, sample_games, target_library):
        """Test that move operation is properly logged."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        game_uuid = str(sample_games[0].uuid)
        target_library_uuid = str(target_library.uuid)
        
        response = client.post('/api/move_game_to_library', json={
            'game_uuid': game_uuid,
            'target_library_uuid': target_library_uuid
        })
        
        assert response.status_code == 200
        
        # Verify logging occurred
        mock_log.assert_called_once()
        log_call = mock_log.call_args[0][0]
        assert 'moved to library Target Library' in log_call
        assert regular_user.name in log_call


class TestGetNextCustomIGDBIdAPI:
    """Test the get next custom IGDB ID API endpoint."""
    
    def test_next_igdb_id_requires_login(self, client):
        """Test that /api/get_next_custom_igdb_id requires user login."""
        response = client.get('/api/get_next_custom_igdb_id')
        assert response.status_code == 302  # Redirect to login
    
    def test_next_igdb_id_no_existing_custom_ids(self, client, regular_user, db_session):
        """Test next IGDB ID when no custom IDs exist."""
        # Clear any existing games with custom IDs
        from sqlalchemy import delete
        db_session.execute(delete(Game).filter(Game.igdb_id >= 2000000420))
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/get_next_custom_igdb_id')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'next_id' in data
        assert data['next_id'] == 2000000420  # Base custom ID
    
    def test_next_igdb_id_with_existing_custom_ids(self, client, regular_user, sample_games):
        """Test next IGDB ID when custom IDs already exist."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/get_next_custom_igdb_id')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'next_id' in data
        # Should return next available after the highest (2000000425 + 1)
        assert data['next_id'] == 2000000426
    
    @patch('modules.routes_apis.game.db.session.execute')
    def test_next_igdb_id_database_error(self, mock_execute, client, regular_user):
        """Test error handling in next IGDB ID endpoint."""
        mock_execute.side_effect = Exception("Database error")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/get_next_custom_igdb_id')
        assert response.status_code == 500
        
        data = response.get_json()
        assert 'error' in data


class TestGameAPIResponseFormats:
    """Test response formats and data structures for game APIs."""
    
    def test_search_response_structure(self, client, regular_user, sample_games):
        """Test that search responses have correct structure."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/search?query=Test')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        data = response.get_json()
        assert isinstance(data, list)
        
        for item in data:
            assert isinstance(item, dict)
            assert 'id' in item
            assert 'uuid' in item
            assert 'name' in item
            assert isinstance(item['id'], int)
            assert isinstance(item['uuid'], str)
            assert isinstance(item['name'], str)
    
    def test_screenshots_response_structure(self, client, regular_user, sample_games, sample_images):
        """Test that screenshots responses have correct structure."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/api/game_screenshots/{sample_games[0].uuid}')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        data = response.get_json()
        assert isinstance(data, list)
        
        for url in data:
            assert isinstance(url, str)
    
    def test_move_game_success_response_structure(self, client, regular_user, sample_games, target_library):
        """Test that move game success responses have correct structure."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/move_game_to_library', json={
            'game_uuid': str(sample_games[0].uuid),
            'target_library_uuid': str(target_library.uuid)
        })
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        data = response.get_json()
        assert isinstance(data, dict)
        assert 'success' in data
        assert 'message' in data
        assert isinstance(data['success'], bool)
        assert isinstance(data['message'], str)
        assert data['success'] is True
    
    def test_move_game_error_response_structure(self, client, regular_user):
        """Test that move game error responses have correct structure."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/move_game_to_library', json={
            'game_uuid': 'invalid'  # Missing target_library_uuid
        })
        
        assert response.status_code == 400
        assert response.content_type == 'application/json'
        
        data = response.get_json()
        assert isinstance(data, dict)
        assert 'success' in data
        assert 'message' in data
        assert isinstance(data['success'], bool)
        assert isinstance(data['message'], str)
        assert data['success'] is False
    
    def test_next_igdb_id_response_structure(self, client, regular_user):
        """Test that next IGDB ID responses have correct structure."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/get_next_custom_igdb_id')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        data = response.get_json()
        assert isinstance(data, dict)
        assert 'next_id' in data
        assert isinstance(data['next_id'], int)