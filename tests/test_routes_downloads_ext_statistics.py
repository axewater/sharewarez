import pytest
import json
from flask import url_for
from unittest.mock import patch, MagicMock
from modules.models import User, DownloadRequest, Game, Library, InviteToken, user_favorites
from modules.platform import LibraryPlatform
from modules import db
from uuid import uuid4
from datetime import datetime, timezone, timedelta


@pytest.fixture
def admin_user(db_session):
    """Create an admin user."""
    admin_uuid = str(uuid4())
    unique_id = str(uuid4())[:8]
    admin = User(
        user_id=admin_uuid,
        name=f'TestAdmin_{unique_id}',
        email=f'admin_{unique_id}@test.com',
        role='admin',
        is_email_verified=True
    )
    admin.set_password('testpass123')
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture
def regular_user(db_session):
    """Create a regular user."""
    user_uuid = str(uuid4())
    unique_id = str(uuid4())[:8]
    user = User(
        user_id=user_uuid,
        name=f'TestUser_{unique_id}',
        email=f'user_{unique_id}@test.com',
        role='user',
        is_email_verified=True
    )
    user.set_password('testpass123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_library(db_session):
    """Create a test library."""
    library = Library(
        name='Test Library',
        platform=LibraryPlatform.PCWIN
    )
    db_session.add(library)
    db_session.commit()
    return library


@pytest.fixture
def test_game(db_session, test_library):
    """Create a test game."""
    game = Game(
        name='Test Game',
        library_uuid=test_library.uuid
    )
    db_session.add(game)
    db_session.commit()
    return game


@pytest.fixture
def sample_statistics_data():
    """Mock statistics data for testing."""
    return {
        'users_with_invites': {
            'labels': ['Admin User', 'Power User'],
            'data': [5, 2]
        },
        'downloads_per_user': {
            'labels': ['User1', 'User2', 'User3'],
            'data': [10, 8, 6]
        },
        'top_downloaders': {
            'labels': ['User1', 'User2', 'User3'],
            'data': [10, 8, 6]
        },
        'top_collectors': {
            'labels': ['Collector1', 'Collector2'],
            'data': [25, 18]
        },
        'top_games': {
            'labels': ['Game A', 'Game B', 'Game C'],
            'data': [50, 35, 22]
        },
        'download_trends': {
            'labels': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'data': [12, 15, 8]
        }
    }


class TestStatisticsRoutes:
    """Test statistics routes in downloads extension."""

    def test_statistics_page_unauthenticated(self, client):
        """Test unauthenticated access to statistics page."""
        response = client.get('/admin/statistics')
        assert response.status_code == 302  # Redirect to login
        assert '/login' in response.location

    def test_statistics_data_unauthenticated(self, client):
        """Test unauthenticated access to statistics data endpoint."""
        response = client.get('/admin/statistics/data')
        assert response.status_code == 302  # Redirect to login
        assert '/login' in response.location

    def test_statistics_page_regular_user(self, client, regular_user):
        """Test regular user access to statistics page."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/statistics')
        assert response.status_code == 302  # Redirect to login (access denied)
        assert '/login' in response.location

    def test_statistics_data_regular_user(self, client, regular_user):
        """Test regular user access to statistics data endpoint."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/statistics/data')
        assert response.status_code == 302  # Redirect to login (access denied)
        assert '/login' in response.location

    def test_statistics_page_admin_user(self, client, admin_user):
        """Test admin user access to statistics page."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/statistics')
        assert response.status_code == 200
        assert b'statistics' in response.data or b'Statistics' in response.data

    @patch('modules.routes_downloads_ext.statistics.get_download_statistics')
    def test_statistics_data_admin_user(self, mock_stats, client, admin_user, sample_statistics_data):
        """Test admin user access to statistics data endpoint."""
        mock_stats.return_value = sample_statistics_data
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/statistics/data')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        data = json.loads(response.data)
        assert 'users_with_invites' in data
        assert 'downloads_per_user' in data
        assert 'top_downloaders' in data
        assert 'top_collectors' in data
        assert 'top_games' in data
        assert 'download_trends' in data

    @patch('modules.routes_downloads_ext.statistics.get_download_statistics')
    def test_statistics_data_structure(self, mock_stats, client, admin_user, sample_statistics_data):
        """Test the structure of statistics data response."""
        mock_stats.return_value = sample_statistics_data
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/statistics/data')
        data = json.loads(response.data)
        
        # Verify each section has labels and data
        for section_name in ['users_with_invites', 'downloads_per_user', 'top_downloaders', 
                            'top_collectors', 'top_games', 'download_trends']:
            assert section_name in data
            assert 'labels' in data[section_name]
            assert 'data' in data[section_name]
            assert isinstance(data[section_name]['labels'], list)
            assert isinstance(data[section_name]['data'], list)

    @patch('modules.routes_downloads_ext.statistics.get_download_statistics')
    def test_statistics_data_empty_database(self, mock_stats, client, admin_user):
        """Test statistics data with empty database."""
        empty_stats = {
            'users_with_invites': {'labels': [], 'data': []},
            'downloads_per_user': {'labels': [], 'data': []},
            'top_downloaders': {'labels': [], 'data': []},
            'top_collectors': {'labels': [], 'data': []},
            'top_games': {'labels': [], 'data': []},
            'download_trends': {'labels': [], 'data': []}
        }
        mock_stats.return_value = empty_stats
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/statistics/data')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        for section in data.values():
            assert section['labels'] == []
            assert section['data'] == []


class TestStatisticsIntegration:
    """Integration tests with real database data."""

    def test_statistics_with_sample_data(self, client, admin_user, regular_user, test_game, db_session):
        """Test statistics with actual database records."""
        # Create sample download requests
        download1 = DownloadRequest(
            user_id=regular_user.id,
            game_uuid=test_game.uuid,
            request_time=datetime.now(timezone.utc),
            status='completed'
        )
        download2 = DownloadRequest(
            user_id=admin_user.id,
            game_uuid=test_game.uuid,
            request_time=datetime.now(timezone.utc) - timedelta(days=1),
            status='completed'
        )
        
        db_session.add(download1)
        db_session.add(download2)
        
        # Create sample invite token
        invite = InviteToken(
            creator_user_id=admin_user.user_id,
            token='test-token',
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(invite)
        
        # Create favorite relationship
        favorite_stmt = user_favorites.insert().values(
            user_id=regular_user.id,
            game_uuid=test_game.uuid
        )
        db_session.execute(favorite_stmt)
        
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/statistics/data')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        
        # Verify we have some data (not empty)
        assert len(data['downloads_per_user']['labels']) > 0
        assert len(data['top_games']['labels']) > 0
        assert len(data['users_with_invites']['labels']) > 0
        assert len(data['top_collectors']['labels']) > 0
        
        # Verify data consistency
        for section in data.values():
            assert len(section['labels']) == len(section['data'])

    @patch('modules.routes_downloads_ext.statistics.get_download_statistics')
    def test_statistics_error_handling(self, mock_stats, client, admin_user):
        """Test error handling when statistics function fails."""
        mock_stats.side_effect = Exception("Database error")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Should handle the exception gracefully (it propagates up)
        with pytest.raises(Exception, match="Database error"):
            response = client.get('/admin/statistics/data')