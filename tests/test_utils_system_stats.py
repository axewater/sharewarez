import pytest
import os
from unittest.mock import patch, MagicMock, mock_open
from modules.utils_system_stats import (
    get_cpu_usage,
    get_memory_usage,
    get_disk_usage,
    get_warez_folder_usage,
    format_bytes,
    get_process_count,
    get_open_files
)


class TestGetCpuUsage:
    """Tests for get_cpu_usage function."""

    @patch('modules.utils_system_stats.psutil.cpu_count')
    @patch('modules.utils_system_stats.psutil.cpu_percent')
    def test_get_cpu_usage_success(self, mock_cpu_percent, mock_cpu_count):
        """Test successful CPU usage retrieval."""
        # Setup mocks
        mock_cpu_percent.return_value = 45.2
        mock_cpu_count.side_effect = lambda logical=True: 8 if logical else 4
        
        result = get_cpu_usage()
        
        assert result is not None
        assert result['percent'] == 45.2
        assert result['cores_physical'] == 4
        assert result['cores_logical'] == 8
        
        # Verify CPU percent was called with interval=1
        mock_cpu_percent.assert_called_once_with(interval=1)
        
        # Verify CPU count was called for both logical and physical cores
        assert mock_cpu_count.call_count == 2
        mock_cpu_count.assert_any_call(logical=False)
        mock_cpu_count.assert_any_call(logical=True)

    @patch('modules.utils_system_stats.psutil.cpu_count')
    @patch('modules.utils_system_stats.psutil.cpu_percent')
    @patch('builtins.print')
    def test_get_cpu_usage_exception(self, mock_print, mock_cpu_percent, mock_cpu_count):
        """Test CPU usage retrieval with exception."""
        # Make psutil.cpu_percent raise an exception
        mock_cpu_percent.side_effect = Exception('CPU error')
        
        result = get_cpu_usage()
        
        assert result is None
        mock_print.assert_called_once()
        assert 'Error getting CPU usage' in str(mock_print.call_args)


class TestGetMemoryUsage:
    """Tests for get_memory_usage function."""

    @patch('modules.utils_system_stats.psutil.virtual_memory')
    def test_get_memory_usage_success(self, mock_virtual_memory):
        """Test successful memory usage retrieval."""
        # Create mock memory object
        mock_memory = MagicMock()
        mock_memory.total = 16777216000  # 16 GB
        mock_memory.available = 8388608000  # 8 GB
        mock_memory.used = 8388608000  # 8 GB
        mock_memory.percent = 50.0
        mock_virtual_memory.return_value = mock_memory
        
        result = get_memory_usage()
        
        assert result is not None
        assert result['total'] == 16777216000
        assert result['available'] == 8388608000
        assert result['used'] == 8388608000
        assert result['percent'] == 50.0
        
        mock_virtual_memory.assert_called_once()

    @patch('modules.utils_system_stats.psutil.virtual_memory')
    @patch('builtins.print')
    def test_get_memory_usage_exception(self, mock_print, mock_virtual_memory):
        """Test memory usage retrieval with exception."""
        mock_virtual_memory.side_effect = Exception('Memory error')
        
        result = get_memory_usage()
        
        assert result is None
        mock_print.assert_called_once()
        assert 'Error getting memory usage' in str(mock_print.call_args)


class TestGetDiskUsage:
    """Tests for get_disk_usage function."""

    @patch('modules.utils_system_stats.psutil.disk_usage')
    @patch('modules.utils_system_stats.os.path.exists')
    @patch('modules.utils_system_stats.os.name', 'posix')
    def test_get_disk_usage_success_posix(self, mock_exists, mock_disk_usage):
        """Test successful disk usage retrieval on POSIX systems."""
        mock_exists.return_value = True
        
        # Create mock disk usage object
        mock_disk = MagicMock()
        mock_disk.total = 1073741824000  # 1 TB
        mock_disk.used = 536870912000  # 500 GB
        mock_disk.free = 536870912000  # 500 GB
        mock_disk.percent = 50.0
        mock_disk_usage.return_value = mock_disk
        
        with patch('modules.utils_system_stats.Config') as mock_config:
            mock_config.BASE_FOLDER_POSIX = '/test/posix/path'
            
            result = get_disk_usage()
            
            assert result is not None
            assert result['total'] == 1073741824000
            assert result['used'] == 536870912000
            assert result['free'] == 536870912000
            assert result['percent'] == 50.0
            
            mock_exists.assert_called_once_with('/test/posix/path')
            mock_disk_usage.assert_called_once_with('/test/posix/path')

    @patch('modules.utils_system_stats.psutil.disk_usage')
    @patch('modules.utils_system_stats.os.path.exists')
    @patch('modules.utils_system_stats.os.name', 'nt')
    def test_get_disk_usage_success_windows(self, mock_exists, mock_disk_usage):
        """Test successful disk usage retrieval on Windows systems."""
        mock_exists.return_value = True
        
        mock_disk = MagicMock()
        mock_disk.total = 2147483648000  # 2 TB
        mock_disk.used = 1073741824000  # 1 TB
        mock_disk.free = 1073741824000  # 1 TB
        mock_disk.percent = 50.0
        mock_disk_usage.return_value = mock_disk
        
        with patch('modules.utils_system_stats.Config') as mock_config:
            mock_config.BASE_FOLDER_WINDOWS = 'C:\\test\\windows\\path'
            
            result = get_disk_usage()
            
            assert result is not None
            assert result['total'] == 2147483648000
            assert result['used'] == 1073741824000
            assert result['free'] == 1073741824000
            assert result['percent'] == 50.0
            
            mock_exists.assert_called_once_with('C:\\test\\windows\\path')
            mock_disk_usage.assert_called_once_with('C:\\test\\windows\\path')

    @patch('modules.utils_system_stats.os.path.exists')
    def test_get_disk_usage_path_not_exists(self, mock_exists):
        """Test disk usage when base path doesn't exist."""
        mock_exists.return_value = False
        
        with patch('modules.utils_system_stats.Config') as mock_config:
            mock_config.BASE_FOLDER_POSIX = '/nonexistent/path'
            
            result = get_disk_usage()
            
            assert result is None
            mock_exists.assert_called_once_with('/nonexistent/path')

    @patch('modules.utils_system_stats.psutil.disk_usage')
    @patch('modules.utils_system_stats.os.path.exists')
    @patch('builtins.print')
    def test_get_disk_usage_exception(self, mock_print, mock_exists, mock_disk_usage):
        """Test disk usage retrieval with exception."""
        mock_exists.return_value = True
        mock_disk_usage.side_effect = Exception('Disk error')
        
        with patch('modules.utils_system_stats.Config') as mock_config:
            mock_config.BASE_FOLDER_POSIX = '/test/path'
            
            result = get_disk_usage()
            
            assert result is None
            mock_print.assert_called_once()
            assert 'Error getting disk usage' in str(mock_print.call_args)


class TestGetWarezFolderUsage:
    """Tests for get_warez_folder_usage function."""

    @patch('modules.utils_system_stats.psutil.disk_usage')
    @patch('modules.utils_system_stats.os.path.exists')
    def test_get_warez_folder_usage_success(self, mock_exists, mock_disk_usage):
        """Test successful warez folder usage retrieval."""
        mock_exists.return_value = True
        
        mock_disk = MagicMock()
        mock_disk.total = 5497558138880  # 5 TB
        mock_disk.used = 2748779069440  # 2.5 TB
        mock_disk.free = 2748779069440  # 2.5 TB
        mock_disk.percent = 50.0
        mock_disk_usage.return_value = mock_disk
        
        with patch('modules.utils_system_stats.Config') as mock_config:
            mock_config.DATA_FOLDER_WAREZ = '/warez/folder/path'
            
            result = get_warez_folder_usage()
            
            assert result is not None
            assert result['total'] == 5497558138880
            assert result['used'] == 2748779069440
            assert result['free'] == 2748779069440
            assert result['percent'] == 50.0
            
            mock_exists.assert_called_once_with('/warez/folder/path')
            mock_disk_usage.assert_called_once_with('/warez/folder/path')

    @patch('modules.utils_system_stats.os.path.exists')
    def test_get_warez_folder_usage_path_not_exists(self, mock_exists):
        """Test warez folder usage when path doesn't exist."""
        mock_exists.return_value = False
        
        with patch('modules.utils_system_stats.Config') as mock_config:
            mock_config.DATA_FOLDER_WAREZ = '/nonexistent/warez/path'
            
            result = get_warez_folder_usage()
            
            assert result is None
            mock_exists.assert_called_once_with('/nonexistent/warez/path')

    @patch('modules.utils_system_stats.psutil.disk_usage')
    @patch('modules.utils_system_stats.os.path.exists')
    @patch('builtins.print')
    def test_get_warez_folder_usage_exception(self, mock_print, mock_exists, mock_disk_usage):
        """Test warez folder usage retrieval with exception."""
        mock_exists.return_value = True
        mock_disk_usage.side_effect = Exception('Warez disk error')
        
        with patch('modules.utils_system_stats.Config') as mock_config:
            mock_config.DATA_FOLDER_WAREZ = '/warez/path'
            
            result = get_warez_folder_usage()
            
            assert result is None
            mock_print.assert_called_once()
            assert 'Error getting warez folder disk usage' in str(mock_print.call_args)


class TestFormatBytes:
    """Tests for format_bytes function."""

    def test_format_bytes_none(self):
        """Test format_bytes with None input."""
        result = format_bytes(None)
        assert result == "N/A"

    def test_format_bytes_bytes(self):
        """Test format_bytes with values in bytes."""
        assert format_bytes(0) == "0.00 B"
        assert format_bytes(512) == "512.00 B"
        assert format_bytes(1023) == "1023.00 B"

    def test_format_bytes_kilobytes(self):
        """Test format_bytes with values in kilobytes."""
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1536) == "1.50 KB"
        assert format_bytes(1047552) == "1023.00 KB"  # 1023 * 1024

    def test_format_bytes_megabytes(self):
        """Test format_bytes with values in megabytes."""
        assert format_bytes(1048576) == "1.00 MB"
        assert format_bytes(1572864) == "1.50 MB"
        assert format_bytes(1072693248) == "1023.00 MB"  # 1023 * 1024 * 1024

    def test_format_bytes_gigabytes(self):
        """Test format_bytes with values in gigabytes."""
        assert format_bytes(1073741824) == "1.00 GB"
        assert format_bytes(1610612736) == "1.50 GB"
        assert format_bytes(1098437885952) == "1023.00 GB"  # 1023 * 1024^3

    def test_format_bytes_terabytes(self):
        """Test format_bytes with values in terabytes."""
        assert format_bytes(1099511627776) == "1.00 TB"
        assert format_bytes(1649267441664) == "1.50 TB"
        assert format_bytes(1124800395214848) == "1023.00 TB"  # 1023 * 1024^4

    def test_format_bytes_petabytes(self):
        """Test format_bytes with values in petabytes."""
        assert format_bytes(1125899906842624) == "1.00 PB"
        assert format_bytes(1688849860263936) == "1.50 PB"

    def test_format_bytes_edge_cases(self):
        """Test format_bytes with edge cases."""
        # Very small values
        assert format_bytes(1) == "1.00 B"
        
        # Exact boundaries
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1024 * 1024) == "1.00 MB"
        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        assert format_bytes(1024 * 1024 * 1024 * 1024) == "1.00 TB"


class TestGetProcessCount:
    """Tests for get_process_count function."""

    @patch('modules.utils_system_stats.psutil.pids')
    def test_get_process_count_success(self, mock_pids):
        """Test successful process count retrieval."""
        mock_pids.return_value = [1, 2, 3, 4, 5, 100, 200, 300, 400, 500]
        
        result = get_process_count()
        
        assert result == 10
        mock_pids.assert_called_once()

    @patch('modules.utils_system_stats.psutil.pids')
    def test_get_process_count_empty_list(self, mock_pids):
        """Test process count with empty PID list."""
        mock_pids.return_value = []
        
        result = get_process_count()
        
        assert result == 0
        mock_pids.assert_called_once()

    @patch('modules.utils_system_stats.psutil.pids')
    @patch('builtins.print')
    def test_get_process_count_exception(self, mock_print, mock_pids):
        """Test process count retrieval with exception."""
        mock_pids.side_effect = Exception('Process error')
        
        result = get_process_count()
        
        assert result is None
        mock_print.assert_called_once()
        assert 'Error getting process count' in str(mock_print.call_args)


class TestGetOpenFiles:
    """Tests for get_open_files function."""

    @patch('modules.utils_system_stats.platform.system')
    @patch('builtins.open', new_callable=mock_open, read_data='1024\t0\t2048')
    def test_get_open_files_linux_success(self, mock_file, mock_system):
        """Test successful open files count on Linux."""
        mock_system.return_value = 'Linux'
        
        result = get_open_files()
        
        assert result == 1024
        mock_file.assert_called_once_with('/proc/sys/fs/file-nr')
        mock_system.assert_called_once()

    @patch('modules.utils_system_stats.platform.system')
    @patch('modules.utils_system_stats.psutil.Process')
    def test_get_open_files_windows_success(self, mock_process_class, mock_system):
        """Test successful open files count on Windows."""
        mock_system.return_value = 'Windows'
        
        # Mock Process instance and its open_files method
        mock_process = MagicMock()
        mock_process.open_files.return_value = ['file1', 'file2', 'file3', 'file4', 'file5']
        mock_process_class.return_value = mock_process
        
        result = get_open_files()
        
        assert result == 5
        mock_system.assert_called_once()
        mock_process_class.assert_called_once()
        mock_process.open_files.assert_called_once()

    @patch('modules.utils_system_stats.platform.system')
    @patch('builtins.open', new_callable=mock_open)
    @patch('builtins.print')
    def test_get_open_files_linux_exception(self, mock_print, mock_file, mock_system):
        """Test open files count on Linux with exception."""
        mock_system.return_value = 'Linux'
        mock_file.side_effect = Exception('File read error')
        
        result = get_open_files()
        
        assert result is None
        mock_print.assert_called_once()
        assert 'Error getting open files count' in str(mock_print.call_args)

    @patch('modules.utils_system_stats.platform.system')
    @patch('modules.utils_system_stats.psutil.Process')
    @patch('builtins.print')
    def test_get_open_files_windows_exception(self, mock_print, mock_process_class, mock_system):
        """Test open files count on Windows with exception."""
        mock_system.return_value = 'Windows'
        mock_process_class.side_effect = Exception('Process error')
        
        result = get_open_files()
        
        assert result is None
        mock_print.assert_called_once()
        assert 'Error getting open files count' in str(mock_print.call_args)

    @patch('modules.utils_system_stats.platform.system')
    @patch('modules.utils_system_stats.psutil.Process')
    def test_get_open_files_other_platform(self, mock_process_class, mock_system):
        """Test open files count on other platforms (non-Linux/Windows)."""
        mock_system.return_value = 'Darwin'  # macOS
        
        mock_process = MagicMock()
        mock_process.open_files.return_value = ['file1', 'file2']
        mock_process_class.return_value = mock_process
        
        result = get_open_files()
        
        assert result == 2
        mock_system.assert_called_once()
        mock_process_class.assert_called_once()
        mock_process.open_files.assert_called_once()