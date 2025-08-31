import pytest
import socket
import ssl
import smtplib
from unittest.mock import patch, MagicMock, call
from modules.utils_smtp_test import SMTPTester, main


class TestSMTPTesterInit:
    """Test SMTPTester class initialization."""
    
    def test_init_default_debug_false(self):
        """Test SMTPTester initialization with default debug=False."""
        tester = SMTPTester()
        assert tester.debug is False
    
    def test_init_debug_true(self):
        """Test SMTPTester initialization with debug=True."""
        tester = SMTPTester(debug=True)
        assert tester.debug is True
    
    def test_init_debug_false_explicit(self):
        """Test SMTPTester initialization with explicit debug=False."""
        tester = SMTPTester(debug=False)
        assert tester.debug is False


class TestSMTPTesterConnection:
    """Test SMTPTester test_connection method."""
    
    @pytest.fixture
    def tester(self):
        """Create SMTPTester instance for testing."""
        return SMTPTester()
    
    @pytest.fixture
    def mock_smtp(self):
        """Create a mock SMTP instance with common setup."""
        mock_smtp = MagicMock()
        mock_smtp.ehlo.return_value = (b'250 Hello', 'additional info')
        mock_smtp.esmtp_features = {
            'STARTTLS': 'STARTTLS',
            'auth': 'PLAIN LOGIN',
            'size': '35882577',
            'PIPELINING': 'PIPELINING',
            '8BITMIME': '8BITMIME'
        }
        mock_smtp.has_extn.return_value = True
        return mock_smtp

    @patch('modules.utils_smtp_test.log_system_event')
    @patch('modules.utils_smtp_test.socket.create_connection')
    @patch('modules.utils_smtp_test.smtplib.SMTP')
    def test_connection_success_basic(self, mock_smtp_class, mock_socket, mock_log, tester, mock_smtp):
        """Test successful basic connection without authentication."""
        # Setup mocks
        mock_socket.return_value.close.return_value = None
        mock_smtp_class.return_value = mock_smtp
        
        # Test
        success, result = tester.test_connection('smtp.example.com', 587)
        
        # Verify
        assert success is True
        assert isinstance(result, dict)
        assert result['status'] == 'Connection successful'
        assert result['auth_status'] == 'No authentication attempted'
        assert 'capabilities' in result
        assert 'server_greeting' in result
        
        # Verify socket connection was tested
        mock_socket.assert_called_once_with(('smtp.example.com', 587), timeout=10)
        
        # Verify SMTP calls
        mock_smtp_class.assert_called_once_with('smtp.example.com', 587, timeout=10)
        mock_smtp.ehlo.assert_called()
        mock_smtp.quit.assert_called()
        
        # Verify logging
        mock_log.assert_called_once_with(
            'SMTP test successful for smtp.example.com:587',
            event_type='test',
            event_level='information'
        )

    @patch('modules.utils_smtp_test.log_system_event')
    @patch('modules.utils_smtp_test.socket.create_connection')
    @patch('modules.utils_smtp_test.smtplib.SMTP')
    def test_connection_success_with_auth(self, mock_smtp_class, mock_socket, mock_log, tester, mock_smtp):
        """Test successful connection with authentication."""
        # Setup mocks
        mock_socket.return_value.close.return_value = None
        mock_smtp_class.return_value = mock_smtp
        mock_smtp.login.return_value = None
        
        # Test
        success, result = tester.test_connection(
            'smtp.example.com', 587, 
            username='testuser', 
            password='testpass'
        )
        
        # Verify
        assert success is True
        assert result['auth_status'] == 'Authentication successful'
        mock_smtp.login.assert_called_once_with('testuser', 'testpass')

    @patch('modules.utils_smtp_test.log_system_event')
    @patch('modules.utils_smtp_test.socket.create_connection')
    @patch('modules.utils_smtp_test.smtplib.SMTP')
    @patch('modules.utils_smtp_test.ssl.create_default_context')
    def test_connection_success_with_tls(self, mock_ssl_context, mock_smtp_class, mock_socket, mock_log, tester, mock_smtp):
        """Test successful connection with TLS."""
        # Setup mocks
        mock_socket.return_value.close.return_value = None
        mock_smtp_class.return_value = mock_smtp
        mock_context = MagicMock()
        mock_ssl_context.return_value = mock_context
        
        # Test
        success, result = tester.test_connection('smtp.example.com', 587, use_tls=True)
        
        # Verify
        assert success is True
        mock_smtp.has_extn.assert_called_with('STARTTLS')
        mock_smtp.starttls.assert_called_once_with(context=mock_context)
        # EHLO should be called twice: once initially, once after STARTTLS
        assert mock_smtp.ehlo.call_count == 2

    @patch('modules.utils_smtp_test.log_system_event')
    @patch('modules.utils_smtp_test.socket.create_connection')
    @patch('modules.utils_smtp_test.smtplib.SMTP')
    def test_connection_no_tls(self, mock_smtp_class, mock_socket, mock_log, tester, mock_smtp):
        """Test connection with TLS disabled."""
        # Setup mocks
        mock_socket.return_value.close.return_value = None
        mock_smtp_class.return_value = mock_smtp
        
        # Test
        success, result = tester.test_connection('smtp.example.com', 587, use_tls=False)
        
        # Verify
        assert success is True
        mock_smtp.has_extn.assert_not_called()
        mock_smtp.starttls.assert_not_called()

    @patch('modules.utils_smtp_test.socket.create_connection')
    @patch('modules.utils_smtp_test.smtplib.SMTP')
    def test_connection_starttls_not_supported(self, mock_smtp_class, mock_socket, tester, mock_smtp):
        """Test connection when STARTTLS is not supported by server."""
        # Setup mocks
        mock_socket.return_value.close.return_value = None
        mock_smtp_class.return_value = mock_smtp
        mock_smtp.has_extn.return_value = False
        
        # Test
        success, result = tester.test_connection('smtp.example.com', 587, use_tls=True)
        
        # Verify
        assert success is False
        assert result == "STARTTLS not supported by server (not found in extensions)"

    @patch('modules.utils_smtp_test.socket.create_connection')
    @patch('modules.utils_smtp_test.smtplib.SMTP')
    def test_connection_auth_failure(self, mock_smtp_class, mock_socket, tester, mock_smtp):
        """Test connection with authentication failure."""
        # Setup mocks
        mock_socket.return_value.close.return_value = None
        mock_smtp_class.return_value = mock_smtp
        mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, 'Authentication failed')
        
        # Test
        success, result = tester.test_connection(
            'smtp.example.com', 587,
            username='testuser',
            password='wrongpass'
        )
        
        # Verify
        assert success is False
        assert result == "Authentication failed - invalid credentials"

    @patch('modules.utils_smtp_test.socket.create_connection')
    def test_connection_socket_timeout(self, mock_socket, tester):
        """Test connection with socket timeout."""
        # Setup mock to raise timeout
        mock_socket.side_effect = socket.timeout()
        
        # Test
        success, result = tester.test_connection('smtp.example.com', 587)
        
        # Verify
        assert success is False
        assert result == "Connection timed out"

    @patch('modules.utils_smtp_test.socket.create_connection')
    def test_connection_dns_failure(self, mock_socket, tester):
        """Test connection with DNS lookup failure."""
        # Setup mock to raise DNS error
        mock_socket.side_effect = socket.gaierror()
        
        # Test
        success, result = tester.test_connection('invalid.example.com', 587)
        
        # Verify
        assert success is False
        assert result == "DNS lookup failed"

    @patch('modules.utils_smtp_test.socket.create_connection')
    def test_connection_ssl_error(self, mock_socket, tester):
        """Test connection with SSL/TLS error."""
        # Setup mock to raise SSL error during socket connection
        mock_socket.side_effect = ssl.SSLError("SSL handshake failed")
        
        # Test
        success, result = tester.test_connection('smtp.example.com', 587, use_tls=True)
        
        # Verify
        assert success is False
        # The SSL error message might be formatted as a tuple by str()
        assert "SSL/TLS error:" in result and "SSL handshake failed" in result

    @patch('modules.utils_smtp_test.log_system_event')
    @patch('modules.utils_smtp_test.socket.create_connection')
    @patch('modules.utils_smtp_test.smtplib.SMTP')
    def test_connection_smtp_exception(self, mock_smtp_class, mock_socket, mock_log, tester, mock_smtp):
        """Test connection with SMTP protocol exception."""
        # Setup mocks
        mock_socket.return_value.close.return_value = None
        mock_smtp_class.return_value = mock_smtp
        mock_smtp.ehlo.side_effect = smtplib.SMTPException("Protocol error")
        
        # Test
        success, result = tester.test_connection('smtp.example.com', 587)
        
        # Verify
        assert success is False
        assert result == "SMTP error: Protocol error"
        
        # Verify failure logging
        mock_log.assert_called_once_with(
            'SMTP test failed for smtp.example.com:587',
            event_type='test',
            event_level='information'
        )

    @patch('modules.utils_smtp_test.socket.create_connection')
    def test_connection_unexpected_error(self, mock_socket, tester):
        """Test connection with unexpected error."""
        # Setup mock to raise unexpected exception
        mock_socket.side_effect = ValueError("Unexpected error")
        
        # Test
        success, result = tester.test_connection('smtp.example.com', 587)
        
        # Verify
        assert success is False
        assert result == "Unexpected error: Unexpected error"

    def test_connection_debug_mode(self, tester):
        """Test that debug mode enables SMTP debug output."""
        debug_tester = SMTPTester(debug=True)
        
        with patch('modules.utils_smtp_test.socket.create_connection') as mock_socket, \
             patch('modules.utils_smtp_test.smtplib.SMTP') as mock_smtp_class:
            
            mock_socket.return_value.close.return_value = None
            mock_smtp = MagicMock()
            mock_smtp.ehlo.return_value = (b'250 Hello', 'additional info')
            mock_smtp.esmtp_features = {}
            mock_smtp_class.return_value = mock_smtp
            
            # Test
            debug_tester.test_connection('smtp.example.com', 587)
            
            # Verify debug was enabled
            mock_smtp.set_debuglevel.assert_called_once_with(1)

    @patch('modules.utils_smtp_test.socket.create_connection')
    @patch('modules.utils_smtp_test.smtplib.SMTP')
    def test_connection_custom_timeout(self, mock_smtp_class, mock_socket, tester):
        """Test connection with custom timeout."""
        # Setup mocks
        mock_socket.return_value.close.return_value = None
        mock_smtp = MagicMock()
        mock_smtp.ehlo.return_value = (b'250 Hello', 'additional info')
        mock_smtp.esmtp_features = {}
        mock_smtp_class.return_value = mock_smtp
        
        # Test
        tester.test_connection('smtp.example.com', 587, timeout=30)
        
        # Verify timeout was used
        mock_socket.assert_called_once_with(('smtp.example.com', 587), timeout=30)
        mock_smtp_class.assert_called_once_with('smtp.example.com', 587, timeout=30)

    @patch('modules.utils_smtp_test.log_system_event')
    @patch('modules.utils_smtp_test.socket.create_connection')
    @patch('modules.utils_smtp_test.smtplib.SMTP')
    def test_connection_server_capabilities(self, mock_smtp_class, mock_socket, mock_log, tester):
        """Test that server capabilities are properly parsed and returned."""
        # Setup mocks
        mock_socket.return_value.close.return_value = None
        mock_smtp = MagicMock()
        mock_smtp.ehlo.return_value = (b'250-smtp.example.com Hello', 'additional info')
        mock_smtp.esmtp_features = {
            'STARTTLS': 'STARTTLS',
            'auth': 'PLAIN LOGIN DIGEST-MD5',
            'size': '52428800',
            'PIPELINING': 'PIPELINING',
            '8BITMIME': '8BITMIME'
        }
        mock_smtp_class.return_value = mock_smtp
        
        # Test
        success, result = tester.test_connection('smtp.example.com', 587, use_tls=False)
        
        # Verify
        assert success is True
        capabilities = result['capabilities']
        assert capabilities['STARTTLS'] is True
        assert capabilities['Authentication Methods'] == ['PLAIN', 'LOGIN', 'DIGEST-MD5']
        assert capabilities['Size Limit'] == '52428800'
        assert capabilities['Pipeline'] is True
        assert capabilities['8BITMIME'] is True

    @patch('modules.utils_smtp_test.log_system_event')
    @patch('modules.utils_smtp_test.socket.create_connection')
    @patch('modules.utils_smtp_test.smtplib.SMTP')
    def test_connection_quit_exception_handling(self, mock_smtp_class, mock_socket, mock_log, tester):
        """Test that exceptions during SMTP quit are handled gracefully."""
        # Setup mocks
        mock_socket.return_value.close.return_value = None
        mock_smtp = MagicMock()
        mock_smtp.ehlo.return_value = (b'250 Hello', 'additional info')
        mock_smtp.esmtp_features = {}
        
        # Configure quit to fail on first call (line 95) but succeed in finally block  
        mock_smtp.quit.side_effect = [Exception("Connection lost"), None]
        mock_smtp_class.return_value = mock_smtp
        
        # Test - the first quit() call fails but it should be caught as an unexpected error
        success, result = tester.test_connection('smtp.example.com', 587, use_tls=False)
        
        # Verify that the connection fails due to the quit() exception being caught by outer handler
        assert success is False
        assert "Unexpected error: Connection lost" in result


class TestMainFunction:
    """Test the main CLI function."""
    
    @patch('modules.utils_smtp_test.SMTPTester')
    @patch('modules.utils_smtp_test.sys.argv', ['smtp_test.py', '--host', 'smtp.example.com', '--port', '587'])
    def test_main_basic_success(self, mock_tester_class):
        """Test main function with basic successful connection."""
        # Setup mocks
        mock_tester = MagicMock()
        mock_tester.test_connection.return_value = (True, {
            'status': 'Connection successful',
            'auth_status': 'No authentication attempted',
            'server_greeting': '250 Hello',
            'capabilities': {'STARTTLS': True}
        })
        mock_tester_class.return_value = mock_tester
        
        # Test - should not raise SystemExit
        with patch('builtins.print') as mock_print:
            main()
            
        # Verify tester was created and called correctly
        mock_tester_class.assert_called_once_with(debug=False)
        mock_tester.test_connection.assert_called_once_with(
            host='smtp.example.com',
            port=587,
            username=None,
            password=None,
            use_tls=True,
            timeout=10
        )
        
        # Verify success output
        mock_print.assert_any_call("\n✅ SMTP Configuration Test Successful!")

    @patch('modules.utils_smtp_test.SMTPTester')
    @patch('modules.utils_smtp_test.sys.argv', [
        'smtp_test.py', '--host', 'smtp.example.com', '--port', '587',
        '--username', 'testuser', '--password', 'testpass', '--debug', '--no-tls'
    ])
    def test_main_with_all_options(self, mock_tester_class):
        """Test main function with all command line options."""
        # Setup mocks
        mock_tester = MagicMock()
        mock_tester.test_connection.return_value = (True, {'status': 'Success'})
        mock_tester_class.return_value = mock_tester
        
        # Test
        with patch('builtins.print'):
            main()
        
        # Verify tester configuration
        mock_tester_class.assert_called_once_with(debug=True)
        mock_tester.test_connection.assert_called_once_with(
            host='smtp.example.com',
            port=587,
            username='testuser',
            password='testpass',
            use_tls=False,  # --no-tls was specified
            timeout=10
        )

    @patch('modules.utils_smtp_test.SMTPTester')
    @patch('modules.utils_smtp_test.getpass')
    @patch('modules.utils_smtp_test.sys.argv', [
        'smtp_test.py', '--host', 'smtp.example.com', '--port', '587',
        '--username', 'testuser'
    ])
    def test_main_password_prompt(self, mock_getpass, mock_tester_class):
        """Test main function prompts for password when username provided without password."""
        # Setup mocks
        mock_getpass.return_value = 'prompted_password'
        mock_tester = MagicMock()
        mock_tester.test_connection.return_value = (True, {'status': 'Success'})
        mock_tester_class.return_value = mock_tester
        
        # Test
        with patch('builtins.print'):
            main()
        
        # Verify password was prompted
        mock_getpass.assert_called_once_with('Enter SMTP password: ')
        
        # Verify connection was called with prompted password
        mock_tester.test_connection.assert_called_once_with(
            host='smtp.example.com',
            port=587,
            username='testuser',
            password='prompted_password',
            use_tls=True,
            timeout=10
        )

    @patch('modules.utils_smtp_test.SMTPTester')
    @patch('modules.utils_smtp_test.sys.argv', ['smtp_test.py', '--host', 'smtp.example.com', '--port', '587'])
    def test_main_connection_failure(self, mock_tester_class):
        """Test main function with connection failure."""
        # Setup mocks
        mock_tester = MagicMock()
        mock_tester.test_connection.return_value = (False, "Connection failed")
        mock_tester_class.return_value = mock_tester
        
        # Test - should exit with code 1
        with patch('builtins.print') as mock_print, \
             pytest.raises(SystemExit) as exc_info:
            main()
        
        # Verify exit code
        assert exc_info.value.code == 1
        
        # Verify failure output
        mock_print.assert_any_call("\n❌ SMTP Configuration Test Failed: Connection failed")

    @patch('modules.utils_smtp_test.sys.argv', ['smtp_test.py', '--host', 'smtp.example.com', '--port', '587', '--timeout', '30'])
    @patch('modules.utils_smtp_test.SMTPTester')
    def test_main_custom_timeout(self, mock_tester_class):
        """Test main function with custom timeout."""
        # Setup mocks
        mock_tester = MagicMock()
        mock_tester.test_connection.return_value = (True, {'status': 'Success'})
        mock_tester_class.return_value = mock_tester
        
        # Test
        with patch('builtins.print'):
            main()
        
        # Verify custom timeout was used
        mock_tester.test_connection.assert_called_once_with(
            host='smtp.example.com',
            port=587,
            username=None,
            password=None,
            use_tls=True,
            timeout=30
        )