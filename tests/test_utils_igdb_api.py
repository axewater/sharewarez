import pytest
from unittest.mock import patch, MagicMock, Mock
import requests

from modules.utils_igdb_api import (
    make_igdb_api_request, get_access_token, 
    get_cover_thumbnail_url, get_cover_url
)


class TestMakeIgdbApiRequest:
    """Test the make_igdb_api_request function."""
    
    @patch('modules.utils_igdb_api.requests.post')
    @patch('modules.utils_igdb_api.GlobalSettings')
    def test_make_igdb_api_request_success(self, mock_settings, mock_post):
        """Test successful IGDB API request."""
        # Setup
        mock_settings_instance = Mock()
        mock_settings_instance.igdb_client_id = "test_client_id"
        mock_settings_instance.igdb_access_token = "test_token"
        mock_settings.query.first.return_value = mock_settings_instance
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'id': 123, 'name': 'Test Game'}]
        mock_post.return_value = mock_response
        
        # Execute
        result = make_igdb_api_request("https://api.igdb.com/v4/games", "fields id,name;")
        
        # Verify
        assert result == [{'id': 123, 'name': 'Test Game'}]
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.igdb.com/v4/games"
        assert 'Client-ID' in call_args[1]['headers']
        assert 'Authorization' in call_args[1]['headers']
    
    @patch('modules.utils_igdb_api.requests.post')
    @patch('modules.utils_igdb_api.GlobalSettings')
    def test_make_igdb_api_request_http_error(self, mock_settings, mock_post):
        """Test IGDB API request with HTTP error."""
        # Setup
        mock_settings_instance = Mock()
        mock_settings_instance.igdb_client_id = "test_client_id"
        mock_settings_instance.igdb_access_token = "test_token"
        mock_settings.query.first.return_value = mock_settings_instance
        
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Unauthorized")
        mock_post.return_value = mock_response
        
        # Execute
        result = make_igdb_api_request("https://api.igdb.com/v4/games", "fields id,name;")
        
        # Verify
        assert result == []
        mock_post.assert_called_once()
    
    @patch('modules.utils_igdb_api.requests.post')
    @patch('modules.utils_igdb_api.GlobalSettings')
    def test_make_igdb_api_request_no_settings(self, mock_settings, mock_post):
        """Test IGDB API request when no settings exist."""
        # Setup
        mock_settings.query.first.return_value = None
        
        # Execute
        result = make_igdb_api_request("https://api.igdb.com/v4/games", "fields id,name;")
        
        # Verify
        assert result == []
        mock_post.assert_not_called()
    
    @patch('modules.utils_igdb_api.requests.post')
    @patch('modules.utils_igdb_api.GlobalSettings')
    def test_make_igdb_api_request_connection_error(self, mock_settings, mock_post):
        """Test IGDB API request with connection error."""
        # Setup
        mock_settings_instance = Mock()
        mock_settings_instance.igdb_client_id = "test_client_id"
        mock_settings_instance.igdb_access_token = "test_token"
        mock_settings.query.first.return_value = mock_settings_instance
        
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")
        
        # Execute
        result = make_igdb_api_request("https://api.igdb.com/v4/games", "fields id,name;")
        
        # Verify
        assert result == []
        mock_post.assert_called_once()


class TestGetAccessToken:
    """Test the get_access_token function."""
    
    @patch('modules.utils_igdb_api.requests.post')
    def test_get_access_token_success(self, mock_post):
        """Test successful access token retrieval."""
        # Setup
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'expires_in': 3600,
            'token_type': 'bearer'
        }
        mock_post.return_value = mock_response
        
        # Execute
        result = get_access_token("test_client_id", "test_client_secret")
        
        # Verify
        assert result == 'new_access_token'
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert 'oauth2/token' in call_args[0][0]
        assert call_args[1]['params']['client_id'] == 'test_client_id'
        assert call_args[1]['params']['client_secret'] == 'test_client_secret'
    
    @patch('modules.utils_igdb_api.requests.post')
    def test_get_access_token_http_error(self, mock_post):
        """Test access token retrieval with HTTP error."""
        # Setup
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Bad Request")
        mock_post.return_value = mock_response
        
        # Execute
        result = get_access_token("invalid_client_id", "invalid_secret")
        
        # Verify
        assert result is None
        mock_post.assert_called_once()
    
    @patch('modules.utils_igdb_api.requests.post')
    def test_get_access_token_connection_error(self, mock_post):
        """Test access token retrieval with connection error."""
        # Setup
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")
        
        # Execute
        result = get_access_token("test_client_id", "test_client_secret")
        
        # Verify
        assert result is None
        mock_post.assert_called_once()


class TestGetCoverThumbnailUrl:
    """Test the get_cover_thumbnail_url function."""
    
    @patch('modules.utils_igdb_api.make_igdb_api_request')
    def test_get_cover_thumbnail_url_success(self, mock_api):
        """Test successful cover thumbnail URL retrieval."""
        # Setup
        mock_api.return_value = [{'url': '//images.igdb.com/igdb/image/upload/t_thumb/abcd1234.jpg'}]
        
        # Execute
        result = get_cover_thumbnail_url(12345)
        
        # Verify
        assert result == 'https://images.igdb.com/igdb/image/upload/t_thumb/abcd1234.jpg'
        mock_api.assert_called_once()
        call_args = mock_api.call_args
        assert 'covers' in call_args[0][0]
        assert 'game = 12345' in call_args[0][1]
    
    @patch('modules.utils_igdb_api.make_igdb_api_request')
    def test_get_cover_thumbnail_url_no_results(self, mock_api):
        """Test cover thumbnail URL retrieval with no results."""
        # Setup
        mock_api.return_value = []
        
        # Execute
        result = get_cover_thumbnail_url(12345)
        
        # Verify
        assert result is None
        mock_api.assert_called_once()
    
    @patch('modules.utils_igdb_api.make_igdb_api_request')
    def test_get_cover_thumbnail_url_api_error(self, mock_api):
        """Test cover thumbnail URL retrieval with API error."""
        # Setup
        mock_api.side_effect = Exception("API Error")
        
        # Execute
        result = get_cover_thumbnail_url(12345)
        
        # Verify
        assert result is None
        mock_api.assert_called_once()


class TestGetCoverUrl:
    """Test the get_cover_url function."""
    
    @patch('modules.utils_igdb_api.make_igdb_api_request')
    def test_get_cover_url_success(self, mock_api):
        """Test successful cover URL retrieval."""
        # Setup
        mock_api.return_value = [{'url': '//images.igdb.com/igdb/image/upload/t_cover_big/abcd1234.jpg'}]
        
        # Execute
        result = get_cover_url(12345)
        
        # Verify
        assert result == 'https://images.igdb.com/igdb/image/upload/t_cover_big/abcd1234.jpg'
        mock_api.assert_called_once()
        call_args = mock_api.call_args
        assert 'covers' in call_args[0][0]
        assert 'game = 12345' in call_args[0][1]
    
    @patch('modules.utils_igdb_api.make_igdb_api_request')
    def test_get_cover_url_no_results(self, mock_api):
        """Test cover URL retrieval with no results."""
        # Setup
        mock_api.return_value = []
        
        # Execute
        result = get_cover_url(12345)
        
        # Verify
        assert result is None
        mock_api.assert_called_once()
    
    @patch('modules.utils_igdb_api.make_igdb_api_request')
    def test_get_cover_url_api_error(self, mock_api):
        """Test cover URL retrieval with API error."""
        # Setup
        mock_api.side_effect = Exception("API Error")
        
        # Execute
        result = get_cover_url(12345)
        
        # Verify
        assert result is None
        mock_api.assert_called_once()


class TestApiUrlAndQueryConstruction:
    """Test API URL and query construction in various functions."""
    
    @patch('modules.utils_igdb_api.make_igdb_api_request')
    def test_cover_thumbnail_url_construction(self, mock_api):
        """Test proper URL construction for cover thumbnails."""
        # Setup
        mock_api.return_value = []
        
        # Execute
        get_cover_thumbnail_url(12345)
        
        # Verify
        mock_api.assert_called_once()
        call_args = mock_api.call_args
        endpoint_url = call_args[0][0]
        query = call_args[0][1]
        
        assert 'covers' in endpoint_url
        assert 'fields url' in query
        assert 'game = 12345' in query
        assert 'limit 1' in query
    
    @patch('modules.utils_igdb_api.make_igdb_api_request')
    def test_cover_url_construction(self, mock_api):
        """Test proper URL construction for cover images."""
        # Setup
        mock_api.return_value = []
        
        # Execute
        get_cover_url(12345)
        
        # Verify
        mock_api.assert_called_once()
        call_args = mock_api.call_args
        endpoint_url = call_args[0][0]
        query = call_args[0][1]
        
        assert 'covers' in endpoint_url
        assert 'fields url' in query
        assert 'game = 12345' in query
        assert 'limit 1' in query