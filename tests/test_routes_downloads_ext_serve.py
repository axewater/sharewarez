import pytest
import json
from unittest.mock import patch
from uuid import uuid4

from modules.models import DownloadRequest, Game, User


def authenticate_user(client, user):
    """Helper function to authenticate a user in the test session."""
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True


@pytest.fixture
def authenticated_user(db_session):
    """Create and return an authenticated user."""
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
    """Create a test library for testing."""
    from modules.models import Library
    from modules.platform import LibraryPlatform
    library = Library(
        uuid=str(uuid4()),
        name='Test Library',
        platform=LibraryPlatform.PCWIN
    )
    db_session.add(library)
    db_session.commit()
    return library


@pytest.fixture
def test_game(db_session, test_library):
    """Create a test game for testing."""
    from datetime import datetime, timezone
    game = Game(
        uuid=str(uuid4()),
        name='Test Game',
        library_uuid=test_library.uuid,
        summary='A test game',
        rating=85,
        size=1024000,
        first_release_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        date_identified=datetime.now(timezone.utc),
        full_disk_path='/test/path/game'
    )
    db_session.add(game)
    db_session.commit()
    return game


@pytest.fixture
def sample_download_request(db_session, authenticated_user, test_game):
    """Create a sample download request for testing."""
    download_request = DownloadRequest(
        user_id=authenticated_user.id,
        game_uuid=test_game.uuid,
        status='available',
        download_size=1024,
        file_location='/test/path/game.zip',
        zip_file_path='/test/path/game.zip'
    )
    db_session.add(download_request)
    db_session.commit()
    return download_request


class TestDownloadZipRoute:
    """Test the Flask download_zip route (should always return error since ASGI handles downloads)."""

    def test_download_zip_requires_login(self, client):
        """Test that download route requires authentication."""
        response = client.get('/download_zip/1')
        assert response.status_code == 302
        assert '/login' in response.location

    @patch('modules.routes_downloads_ext.serve.log_system_event')
    def test_download_zip_returns_asgi_error(self, mock_log, client, authenticated_user, sample_download_request):
        """Test that Flask download route returns error since ASGI should handle downloads."""
        authenticate_user(client, authenticated_user)

        response = client.get(f'/download_zip/{sample_download_request.id}')

        # Flask route should return 500 since ASGI should handle this
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert response_data['error'] == 'Download route should be handled by ASGI'

        # Verify system logging for unexpected Flask route access
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert 'Flask download route reached unexpectedly' in call_args[0][0]
        assert call_args[1]['event_type'] == 'system'
        assert call_args[1]['event_level'] == 'warning'