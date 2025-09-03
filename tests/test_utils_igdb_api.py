import pytest
import time
import threading
from unittest.mock import patch, MagicMock

from modules import create_app, db
from modules.models import GlobalSettings
from modules.utils_igdb_api import (
    make_igdb_api_request,
    get_access_token,
    get_cover_thumbnail_url,
    get_cover_url,
    IGDBRateLimiter
)


def safe_cleanup_database(db_session):
    """Safely clean up database records respecting foreign key constraints.""" 
    from sqlalchemy import delete
    
    # Clean up GlobalSettings
    db_session.execute(delete(GlobalSettings))
    db_session.commit()


@pytest.fixture
def sample_global_settings(db_session):
    """Create global settings with IGDB credentials for testing."""
    safe_cleanup_database(db_session)
    settings = GlobalSettings(
        igdb_client_id='test_client_id',
        igdb_client_secret='test_client_secret'
    )
    db_session.add(settings)
    db_session.commit()  # Use commit to make it visible to global session
    return settings


@pytest.fixture
def mock_access_token():
    """Mock access token response."""
    return 'test_access_token_12345'


@pytest.fixture
def mock_cover_response():
    """Mock IGDB cover API response."""
    return [
        {
            'url': '//images.igdb.com/igdb/image/upload/t_thumb/test_cover.jpg'
        }
    ]


@pytest.fixture
def mock_cover_image_id_response():
    """Mock IGDB cover API response with image_id."""
    return [
        {
            'image_id': 'test_image_id_12345'
        }
    ]


class TestMakeIgdbApiRequest:
    """Tests for make_igdb_api_request function."""
    
    @patch('modules.utils_igdb_api.get_access_token')
    @patch('requests.post')
    def test_successful_api_request(self, mock_requests_post, mock_get_token, 
                                  db_session, sample_global_settings):
        """Test successful IGDB API request."""
        mock_get_token.return_value = 'test_token'
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': 'test_response'}
        mock_requests_post.return_value = mock_response
        
        result = make_igdb_api_request('https://api.igdb.com/v4/games', 'fields name;')
        
        assert result == {'data': 'test_response'}
        mock_get_token.assert_called_once_with('test_client_id', 'test_client_secret')
        mock_requests_post.assert_called_once_with(
            'https://api.igdb.com/v4/games',
            headers={
                'Client-ID': 'test_client_id',
                'Authorization': 'Bearer test_token'
            },
            data='fields name;'
        )

    def test_missing_igdb_settings(self, db_session):
        """Test API request with missing IGDB settings."""
        safe_cleanup_database(db_session)  # Ensure no settings exist
        result = make_igdb_api_request('https://api.igdb.com/v4/games', 'fields name;')
        
        assert result == {"error": "IGDB settings not configured in database"}

    def test_missing_client_credentials(self, db_session):
        """Test API request with incomplete IGDB settings."""
        safe_cleanup_database(db_session)
        settings = GlobalSettings(igdb_client_id='test_id')  # Missing secret
        db_session.add(settings)
        db_session.commit()  # Use commit to make it visible to global session
        
        result = make_igdb_api_request('https://api.igdb.com/v4/games', 'fields name;')
        
        assert result == {"error": "IGDB settings not configured in database"}

    @patch('modules.utils_igdb_api.get_access_token')
    def test_failed_access_token_retrieval(self, mock_get_token, db_session, sample_global_settings):
        """Test API request when access token retrieval fails."""
        mock_get_token.return_value = None
        
        result = make_igdb_api_request('https://api.igdb.com/v4/games', 'fields name;')
        
        assert result == {"error": "Failed to retrieve access token"}

    @patch('modules.utils_igdb_api.get_access_token')
    @patch('requests.post')
    def test_request_exception(self, mock_requests_post, mock_get_token,
                             db_session, sample_global_settings):
        """Test API request with RequestException."""
        mock_get_token.return_value = 'test_token'
        mock_requests_post.side_effect = Exception("Network error")
        
        result = make_igdb_api_request('https://api.igdb.com/v4/games', 'fields name;')
        
        assert "error" in result
        assert "An unexpected error occurred" in result["error"]

    @patch('modules.utils_igdb_api.get_access_token')
    @patch('requests.post')
    def test_invalid_json_response(self, mock_requests_post, mock_get_token,
                                 db_session, sample_global_settings):
        """Test API request with invalid JSON response."""
        mock_get_token.return_value = 'test_token'
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_requests_post.return_value = mock_response
        
        result = make_igdb_api_request('https://api.igdb.com/v4/games', 'fields name;')
        
        assert result == {"error": "make_igdb_api_request Invalid JSON in response"}


class TestGetAccessToken:
    """Tests for get_access_token function."""
    
    @patch('requests.post')
    def test_successful_token_retrieval(self, mock_requests_post):
        """Test successful access token retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'access_token': 'test_token_12345'}
        mock_requests_post.return_value = mock_response
        
        token = get_access_token('client_id', 'client_secret')
        
        assert token == 'test_token_12345'
        mock_requests_post.assert_called_once_with(
            'https://id.twitch.tv/oauth2/token',
            params={
                'client_id': 'client_id',
                'client_secret': 'client_secret',
                'grant_type': 'client_credentials'
            }
        )

    @patch('requests.post')
    @patch('builtins.print')
    def test_failed_token_retrieval(self, mock_print, mock_requests_post):
        """Test failed access token retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_requests_post.return_value = mock_response
        
        token = get_access_token('invalid_id', 'invalid_secret')
        
        assert token is None
        mock_print.assert_called_once_with("Failed to obtain access token")


class TestGetCoverThumbnailUrl:
    """Tests for get_cover_thumbnail_url function."""
    
    @patch('modules.utils_igdb_api.make_igdb_api_request')
    def test_successful_cover_thumbnail_retrieval(self, mock_api_request, mock_cover_response):
        """Test successful cover thumbnail URL retrieval."""
        mock_api_request.return_value = mock_cover_response
        
        result = get_cover_thumbnail_url(12345)
        
        assert result == 'https://images.igdb.com/igdb/image/upload/t_thumb/test_cover.jpg'
        mock_api_request.assert_called_once_with(
            'https://api.igdb.com/v4/covers',
            'fields url; where game=12345;'
        )

    @patch('modules.utils_igdb_api.make_igdb_api_request')
    @patch('builtins.print')
    def test_api_error_response(self, mock_print, mock_api_request):
        """Test cover thumbnail retrieval with API error."""
        mock_api_request.return_value = {'error': 'API Error'}
        
        result = get_cover_thumbnail_url(12345)
        
        assert result is None
        mock_print.assert_called_once_with(
            "Failed to retrieve cover for IGDB ID 12345. Response: {'error': 'API Error'}"
        )

    @patch('modules.utils_igdb_api.make_igdb_api_request')
    @patch('builtins.print')
    def test_empty_response(self, mock_print, mock_api_request):
        """Test cover thumbnail retrieval with empty response."""
        mock_api_request.return_value = []
        
        result = get_cover_thumbnail_url(12345)
        
        assert result is None
        mock_print.assert_called_once_with(
            "Failed to retrieve cover for IGDB ID 12345. Response: []"
        )

    @patch('modules.utils_igdb_api.make_igdb_api_request')
    @patch('builtins.print')
    def test_missing_url_in_response(self, mock_print, mock_api_request):
        """Test cover thumbnail retrieval with missing URL in response."""
        mock_api_request.return_value = [{'id': 1}]  # No URL field
        
        result = get_cover_thumbnail_url(12345)
        
        assert result is None
        mock_print.assert_called_once_with("No cover URL found for IGDB ID 12345.")


class TestGetCoverUrl:
    """Tests for get_cover_url function."""
    
    @patch('modules.utils_igdb_api.make_igdb_api_request')
    def test_successful_cover_url_retrieval(self, mock_api_request, mock_cover_image_id_response):
        """Test successful cover URL retrieval."""
        mock_api_request.return_value = mock_cover_image_id_response
        
        result = get_cover_url(12345)
        
        assert result == 'https://images.igdb.com/igdb/image/upload/t_cover_big_2x/test_image_id_12345.jpg'
        mock_api_request.assert_called_once_with(
            'https://api.igdb.com/v4/covers',
            'fields image_id; where game=12345;'
        )

    @patch('modules.utils_igdb_api.make_igdb_api_request')
    @patch('builtins.print')
    def test_api_error_response(self, mock_print, mock_api_request):
        """Test cover URL retrieval with API error."""
        mock_api_request.return_value = {'error': 'API Error'}
        
        result = get_cover_url(12345)
        
        assert result is None
        mock_print.assert_called_once_with(
            "Failed to retrieve cover image ID for IGDB ID 12345. Response: {'error': 'API Error'}"
        )

    @patch('modules.utils_igdb_api.make_igdb_api_request')
    @patch('builtins.print')
    def test_empty_response(self, mock_print, mock_api_request):
        """Test cover URL retrieval with empty response."""
        mock_api_request.return_value = []
        
        result = get_cover_url(12345)
        
        assert result is None
        mock_print.assert_called_once_with(
            "Failed to retrieve cover image ID for IGDB ID 12345. Response: []"
        )

    @patch('modules.utils_igdb_api.make_igdb_api_request')
    @patch('builtins.print')
    def test_missing_image_id_in_response(self, mock_print, mock_api_request):
        """Test cover URL retrieval with missing image_id in response."""
        mock_api_request.return_value = [{'id': 1}]  # No image_id field
        
        result = get_cover_url(12345)
        
        assert result is None
        mock_print.assert_called_once_with("No cover image ID found for IGDB ID 12345.")


class TestIGDBRateLimiter:
    """Tests for IGDBRateLimiter class."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes with correct defaults."""
        limiter = IGDBRateLimiter()
        
        assert limiter.max_requests_per_second == 4
        assert limiter.max_concurrent_requests == 8
        assert limiter.request_times == []
        assert limiter.concurrent_requests == 0
        assert limiter.lock is not None

    def test_rate_limiter_custom_initialization(self):
        """Test rate limiter with custom parameters."""
        limiter = IGDBRateLimiter(max_requests_per_second=2, max_concurrent_requests=4)
        
        assert limiter.max_requests_per_second == 2
        assert limiter.max_concurrent_requests == 4

    @patch('time.time')
    @patch('time.sleep')
    def test_acquire_within_limits(self, mock_sleep, mock_time):
        """Test acquire when within rate limits."""
        mock_time.return_value = 1000.0
        limiter = IGDBRateLimiter(max_requests_per_second=4, max_concurrent_requests=8)
        
        limiter.acquire()
        
        assert limiter.concurrent_requests == 1
        assert len(limiter.request_times) == 1
        mock_sleep.assert_not_called()

    @patch('time.time')
    @patch('time.sleep')
    def test_acquire_rate_limit_exceeded(self, mock_sleep, mock_time):
        """Test acquire when rate limit is exceeded."""
        limiter = IGDBRateLimiter(max_requests_per_second=2, max_concurrent_requests=8)
        mock_time.return_value = 1000.0
        
        # Fill up the rate limit
        limiter.request_times = [999.5, 999.7]  # 2 requests in the last second
        
        # This should trigger a sleep
        limiter.acquire()
        
        mock_sleep.assert_called()
        assert limiter.concurrent_requests == 1

    def test_release_decrements_counter(self):
        """Test release method decrements concurrent requests."""
        limiter = IGDBRateLimiter()
        limiter.concurrent_requests = 3
        
        limiter.release()
        
        assert limiter.concurrent_requests == 2

    def test_release_never_goes_below_zero(self):
        """Test release method never goes below zero."""
        limiter = IGDBRateLimiter()
        limiter.concurrent_requests = 0
        
        limiter.release()
        
        assert limiter.concurrent_requests == 0

    @patch('time.time')
    def test_old_request_times_cleanup(self, mock_time):
        """Test that old request times are cleaned up."""
        mock_time.return_value = 1000.0
        limiter = IGDBRateLimiter()
        
        # Add some old request times (more than 1 second old)
        limiter.request_times = [998.0, 998.5, 999.5]  # Only 999.5 should remain
        
        limiter.acquire()
        
        # Should clean up old requests and add new one
        assert len(limiter.request_times) == 2  # 999.5 + new request at 1000.0
        assert 999.5 in limiter.request_times
        assert 1000.0 in limiter.request_times

    def test_concurrent_access_thread_safety(self):
        """Test rate limiter thread safety with concurrent access."""
        limiter = IGDBRateLimiter(max_requests_per_second=10, max_concurrent_requests=5)
        results = []
        
        def worker():
            limiter.acquire()
            results.append(limiter.concurrent_requests)
            time.sleep(0.01)  # Small delay to simulate work
            limiter.release()
        
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All threads should have completed
        assert len(results) == 3
        assert limiter.concurrent_requests == 0