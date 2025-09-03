"""
Unit tests for modules.routes_apis.user

Tests the user API endpoints including current user role retrieval,
username checking, and favorite game management functionality.
"""

import pytest
import json
from uuid import uuid4

from modules.models import User, Game, Library, LibraryPlatform


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
def admin_user(db_session):
    """Create a test admin user."""
    user_uuid = str(uuid4())
    user = User(
        name=f'adminuser_{user_uuid[:8]}',
        email=f'admin_{user_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='admin',
        user_id=user_uuid,
        avatarpath='newstyle/avatar_default.jpg',
        invite_quota=10
    )
    user.set_password('adminpassword123')
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
def sample_game(db_session, sample_library):
    """Create a sample game for testing."""
    # Generate unique IGDB ID to avoid conflicts
    import random
    igdb_id = random.randint(200000, 299999)
    
    game = Game(
        name='Test Game',
        full_disk_path='/tmp/test_game',
        library_uuid=sample_library.uuid,
        igdb_id=igdb_id
    )
    db_session.add(game)
    db_session.commit()
    return game


class TestCurrentUserRoleEndpoint:
    """Test the /api/current_user_role endpoint."""
    
    def test_current_user_role_requires_login(self, client):
        """Test that current_user_role requires user login."""
        response = client.get('/api/current_user_role')
        assert response.status_code == 302  # Redirect to login
    
    def test_current_user_role_regular_user(self, client, regular_user):
        """Test that regular user gets correct role returned."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/current_user_role')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['role'] == 'user'
    
    def test_current_user_role_admin_user(self, client, admin_user):
        """Test that admin user gets correct role returned."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/current_user_role')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['role'] == 'admin'


class TestCheckUsernameEndpoint:
    """Test the /api/check_username endpoint."""
    
    def test_check_username_requires_login(self, client):
        """Test that check_username requires user login."""
        response = client.post('/api/check_username', 
                             json={'username': 'testuser'})
        assert response.status_code == 302  # Redirect to login
    
    def test_check_username_missing_parameter(self, client, regular_user):
        """Test check_username with missing username parameter."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/check_username', json={})
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error'] == 'Missing username parameter'
    
    def test_check_username_exists(self, client, regular_user):
        """Test check_username with existing username."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/check_username', 
                             json={'username': regular_user.name})
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['exists'] is True
    
    def test_check_username_not_exists(self, client, regular_user):
        """Test check_username with non-existing username."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/check_username', 
                             json={'username': 'nonexistentuser12345'})
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['exists'] is False
    
    def test_check_username_case_insensitive(self, client, regular_user):
        """Test check_username is case insensitive."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # Test uppercase version of existing username
        response = client.post('/api/check_username', 
                             json={'username': regular_user.name.upper()})
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['exists'] is True


class TestCheckFavoriteEndpoint:
    """Test the /api/check_favorite/<game_uuid> endpoint."""
    
    def test_check_favorite_requires_login(self, client, sample_game):
        """Test that check_favorite requires user login."""
        response = client.get(f'/api/check_favorite/{sample_game.uuid}')
        assert response.status_code == 302  # Redirect to login
    
    def test_check_favorite_game_not_found(self, client, regular_user):
        """Test check_favorite with non-existent game UUID."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        fake_uuid = str(uuid4())
        response = client.get(f'/api/check_favorite/{fake_uuid}')
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error'] == 'Game not found'
    
    def test_check_favorite_not_favorited(self, client, regular_user, sample_game):
        """Test check_favorite when game is not in user's favorites."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/api/check_favorite/{sample_game.uuid}')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['is_favorite'] is False
    
    def test_check_favorite_is_favorited(self, client, regular_user, sample_game, db_session):
        """Test check_favorite when game is in user's favorites."""
        # Add game to user's favorites
        regular_user.favorites.append(sample_game)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/api/check_favorite/{sample_game.uuid}')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['is_favorite'] is True


class TestToggleFavoriteEndpoint:
    """Test the /api/toggle_favorite/<game_uuid> endpoint."""
    
    def test_toggle_favorite_requires_login(self, client, sample_game):
        """Test that toggle_favorite requires user login."""
        response = client.post(f'/api/toggle_favorite/{sample_game.uuid}')
        assert response.status_code == 302  # Redirect to login
    
    def test_toggle_favorite_game_not_found(self, client, regular_user):
        """Test toggle_favorite with non-existent game UUID."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        fake_uuid = str(uuid4())
        response = client.post(f'/api/toggle_favorite/{fake_uuid}')
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error'] == 'Game not found'
    
    def test_toggle_favorite_add_to_favorites(self, client, regular_user, sample_game, db_session):
        """Test toggle_favorite adding a game to favorites."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # Ensure game is not in favorites initially
        assert sample_game not in regular_user.favorites
        
        response = client.post(f'/api/toggle_favorite/{sample_game.uuid}')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['is_favorite'] is True
        
        # Refresh user to check database changes
        db_session.refresh(regular_user)
        assert sample_game in regular_user.favorites
    
    def test_toggle_favorite_remove_from_favorites(self, client, regular_user, sample_game, db_session):
        """Test toggle_favorite removing a game from favorites."""
        # Add game to favorites first
        regular_user.favorites.append(sample_game)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # Ensure game is in favorites initially
        assert sample_game in regular_user.favorites
        
        response = client.post(f'/api/toggle_favorite/{sample_game.uuid}')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['is_favorite'] is False
        
        # Refresh user to check database changes
        db_session.refresh(regular_user)
        assert sample_game not in regular_user.favorites
    
    def test_toggle_favorite_multiple_toggles(self, client, regular_user, sample_game, db_session):
        """Test toggle_favorite behavior with multiple toggles."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # Initially not favorited
        assert sample_game not in regular_user.favorites
        
        # First toggle - add to favorites
        response = client.post(f'/api/toggle_favorite/{sample_game.uuid}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['is_favorite'] is True
        
        db_session.refresh(regular_user)
        assert sample_game in regular_user.favorites
        
        # Second toggle - remove from favorites
        response = client.post(f'/api/toggle_favorite/{sample_game.uuid}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['is_favorite'] is False
        
        db_session.refresh(regular_user)
        assert sample_game not in regular_user.favorites
        
        # Third toggle - add back to favorites
        response = client.post(f'/api/toggle_favorite/{sample_game.uuid}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['is_favorite'] is True
        
        db_session.refresh(regular_user)
        assert sample_game in regular_user.favorites