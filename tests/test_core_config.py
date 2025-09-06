"""
Unit tests for modules.core.config

Tests the AppConfig dataclass and its factory methods for configuration management.
"""

import os
import pytest
from unittest.mock import patch

from modules.core.config import AppConfig


class TestAppConfig:
    """Test AppConfig dataclass initialization and default values."""
    
    def test_appconfig_initialization_with_defaults(self):
        """Test AppConfig initialization with minimal required parameters."""
        config = AppConfig(
            database_url="sqlite:///test.db",
            upload_folder="/test/uploads",
            data_folder="/test/data"
        )
        
        # Required fields
        assert config.database_url == "sqlite:///test.db"
        assert config.upload_folder == "/test/uploads"
        assert config.data_folder == "/test/data"
        
        # Default values
        assert config.igdb_client_id is None
        assert config.igdb_client_secret is None
        assert config.igdb_access_token is None
        assert config.igdb_api_endpoint == "https://api.igdb.com/v4"
        assert config.discord_webhook_url is None
        assert config.secret_key == "dev-secret-key"
        assert config.debug is False
        assert config.testing is False
        assert config.update_folder_name == "Updates"
        assert config.extras_folder_name == "Extras"
        assert config.max_image_download_workers == 5
        assert config.image_download_batch_size == 10
        assert config.image_download_delay == 1.0
        assert config.scan_timeout == 300
    
    def test_appconfig_initialization_with_all_parameters(self):
        """Test AppConfig initialization with all parameters specified."""
        config = AppConfig(
            database_url="postgresql://user:pass@host:5432/db",
            upload_folder="/custom/uploads",
            data_folder="/custom/data",
            igdb_client_id="test_client_id",
            igdb_client_secret="test_secret",
            igdb_access_token="test_token",
            igdb_api_endpoint="https://custom.api.com/v4",
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
            secret_key="custom-secret-key",
            debug=True,
            testing=True,
            update_folder_name="CustomUpdates",
            extras_folder_name="CustomExtras",
            max_image_download_workers=10,
            image_download_batch_size=20,
            image_download_delay=2.0,
            scan_timeout=600
        )
        
        assert config.database_url == "postgresql://user:pass@host:5432/db"
        assert config.upload_folder == "/custom/uploads"
        assert config.data_folder == "/custom/data"
        assert config.igdb_client_id == "test_client_id"
        assert config.igdb_client_secret == "test_secret"
        assert config.igdb_access_token == "test_token"
        assert config.igdb_api_endpoint == "https://custom.api.com/v4"
        assert config.discord_webhook_url == "https://discord.com/api/webhooks/123/abc"
        assert config.secret_key == "custom-secret-key"
        assert config.debug is True
        assert config.testing is True
        assert config.update_folder_name == "CustomUpdates"
        assert config.extras_folder_name == "CustomExtras"
        assert config.max_image_download_workers == 10
        assert config.image_download_batch_size == 20
        assert config.image_download_delay == 2.0
        assert config.scan_timeout == 600


class TestAppConfigFromFlaskConfig:
    """Test AppConfig.from_flask_config factory method."""
    
    def test_from_flask_config_with_minimal_data(self):
        """Test creating AppConfig from minimal Flask config."""
        flask_config = {}
        
        config = AppConfig.from_flask_config(flask_config)
        
        # Should use default values
        assert config.database_url == "sqlite:///app.db"
        assert config.upload_folder == "uploads"
        assert config.data_folder == ""
        assert config.igdb_client_id is None
        assert config.igdb_client_secret is None
        assert config.igdb_access_token is None
        assert config.igdb_api_endpoint == "https://api.igdb.com/v4"
        assert config.discord_webhook_url is None
        assert config.secret_key == "dev-secret-key"
        assert config.debug is False
        assert config.testing is False
        assert config.update_folder_name == "Updates"
        assert config.extras_folder_name == "Extras"
    
    def test_from_flask_config_with_complete_data(self):
        """Test creating AppConfig from complete Flask config."""
        flask_config = {
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/testdb',
            'UPLOAD_FOLDER': '/app/uploads',
            'DATA_FOLDER_WAREZ': '/app/games',
            'IGDB_CLIENT_ID': 'flask_client_id',
            'IGDB_CLIENT_SECRET': 'flask_client_secret',
            'IGDB_ACCESS_TOKEN': 'flask_access_token',
            'IGDB_API_ENDPOINT': 'https://flask.api.com/v4',
            'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/flask/xyz',
            'SECRET_KEY': 'flask-secret-key',
            'DEBUG': True,
            'TESTING': True,
            'UPDATE_FOLDER_NAME': 'FlaskUpdates',
            'EXTRAS_FOLDER_NAME': 'FlaskExtras'
        }
        
        config = AppConfig.from_flask_config(flask_config)
        
        assert config.database_url == 'postgresql://user:pass@localhost:5432/testdb'
        assert config.upload_folder == '/app/uploads'
        assert config.data_folder == '/app/games'
        assert config.igdb_client_id == 'flask_client_id'
        assert config.igdb_client_secret == 'flask_client_secret'
        assert config.igdb_access_token == 'flask_access_token'
        assert config.igdb_api_endpoint == 'https://flask.api.com/v4'
        assert config.discord_webhook_url == 'https://discord.com/api/webhooks/flask/xyz'
        assert config.secret_key == 'flask-secret-key'
        assert config.debug is True
        assert config.testing is True
        assert config.update_folder_name == 'FlaskUpdates'
        assert config.extras_folder_name == 'FlaskExtras'
    
    def test_from_flask_config_with_partial_data(self):
        """Test creating AppConfig from partial Flask config."""
        flask_config = {
            'DATABASE_URL': 'sqlite:///partial.db',
            'IGDB_CLIENT_ID': 'partial_client_id',
            'DEBUG': True
        }
        
        config = AppConfig.from_flask_config(flask_config)
        
        # Specified values
        assert config.database_url == 'sqlite:///partial.db'
        assert config.igdb_client_id == 'partial_client_id'
        assert config.debug is True
        
        # Default values for unspecified
        assert config.upload_folder == "uploads"
        assert config.data_folder == ""
        assert config.igdb_client_secret is None
        assert config.secret_key == "dev-secret-key"
        assert config.testing is False


class TestAppConfigFromEnvironment:
    """Test AppConfig.from_environment factory method."""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_from_environment_with_no_env_vars(self):
        """Test creating AppConfig from environment with no environment variables."""
        config = AppConfig.from_environment()
        
        # Should use default values
        assert config.database_url == "sqlite:///app.db"
        assert config.upload_folder == "uploads"
        assert config.data_folder == ""
        assert config.igdb_client_id is None
        assert config.igdb_client_secret is None
        assert config.igdb_access_token is None
        assert config.igdb_api_endpoint == "https://api.igdb.com/v4"
        assert config.discord_webhook_url is None
        assert config.secret_key == "dev-secret-key"
        assert config.debug is False
        assert config.testing is False
        assert config.update_folder_name == "Updates"
        assert config.extras_folder_name == "Extras"
    
    @patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql://env:pass@localhost:5432/envdb',
        'UPLOAD_FOLDER': '/env/uploads',
        'DATA_FOLDER_WAREZ': '/env/games',
        'IGDB_CLIENT_ID': 'env_client_id',
        'IGDB_CLIENT_SECRET': 'env_client_secret',
        'IGDB_ACCESS_TOKEN': 'env_access_token',
        'IGDB_API_ENDPOINT': 'https://env.api.com/v4',
        'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/env/abc',
        'SECRET_KEY': 'env-secret-key',
        'DEBUG': 'true',
        'TESTING': 'true',
        'UPDATE_FOLDER_NAME': 'EnvUpdates',
        'EXTRAS_FOLDER_NAME': 'EnvExtras'
    })
    def test_from_environment_with_all_env_vars(self):
        """Test creating AppConfig from environment with all environment variables."""
        config = AppConfig.from_environment()
        
        assert config.database_url == 'postgresql://env:pass@localhost:5432/envdb'
        assert config.upload_folder == '/env/uploads'
        assert config.data_folder == '/env/games'
        assert config.igdb_client_id == 'env_client_id'
        assert config.igdb_client_secret == 'env_client_secret'
        assert config.igdb_access_token == 'env_access_token'
        assert config.igdb_api_endpoint == 'https://env.api.com/v4'
        assert config.discord_webhook_url == 'https://discord.com/api/webhooks/env/abc'
        assert config.secret_key == 'env-secret-key'
        assert config.debug is True
        assert config.testing is True
        assert config.update_folder_name == 'EnvUpdates'
        assert config.extras_folder_name == 'EnvExtras'
    
    @patch.dict(os.environ, {
        'DATABASE_URL': 'sqlite:///env.db',
        'IGDB_CLIENT_ID': 'env_partial_id',
        'DEBUG': 'false'
    }, clear=True)
    def test_from_environment_with_partial_env_vars(self):
        """Test creating AppConfig from environment with partial environment variables."""
        config = AppConfig.from_environment()
        
        # Specified values
        assert config.database_url == 'sqlite:///env.db'
        assert config.igdb_client_id == 'env_partial_id'
        assert config.debug is False
        
        # Default values for unspecified
        assert config.upload_folder == "uploads"
        assert config.igdb_client_secret is None
        assert config.testing is False
    
    @patch.dict(os.environ, {
        'DEBUG': 'True',
        'TESTING': 'FALSE'
    })
    def test_from_environment_boolean_parsing(self):
        """Test boolean parsing from environment variables."""
        config = AppConfig.from_environment()
        
        assert config.debug is True  # 'True' -> True
        assert config.testing is False  # 'FALSE' -> False
    
    @patch.dict(os.environ, {
        'DEBUG': 'yes',
        'TESTING': 'no'
    })
    def test_from_environment_boolean_parsing_non_true_values(self):
        """Test boolean parsing handles non-'true' values as False."""
        config = AppConfig.from_environment()
        
        assert config.debug is False  # 'yes' -> False
        assert config.testing is False  # 'no' -> False


class TestAppConfigForTesting:
    """Test AppConfig.for_testing factory method."""
    
    def test_for_testing_with_defaults(self):
        """Test creating test AppConfig with default test values."""
        config = AppConfig.for_testing()
        
        assert config.database_url == 'sqlite:///:memory:'
        assert config.upload_folder == '/tmp/test_uploads'
        assert config.data_folder == '/tmp/test_data'
        assert config.igdb_client_id == 'test_client_id'
        assert config.igdb_client_secret == 'test_client_secret'
        assert config.igdb_access_token == 'test_access_token'
        assert config.discord_webhook_url is None
        assert config.secret_key == 'test-secret-key'
        assert config.debug is True
        assert config.testing is True
        
        # Non-overridden defaults should remain
        assert config.igdb_api_endpoint == "https://api.igdb.com/v4"
        assert config.update_folder_name == "Updates"
        assert config.extras_folder_name == "Extras"
    
    def test_for_testing_with_overrides(self):
        """Test creating test AppConfig with override values."""
        config = AppConfig.for_testing(
            database_url='postgresql://test:pass@localhost:5432/testdb',
            upload_folder='/custom/test/uploads',
            igdb_client_id='custom_test_client_id',
            debug=False,
            update_folder_name='TestUpdates'
        )
        
        # Overridden values
        assert config.database_url == 'postgresql://test:pass@localhost:5432/testdb'
        assert config.upload_folder == '/custom/test/uploads'
        assert config.igdb_client_id == 'custom_test_client_id'
        assert config.debug is False
        assert config.update_folder_name == 'TestUpdates'
        
        # Non-overridden test defaults
        assert config.data_folder == '/tmp/test_data'
        assert config.igdb_client_secret == 'test_client_secret'
        assert config.secret_key == 'test-secret-key'
        assert config.testing is True
    
    def test_for_testing_ignores_invalid_attributes(self):
        """Test that invalid attribute overrides are ignored."""
        config = AppConfig.for_testing(
            database_url='sqlite:///:memory:',
            invalid_attribute='should_be_ignored',
            another_invalid='also_ignored'
        )
        
        # Valid override should work
        assert config.database_url == 'sqlite:///:memory:'
        
        # Invalid attributes should not exist
        assert not hasattr(config, 'invalid_attribute')
        assert not hasattr(config, 'another_invalid')
        
        # Other test defaults should remain
        assert config.testing is True
        assert config.debug is True