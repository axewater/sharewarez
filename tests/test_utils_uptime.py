import pytest
import platform
import sys
from datetime import datetime, timedelta
from unittest.mock import patch, mock_open, MagicMock
from modules.utils_uptime import (
    get_system_uptime,
    format_uptime,
    get_formatted_system_uptime,
    get_formatted_app_uptime
)


class TestGetSystemUptime:
    """Test system uptime detection functionality."""
    
    @patch('platform.system', return_value='Linux')
    @patch('builtins.open', new_callable=mock_open, read_data='12345.67 98765.43\n')
    def test_get_system_uptime_unix_success(self, mock_file, mock_platform):
        """Test successful uptime retrieval on Unix-like systems."""
        result = get_system_uptime()
        
        assert result == 12345.67
        mock_file.assert_called_once_with('/proc/uptime', 'r')
    
    @patch('platform.system', return_value='Windows')
    def test_get_system_uptime_windows_success(self, mock_platform):
        """Test successful uptime retrieval on Windows systems."""
        # Mock the ctypes module and windll
        mock_windll = MagicMock()
        mock_windll.kernel32.GetTickCount64.return_value = 3600000  # 1 hour in milliseconds
        
        with patch.dict('sys.modules', {'ctypes': MagicMock(windll=mock_windll)}):
            result = get_system_uptime()
        
        assert result == 3600.0  # Should be converted to seconds
        mock_windll.kernel32.GetTickCount64.assert_called_once()
    
    @patch('platform.system', return_value='Linux')
    @patch('builtins.open', side_effect=FileNotFoundError("No such file"))
    @patch('builtins.print')  # Suppress error output
    def test_get_system_uptime_unix_file_not_found(self, mock_print, mock_file, mock_platform):
        """Test uptime retrieval when /proc/uptime is not available."""
        result = get_system_uptime()
        
        assert result is None
        mock_file.assert_called_once_with('/proc/uptime', 'r')
        mock_print.assert_called_once_with("Error getting system uptime: No such file")
    
    @patch('platform.system', return_value='Linux')
    @patch('builtins.open', new_callable=mock_open, read_data='invalid_data\n')
    @patch('builtins.print')  # Suppress error output
    def test_get_system_uptime_unix_invalid_data(self, mock_print, mock_file, mock_platform):
        """Test uptime retrieval with invalid data in /proc/uptime."""
        result = get_system_uptime()
        
        assert result is None
        mock_file.assert_called_once_with('/proc/uptime', 'r')
        # Should print error about ValueError when converting to float
        mock_print.assert_called_once()
    
    @patch('platform.system', return_value='Windows')
    @patch('builtins.print')  # Suppress error output  
    def test_get_system_uptime_windows_ctypes_error(self, mock_print, mock_platform):
        """Test uptime retrieval when ctypes import fails on Windows."""
        # Mock the import to fail
        with patch('builtins.__import__', side_effect=ImportError("No module named 'ctypes'")):
            result = get_system_uptime()
        
        assert result is None
        mock_print.assert_called_once_with("Error getting system uptime: No module named 'ctypes'")
    
    @patch('platform.system', return_value='Darwin')  # macOS
    @patch('builtins.open', side_effect=FileNotFoundError("No such file"))
    @patch('builtins.print')  # Suppress error output
    def test_get_system_uptime_unsupported_platform(self, mock_print, mock_file, mock_platform):
        """Test uptime retrieval on unsupported platform (macOS without /proc/uptime)."""
        result = get_system_uptime()
        
        assert result is None
        mock_file.assert_called_once_with('/proc/uptime', 'r')
        mock_print.assert_called_once_with("Error getting system uptime: No such file")


class TestFormatUptime:
    """Test uptime formatting functionality."""
    
    def test_format_uptime_none_input(self):
        """Test formatting when input is None."""
        result = format_uptime(None)
        assert result == "Unavailable"
    
    def test_format_uptime_less_than_minute(self):
        """Test formatting for uptime less than 1 minute."""
        result = format_uptime(30)  # 30 seconds
        assert result == "Less than 1 minute"
        
        result = format_uptime(0)  # 0 seconds
        assert result == "Less than 1 minute"
    
    def test_format_uptime_minutes_only(self):
        """Test formatting for uptime in minutes only."""
        result = format_uptime(120)  # 2 minutes
        assert result == "2 minutes"
        
        result = format_uptime(60)  # 1 minute
        assert result == "1 minute"
    
    def test_format_uptime_hours_and_minutes(self):
        """Test formatting for uptime with hours and minutes."""
        result = format_uptime(3661)  # 1 hour, 1 minute, 1 second
        assert result == "1 hour, 1 minute"
        
        result = format_uptime(7320)  # 2 hours, 2 minutes
        assert result == "2 hours, 2 minutes"
    
    def test_format_uptime_days_hours_minutes(self):
        """Test formatting for uptime with days, hours, and minutes."""
        result = format_uptime(90061)  # 1 day, 1 hour, 1 minute, 1 second
        assert result == "1 day, 1 hour, 1 minute"
        
        result = format_uptime(180122)  # 2 days, 2 hours, 2 minutes, 2 seconds
        assert result == "2 days, 2 hours, 2 minutes"
    
    def test_format_uptime_days_only(self):
        """Test formatting for uptime with only days (no hours/minutes)."""
        result = format_uptime(86400)  # Exactly 1 day
        assert result == "1 day"
        
        result = format_uptime(172800)  # Exactly 2 days
        assert result == "2 days"
    
    def test_format_uptime_hours_only(self):
        """Test formatting for uptime with only hours (no days, no minutes)."""
        result = format_uptime(3600)  # Exactly 1 hour
        assert result == "1 hour"
        
        result = format_uptime(7200)  # Exactly 2 hours
        assert result == "2 hours"
    
    def test_format_uptime_days_and_minutes_no_hours(self):
        """Test formatting for uptime with days and minutes but no hours."""
        result = format_uptime(86460)  # 1 day and 1 minute
        assert result == "1 day, 1 minute"
    
    def test_format_uptime_large_values(self):
        """Test formatting for very large uptime values."""
        result = format_uptime(2592061)  # 30 days, 1 minute, 1 second (no full hour)
        assert result == "30 days, 1 minute"
    
    def test_format_uptime_floating_point_input(self):
        """Test formatting with floating point input."""
        result = format_uptime(3661.5)  # 1 hour, 1 minute, 1.5 seconds
        assert result == "1 hour, 1 minute"
        
        result = format_uptime(59.9)  # Almost 1 minute
        assert result == "Less than 1 minute"


class TestGetFormattedSystemUptime:
    """Test formatted system uptime functionality."""
    
    @patch('modules.utils_uptime.get_system_uptime', return_value=3661)
    def test_get_formatted_system_uptime_success(self, mock_get_uptime):
        """Test successful formatted system uptime retrieval."""
        result = get_formatted_system_uptime()
        
        assert result == "1 hour, 1 minute"
        mock_get_uptime.assert_called_once()
    
    @patch('modules.utils_uptime.get_system_uptime', return_value=None)
    def test_get_formatted_system_uptime_failure(self, mock_get_uptime):
        """Test formatted system uptime when get_system_uptime fails."""
        result = get_formatted_system_uptime()
        
        assert result == "Unavailable"
        mock_get_uptime.assert_called_once()
    
    @patch('modules.utils_uptime.get_system_uptime', return_value=30)
    def test_get_formatted_system_uptime_short_duration(self, mock_get_uptime):
        """Test formatted system uptime for short durations."""
        result = get_formatted_system_uptime()
        
        assert result == "Less than 1 minute"
        mock_get_uptime.assert_called_once()


class TestGetFormattedAppUptime:
    """Test formatted application uptime functionality."""
    
    def test_get_formatted_app_uptime_success(self):
        """Test successful formatted app uptime calculation."""
        # Create a start time 1 hour, 1 minute, 1 second ago
        start_time = datetime.now() - timedelta(seconds=3661)
        
        result = get_formatted_app_uptime(start_time)
        
        # Should be approximately "1 hour, 1 minute" (allowing for small timing differences)
        assert "1 hour" in result
        assert "1 minute" in result or "0 minutes" in result  # Account for timing precision
    
    def test_get_formatted_app_uptime_short_duration(self):
        """Test formatted app uptime for short durations."""
        # Create a start time 30 seconds ago
        start_time = datetime.now() - timedelta(seconds=30)
        
        result = get_formatted_app_uptime(start_time)
        
        assert result == "Less than 1 minute"
    
    def test_get_formatted_app_uptime_invalid_input_none(self):
        """Test formatted app uptime with None input."""
        result = get_formatted_app_uptime(None)
        
        assert result == "Unavailable"
    
    def test_get_formatted_app_uptime_invalid_input_string(self):
        """Test formatted app uptime with string input."""
        result = get_formatted_app_uptime("not a datetime")
        
        assert result == "Unavailable"
    
    def test_get_formatted_app_uptime_invalid_input_number(self):
        """Test formatted app uptime with numeric input."""
        result = get_formatted_app_uptime(12345)
        
        assert result == "Unavailable"
    
    def test_get_formatted_app_uptime_future_time(self):
        """Test formatted app uptime with future start time."""
        # Create a start time 1 hour in the future
        future_time = datetime.now() + timedelta(hours=1)
        
        result = get_formatted_app_uptime(future_time)
        
        # The function formats negative durations as the absolute value
        # so 1 hour future becomes 1 hour uptime  
        assert "hour" in result
    
    def test_get_formatted_app_uptime_long_duration(self):
        """Test formatted app uptime for long durations."""
        # Create a start time 2 days, 3 hours, 4 minutes ago
        start_time = datetime.now() - timedelta(days=2, hours=3, minutes=4, seconds=30)
        
        result = get_formatted_app_uptime(start_time)
        
        assert "2 days" in result
        assert "3 hours" in result
        assert "4 minutes" in result


class TestIntegration:
    """Integration tests for uptime utility functions."""
    
    @patch('platform.system', return_value='Linux')
    @patch('builtins.open', new_callable=mock_open, read_data='3661.5 98765.43\n')
    def test_full_system_uptime_workflow(self, mock_file, mock_platform):
        """Test complete system uptime workflow from raw data to formatted string."""
        result = get_formatted_system_uptime()
        
        assert result == "1 hour, 1 minute"
        mock_file.assert_called_once_with('/proc/uptime', 'r')
    
    def test_full_app_uptime_workflow(self):
        """Test complete app uptime workflow with real datetime objects."""
        # Create a precise start time
        start_time = datetime.now() - timedelta(days=1, hours=1, minutes=1, seconds=30)
        
        result = get_formatted_app_uptime(start_time)
        
        # Should contain 1 day and 1 hour (allowing for timing variations)
        assert "1 day" in result
        assert "1 hour" in result