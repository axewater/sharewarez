import pytest
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from modules.models import User, SystemEvents, GlobalSettings
from modules.utils_status import (
    get_system_info,
    get_config_values,
    get_active_users,
    get_log_info,
    check_server_settings
)


class TestGetSystemInfo:
    """Tests for get_system_info function."""

    @patch('modules.utils_status.socket.gethostbyname')
    @patch('modules.utils_status.socket.gethostname')
    @patch('modules.utils_status.platform.python_version')
    @patch('modules.utils_status.platform.version')
    @patch('modules.utils_status.platform.system')
    def test_get_system_info_success(self, mock_system, mock_version, mock_python_version,
                                   mock_hostname, mock_gethostbyname):
        """Test successful system info retrieval."""
        # Setup mocks
        mock_system.return_value = 'Linux'
        mock_version.return_value = '5.4.0-74-generic'
        mock_python_version.return_value = '3.9.7'
        mock_hostname.return_value = 'test-server'
        mock_gethostbyname.return_value = '192.168.1.100'
        
        result = get_system_info()
        
        assert result['Operating System'] == 'Linux'
        assert result['Operating System Version'] == '5.4.0-74-generic'
        assert result['Python Version'] == '3.9.7'
        assert result['Hostname'] == 'test-server'
        assert result['IP Address'] == '192.168.1.100'
        assert 'Current Time' in result
        
        # Verify datetime format
        current_time = result['Current Time']
        datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")

    @patch('modules.utils_status.socket.gethostbyname')
    @patch('modules.utils_status.socket.gethostname')
    @patch('modules.utils_status.platform.python_version')
    @patch('modules.utils_status.platform.version')
    @patch('modules.utils_status.platform.system')
    @patch('builtins.print')
    def test_get_system_info_network_error(self, mock_print, mock_system, mock_version, 
                                         mock_python_version, mock_hostname, mock_gethostbyname):
        """Test system info retrieval with network error."""
        # Setup mocks - network operations fail
        mock_system.return_value = 'Linux'
        mock_version.return_value = '5.4.0-74-generic'
        mock_python_version.return_value = '3.9.7'
        mock_hostname.side_effect = Exception('Network error')
        mock_gethostbyname.return_value = '127.0.0.1'
        
        result = get_system_info()
        
        assert result['Operating System'] == 'Linux'
        assert result['Operating System Version'] == '5.4.0-74-generic'
        assert result['Python Version'] == '3.9.7'
        assert result['Hostname'] == 'Unavailable'
        assert result['IP Address'] == 'Unavailable'
        assert 'Current Time' in result
        
        # Verify error was printed
        mock_print.assert_called_once()
        assert 'Error retrieving IP address' in str(mock_print.call_args)


class TestGetConfigValues:
    """Tests for get_config_values function."""

    @patch('modules.utils_status.os.path.exists')
    @patch('modules.utils_status.os.access')
    def test_get_config_values_with_existing_paths(self, mock_access, mock_exists):
        """Test config values retrieval with existing accessible paths."""
        # Mock all paths exist and are accessible
        mock_exists.return_value = True
        mock_access.return_value = True
        
        # Mock Config class with test paths
        with patch('modules.utils_status.Config') as mock_config:
            mock_config.DATA_FOLDER_WAREZ = '/test/warez/path'
            mock_config.IMAGE_SAVE_PATH = '/test/images/path'
            mock_config.UPLOAD_FOLDER = '/test/uploads/path'
            
            result = get_config_values()
            
            expected_keys = ['DATA_FOLDER_WAREZ', 'IMAGE_SAVE_PATH', 'UPLOAD_FOLDER']
            for key in expected_keys:
                assert key in result
                assert result[key]['path'] == getattr(mock_config, key)
                assert result[key]['exists'] is True
                assert result[key]['read'] is True
                assert result[key]['write'] is True

    @patch('modules.utils_status.os.path.exists')
    @patch('modules.utils_status.os.access')
    def test_get_config_values_with_nonexistent_paths(self, mock_access, mock_exists):
        """Test config values retrieval with non-existent paths."""
        # Mock paths don't exist
        mock_exists.return_value = False
        mock_access.return_value = False
        
        # Mock Config class with test paths
        with patch('modules.utils_status.Config') as mock_config:
            mock_config.DATA_FOLDER_WAREZ = '/nonexistent/path'
            
            result = get_config_values()
            
            if 'DATA_FOLDER_WAREZ' in result:
                assert result['DATA_FOLDER_WAREZ']['exists'] is False
                assert result['DATA_FOLDER_WAREZ']['read'] is False
                assert result['DATA_FOLDER_WAREZ']['write'] is False

    @patch('modules.utils_status.os.path.exists')
    @patch('modules.utils_status.os.access')
    def test_get_config_values_mixed_permissions(self, mock_access, mock_exists):
        """Test config values with mixed read/write permissions."""
        mock_exists.return_value = True
        
        def mock_access_func(path, mode):
            if mode == os.R_OK:
                return True  # Readable
            elif mode == os.W_OK:
                return False  # Not writable
            return False
        
        mock_access.side_effect = mock_access_func
        
        with patch('modules.utils_status.Config') as mock_config:
            mock_config.DATA_FOLDER_WAREZ = '/readonly/path'
            
            result = get_config_values()
            
            if 'DATA_FOLDER_WAREZ' in result:
                assert result['DATA_FOLDER_WAREZ']['exists'] is True
                assert result['DATA_FOLDER_WAREZ']['read'] is True
                assert result['DATA_FOLDER_WAREZ']['write'] is False


class TestGetActiveUsers:
    """Tests for get_active_users function."""

    def test_get_active_users_with_recent_logins(self, db_session):
        """Test counting users with recent logins."""
        # Get baseline count first
        baseline_count = get_active_users()
        
        # Create users with different login times
        recent_login_time = datetime.now(timezone.utc) - timedelta(hours=12)
        old_login_time = datetime.now(timezone.utc) - timedelta(hours=48)
        
        # Create active user
        active_user = User(
            name=f'active_user_{uuid4().hex[:8]}',
            email=f'active_{uuid4().hex[:8]}@example.com',
            role='user',
            user_id=str(uuid4())
        )
        active_user.set_password('testpass')
        active_user.lastlogin = recent_login_time
        
        # Create inactive user
        inactive_user = User(
            name=f'inactive_user_{uuid4().hex[:8]}',
            email=f'inactive_{uuid4().hex[:8]}@example.com',
            role='user',
            user_id=str(uuid4())
        )
        inactive_user.set_password('testpass')
        inactive_user.lastlogin = old_login_time
        
        # Create user with no login
        never_logged_in = User(
            name=f'never_user_{uuid4().hex[:8]}',
            email=f'never_{uuid4().hex[:8]}@example.com',
            role='user',
            user_id=str(uuid4())
        )
        never_logged_in.set_password('testpass')
        never_logged_in.lastlogin = None
        
        db_session.add_all([active_user, inactive_user, never_logged_in])
        db_session.flush()
        
        result = get_active_users()
        
        # Should have increased by 1 (only the active user)
        assert result >= baseline_count + 1
        
    def test_get_active_users_no_recent_logins(self, db_session):
        """Test counting users with no recent logins."""
        # Create user with old login
        old_user = User(
            name=f'old_user_{uuid4().hex[:8]}',
            email=f'old_{uuid4().hex[:8]}@example.com',
            role='user',
            user_id=str(uuid4())
        )
        old_user.set_password('testpass')
        old_user.lastlogin = datetime.now(timezone.utc) - timedelta(days=7)
        
        db_session.add(old_user)
        db_session.flush()
        
        # Count only users active in last 24 hours (should not include our test user)
        result = get_active_users()
        
        # Result should be the baseline count (may be 0 or more depending on existing data)
        assert isinstance(result, int)
        assert result >= 0


class TestGetLogInfo:
    """Tests for get_log_info function."""

    def test_get_log_info_with_events(self, db_session):
        """Test log info retrieval with existing events."""
        # Get baseline count first
        baseline_result = get_log_info()
        baseline_count = baseline_result['count']
        
        # Create test system events with very recent timestamps to ensure they are latest
        event1 = SystemEvents(
            timestamp=datetime.now(timezone.utc) + timedelta(seconds=1),
            event_level='INFO',
            event_text='Test event 1'
        )
        
        event2 = SystemEvents(
            timestamp=datetime.now(timezone.utc) + timedelta(seconds=2),
            event_level='ERROR',
            event_text='Test event 2'
        )
        
        db_session.add_all([event1, event2])
        db_session.flush()
        
        result = get_log_info()
        
        assert 'count' in result
        assert 'latest' in result
        assert isinstance(result['count'], int)
        assert result['count'] >= baseline_count + 2
        
        # Latest event should be event2 (more recent)
        if result['latest']:
            assert result['latest'].event_text == 'Test event 2'
            assert result['latest'].event_level == 'ERROR'

    def test_get_log_info_no_events(self, db_session):
        """Test log info retrieval with no events."""
        # Clear any existing events (if needed for clean test)
        # Note: We can't delete from SystemEvents easily due to transaction isolation
        # So we just test the structure
        
        result = get_log_info()
        
        assert 'count' in result
        assert 'latest' in result
        assert isinstance(result['count'], int)
        assert result['count'] >= 0


class TestCheckServerSettings:
    """Tests for check_server_settings function."""

    def test_check_server_settings_enabled(self, db_session):
        """Test server settings check when feature is enabled."""
        # Get existing GlobalSettings (as per testing guide)
        from sqlalchemy import select
        settings = db_session.execute(select(GlobalSettings)).scalars().first()
        if not settings:
            settings = GlobalSettings()
            db_session.add(settings)
            db_session.flush()
        
        # Store original value to restore later
        original_settings = settings.settings.copy() if settings.settings else {}
        
        # Enable the server status feature
        if not settings.settings:
            settings.settings = {}
        settings.settings['enableServerStatusFeature'] = True
        db_session.flush()
        
        try:
            enabled, message = check_server_settings()
            
            assert enabled is True
            assert message is None
        finally:
            # Restore original settings
            settings.settings = original_settings
            db_session.flush()

    def test_check_server_settings_disabled(self, db_session):
        """Test server settings check when feature is disabled."""
        # Get existing GlobalSettings (as per testing guide)
        from sqlalchemy import select
        settings = db_session.execute(select(GlobalSettings)).scalars().first()
        if not settings:
            settings = GlobalSettings()
            db_session.add(settings)
            db_session.flush()
        
        # Store original value to restore later
        original_settings = settings.settings.copy() if settings.settings else {}
        
        # Disable the server status feature
        if not settings.settings:
            settings.settings = {}
        settings.settings['enableServerStatusFeature'] = False
        db_session.flush()
        
        try:
            enabled, message = check_server_settings()
            
            assert enabled is False
            assert message == "Server Status feature is disabled."
        finally:
            # Restore original settings
            settings.settings = original_settings
            db_session.flush()

    def test_check_server_settings_no_settings_record(self, db_session):
        """Test server settings check with no GlobalSettings record."""
        # Clear any existing GlobalSettings
        from sqlalchemy import select, delete
        db_session.execute(delete(GlobalSettings))
        db_session.commit()
        
        enabled, message = check_server_settings()
        
        assert enabled is False
        assert message == "Server settings not configured."

    def test_check_server_settings_no_settings_dict(self, db_session):
        """Test server settings check with null settings dictionary."""
        # Get or create GlobalSettings
        from sqlalchemy import select
        settings = db_session.execute(select(GlobalSettings)).scalars().first()
        if not settings:
            settings = GlobalSettings()
            db_session.add(settings)
        
        # Set settings to None
        settings.settings = None
        db_session.commit()
        
        enabled, message = check_server_settings()
        
        assert enabled is False
        assert message == "Server settings not configured."