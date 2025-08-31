import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timezone
from uuid import uuid4

from modules import create_app, db
from modules.models import User
from modules.utils_logging import log_system_event




@pytest.fixture
def admin_user(db_session):
    """Create an admin test user."""
    unique_id = uuid4()
    admin = User(
        name=f'admin_{unique_id.hex[:8]}',
        email=f'admin_{unique_id.hex[:8]}@example.com',
        password_hash='hashed_password',
        role='admin',
        user_id=unique_id
    )
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture
def regular_user(db_session):
    """Create a regular test user."""
    unique_id = uuid4()
    user = User(
        name=f'user_{unique_id.hex[:8]}',
        email=f'user_{unique_id.hex[:8]}@example.com',
        password_hash='hashed_password',
        role='user',
        user_id=unique_id
    )
    db_session.add(user)
    db_session.commit()
    return user


class TestContextProcessor:
    """Test the context processor functionality."""

    @patch('modules.routes_info.get_global_settings')
    def test_inject_settings_context_processor(self, mock_get_global_settings, app):
        """Test that the context processor injects global settings correctly."""
        mock_settings = {'theme': 'default', 'site_name': 'SharewareZ', 'maintenance_mode': False}
        mock_get_global_settings.return_value = mock_settings
        
        with app.app_context():
            from modules.routes_info import inject_settings
            result = inject_settings()
            
        assert result == mock_settings
        mock_get_global_settings.assert_called_once()

    @patch('modules.routes_info.get_global_settings')
    def test_inject_settings_cached(self, mock_get_global_settings, app):
        """Test that the context processor is cached."""
        mock_settings = {'theme': 'dark', 'site_name': 'Test Site'}
        mock_get_global_settings.return_value = mock_settings
        
        with app.app_context():
            from modules.routes_info import inject_settings
            
            # Call multiple times
            result1 = inject_settings()
            result2 = inject_settings()
            
            assert result1 == result2 == mock_settings


class TestAdminServerStatusRoute:
    """Test the admin server status route functionality."""

    def test_admin_server_status_requires_login(self, client):
        """Test that admin server status route requires authentication."""
        response = client.get('/admin/server_status_page')
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/login' in response.location

    @patch('modules.routes_info.current_user')
    def test_admin_server_status_requires_admin_role(self, mock_current_user, client, regular_user):
        """Test that admin server status route requires admin role."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'user'
        mock_current_user.id = regular_user.id
        
        with patch('flask_login.utils._get_user', return_value=regular_user):
            response = client.get('/admin/server_status_page')
            
            # Should redirect or return 403
            assert response.status_code in [302, 403]

    @patch('modules.routes_info.log_system_event')
    @patch('modules.routes_info.check_server_settings')
    @patch('modules.routes_info.get_cpu_usage')
    @patch('modules.routes_info.get_process_count')
    @patch('modules.routes_info.get_open_files')
    @patch('modules.routes_info.get_memory_usage')
    @patch('modules.routes_info.get_disk_usage')
    @patch('modules.routes_info.get_warez_folder_usage')
    @patch('modules.routes_info.get_system_info')
    @patch('modules.routes_info.get_config_values')
    @patch('modules.routes_info.get_active_users')
    @patch('modules.routes_info.get_log_info')
    @patch('modules.routes_info.get_formatted_system_uptime')
    @patch('modules.routes_info.get_formatted_app_uptime')
    @patch('modules.routes_info.format_bytes')
    @patch('modules.routes_info.current_user')
    def test_admin_server_status_success(self, mock_current_user, mock_format_bytes,
                                       mock_app_uptime, mock_system_uptime, mock_log_info,
                                       mock_active_users, mock_config_values, mock_system_info,
                                       mock_warez_usage, mock_disk_usage, mock_memory_usage,
                                       mock_open_files, mock_process_count, mock_cpu_usage,
                                       mock_check_server_settings, mock_log_system_event,
                                       client, admin_user):
        """Test successful admin server status page rendering."""
        # Mock all the utility functions
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.id = admin_user.id
        
        mock_check_server_settings.return_value = (True, None)
        mock_cpu_usage.return_value = 45.5
        mock_process_count.return_value = 150
        mock_open_files.return_value = 1200
        mock_memory_usage.return_value = {
            'total': 8589934592,
            'used': 4294967296,
            'available': 4294967296,
            'free': 2147483648
        }
        mock_disk_usage.return_value = {
            'total': 1000000000000,
            'used': 500000000000,
            'available': 500000000000,
            'free': 500000000000
        }
        mock_warez_usage.return_value = {
            'total': 500000000000,
            'used': 250000000000,
            'available': 250000000000,
            'free': 250000000000
        }
        mock_system_info.return_value = {
            'OS': 'Linux',
            'Architecture': 'x86_64',
            'Python Version': '3.9.0'
        }
        mock_config_values.return_value = {
            'DATABASE_URL': 'postgresql://...',
            'DATA_FOLDER_WAREZ': '/var/games'
        }
        mock_active_users.return_value = [{'name': 'testuser', 'last_seen': '2023-01-01'}]
        
        # Mock log entry with proper structure
        mock_latest_log = Mock()
        mock_latest_log.timestamp = datetime(2023, 1, 1, 12, 0, 0)
        mock_latest_log.event_text = 'Test log entry'
        mock_log_info.return_value = {'count': 100, 'latest': mock_latest_log}
        mock_system_uptime.return_value = '2 days, 3 hours'
        mock_app_uptime.return_value = '1 day, 2 hours'
        mock_format_bytes.side_effect = lambda x: f"{x} bytes"

        with patch('flask_login.utils._get_user', return_value=admin_user):
            response = client.get('/admin/server_status_page')
            
        assert response.status_code == 200
        
        # Verify all utility functions were called
        mock_check_server_settings.assert_called_once()
        mock_cpu_usage.assert_called_once()
        mock_process_count.assert_called_once()
        mock_open_files.assert_called_once()
        mock_memory_usage.assert_called_once()
        mock_disk_usage.assert_called_once()
        mock_warez_usage.assert_called_once()
        mock_system_info.assert_called_once()
        mock_config_values.assert_called_once()
        mock_active_users.assert_called_once()
        mock_log_info.assert_called_once()
        mock_system_uptime.assert_called_once()
        mock_app_uptime.assert_called_once()
        
        # Verify logging was called
        mock_log_system_event.assert_called_once_with(
            "Admin accessed server status page", 
            event_type='audit', 
            event_level='information'
        )
        
        # Verify format_bytes was called for formatting usage statistics
        assert mock_format_bytes.call_count >= 8  # Should be called for total, used, available, free for each usage dict

    @patch('modules.routes_info.check_server_settings')
    @patch('modules.routes_info.current_user')
    def test_admin_server_status_invalid_settings(self, mock_current_user,
                                                 mock_check_server_settings,
                                                 client, admin_user):
        """Test admin server status with invalid server settings."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.id = admin_user.id
        
        mock_check_server_settings.return_value = (False, "Database connection failed")

        with patch('flask_login.utils._get_user', return_value=admin_user):
            response = client.get('/admin/server_status_page')
            
        assert response.status_code == 302
        assert '/admin' in response.location or 'admin_dashboard' in response.location

    @patch('modules.routes_info.check_server_settings')
    @patch('modules.routes_info.get_cpu_usage')
    @patch('modules.routes_info.current_user')
    def test_admin_server_status_exception_handling(self, mock_current_user,
                                                   mock_cpu_usage,
                                                   mock_check_server_settings,
                                                   client, admin_user):
        """Test admin server status handles exceptions gracefully."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.id = admin_user.id
        
        mock_check_server_settings.return_value = (True, None)
        mock_cpu_usage.side_effect = Exception("System error occurred")

        with patch('flask_login.utils._get_user', return_value=admin_user):
            response = client.get('/admin/server_status_page')
            
        assert response.status_code == 302
        assert '/admin' in response.location or 'admin_dashboard' in response.location

    @patch('modules.routes_info.log_system_event')
    @patch('modules.routes_info.check_server_settings')
    @patch('modules.routes_info.get_cpu_usage')
    @patch('modules.routes_info.get_process_count')
    @patch('modules.routes_info.get_open_files')
    @patch('modules.routes_info.get_memory_usage')
    @patch('modules.routes_info.get_disk_usage')
    @patch('modules.routes_info.get_warez_folder_usage')
    @patch('modules.routes_info.get_system_info')
    @patch('modules.routes_info.get_config_values')
    @patch('modules.routes_info.get_active_users')
    @patch('modules.routes_info.get_log_info')
    @patch('modules.routes_info.get_formatted_system_uptime')
    @patch('modules.routes_info.get_formatted_app_uptime')
    @patch('modules.routes_info.format_bytes')
    @patch('modules.routes_info.current_user')
    def test_admin_server_status_with_none_usage_values(self, mock_current_user, mock_format_bytes,
                                                      mock_app_uptime, mock_system_uptime, mock_log_info,
                                                      mock_active_users, mock_config_values, mock_system_info,
                                                      mock_warez_usage, mock_disk_usage, mock_memory_usage,
                                                      mock_open_files, mock_process_count, mock_cpu_usage,
                                                      mock_check_server_settings, mock_log_system_event,
                                                      client, admin_user):
        """Test admin server status handles None usage values correctly."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.id = admin_user.id
        
        mock_check_server_settings.return_value = (True, None)
        mock_cpu_usage.return_value = 45.5
        mock_process_count.return_value = 150
        mock_open_files.return_value = 1200
        
        # Some usage returns None
        mock_memory_usage.return_value = None
        mock_disk_usage.return_value = {
            'total': 1000000000000,
            'used': 500000000000,
            'available': 500000000000,
            'free': 500000000000
        }
        mock_warez_usage.return_value = None
        
        mock_system_info.return_value = {'OS': 'Linux'}
        mock_config_values.return_value = {'DATABASE_URL': 'postgresql://...'}
        mock_active_users.return_value = []
        
        # Mock log info with None latest log
        mock_log_info.return_value = {'count': 0, 'latest': None}
        mock_system_uptime.return_value = '1 hour'
        mock_app_uptime.return_value = '30 minutes'
        mock_format_bytes.side_effect = lambda x: f"{x} bytes"

        with patch('flask_login.utils._get_user', return_value=admin_user):
            response = client.get('/admin/server_status_page')
            
        assert response.status_code == 200
        
        # Verify format_bytes was only called for non-None usage values
        # Should only format disk_usage keys (4 calls)
        assert mock_format_bytes.call_count == 4


class TestRouteIntegration:
    """Test route integration and blueprint registration."""

    def test_info_blueprint_registration(self, app):
        """Test that the info blueprint is registered correctly."""
        with app.app_context():
            # Check that the route exists
            rules = [rule.rule for rule in app.url_map.iter_rules()]
            assert '/admin/server_status_page' in rules

    def test_info_blueprint_context_processor(self, app):
        """Test that the info blueprint context processor is registered."""
        with app.app_context():
            from modules.routes_info import info_bp
            
            # Check that context processor is registered
            assert hasattr(info_bp, 'context_processor')


class TestUtilityFunctionIntegration:
    """Test integration with utility functions."""

    def test_format_bytes_integration(self, app):
        """Test format_bytes function integration."""
        from modules.routes_info import format_bytes
        
        # Test various byte values
        assert format_bytes(1024) is not None
        assert format_bytes(1048576) is not None
        assert format_bytes(0) is not None

    def test_app_version_import(self, app):
        """Test that app_version is imported correctly."""
        from modules.routes_info import app_version
        
        assert app_version is not None
        assert isinstance(app_version, str)

    def test_app_start_time_import(self, app):
        """Test that app_start_time is imported correctly."""
        from modules.routes_info import app_start_time
        
        assert app_start_time is not None
        assert isinstance(app_start_time, datetime)


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch('modules.routes_info.check_server_settings')
    @patch('modules.routes_info.current_user')
    def test_server_settings_check_failure(self, mock_current_user,
                                          mock_check_server_settings,
                                          client, admin_user):
        """Test handling when server settings check fails."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.id = admin_user.id
        
        mock_check_server_settings.return_value = (False, "Configuration error")

        with patch('flask_login.utils._get_user', return_value=admin_user):
            response = client.get('/admin/server_status_page')
            
        assert response.status_code == 302

    @patch('modules.routes_info.check_server_settings')
    @patch('modules.routes_info.get_system_info')
    @patch('modules.routes_info.current_user')
    def test_system_info_exception(self, mock_current_user,
                                 mock_get_system_info,
                                 mock_check_server_settings,
                                 client, admin_user):
        """Test handling when system info gathering fails."""
        mock_current_user.is_authenticated = True
        mock_current_user.role = 'admin'
        mock_current_user.id = admin_user.id
        
        mock_check_server_settings.return_value = (True, None)
        mock_get_system_info.side_effect = Exception("Failed to get system info")

        with patch('flask_login.utils._get_user', return_value=admin_user):
            response = client.get('/admin/server_status_page')
            
        assert response.status_code == 302