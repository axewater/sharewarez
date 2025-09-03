import pytest
import socket
import ssl
import smtplib
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone

from modules import create_app, db
from modules.models import GlobalSettings
from modules.utils_smtp import (
    get_smtp_settings, is_smtp_config_valid, is_server_reachable,
    send_email, send_password_reset_email, send_invite_email
)


def safe_cleanup_database(db_session):
    """Safely clean up database records respecting foreign key constraints."""
    from sqlalchemy import delete
    db_session.execute(delete(GlobalSettings))
    db_session.commit()


@pytest.fixture
def valid_smtp_settings():
    """Create or update GlobalSettings record with valid SMTP configuration."""
    def _create_settings(db_session, enabled=True):
        from sqlalchemy import select
        # Get existing settings or create new one
        settings = db_session.execute(select(GlobalSettings)).scalars().first()
        if not settings:
            settings = GlobalSettings()
            db_session.add(settings)
        
        # Update with test values
        settings.smtp_enabled = enabled
        settings.smtp_server = 'smtp.example.com'
        settings.smtp_port = 587
        settings.smtp_username = 'testuser@example.com'
        settings.smtp_password = 'testpass123'
        settings.smtp_use_tls = True
        settings.smtp_default_sender = 'noreply@example.com'
        settings.smtp_last_tested = datetime.now(timezone.utc)
        
        db_session.commit()
        return settings
    return _create_settings


@pytest.fixture
def invalid_smtp_settings():
    """Create or update GlobalSettings record with invalid SMTP configuration."""
    def _create_settings(db_session, **overrides):
        from sqlalchemy import select
        # Get existing settings or create new one
        settings = db_session.execute(select(GlobalSettings)).scalars().first()
        if not settings:
            settings = GlobalSettings()
            db_session.add(settings)
            
        default_settings = {
            'smtp_enabled': True,
            'smtp_server': None,
            'smtp_port': None,
            'smtp_username': None,
            'smtp_password': None,
            'smtp_use_tls': True,
            'smtp_default_sender': None,
        }
        default_settings.update(overrides)
        
        # Update settings with test values
        for key, value in default_settings.items():
            setattr(settings, key, value)
        
        db_session.commit()
        return settings
    return _create_settings


class TestGetSMTPSettings:
    """Test get_smtp_settings function."""
    
    def test_get_smtp_settings_enabled(self, app, db_session, valid_smtp_settings):
        """Test getting SMTP settings when enabled and configured."""
        with app.app_context():
            # Create valid settings
            settings = valid_smtp_settings(db_session, enabled=True)
            
            # Test
            result = get_smtp_settings()
            
            # Verify
            assert result is not None
            assert result['SMTP_ENABLED'] is True
            assert result['MAIL_SERVER'] == 'smtp.example.com'
            assert result['MAIL_PORT'] == 587
            assert result['MAIL_USERNAME'] == 'testuser@example.com'
            assert result['MAIL_PASSWORD'] == 'testpass123'
            assert result['MAIL_USE_TLS'] is True
            assert result['MAIL_DEFAULT_SENDER'] == 'noreply@example.com'
            assert result['SERVER_HOSTNAME'] == 'smtp.example.com'
    
    def test_get_smtp_settings_disabled(self, app, db_session, valid_smtp_settings):
        """Test getting SMTP settings when disabled."""
        with app.app_context():
            # Create disabled settings
            valid_smtp_settings(db_session, enabled=False)
            
            # Test
            result = get_smtp_settings()
            
            # Verify - should return None when disabled
            assert result is None
    
    def test_get_smtp_settings_no_settings(self, app, db_session):
        """Test getting SMTP settings when no GlobalSettings exist."""
        with app.app_context():
            # Ensure no settings exist
            safe_cleanup_database(db_session)
            
            # Test
            result = get_smtp_settings()
            
            # Verify
            assert result is None


class TestIsSMTPConfigValid:
    """Test is_smtp_config_valid function."""
    
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_config_valid_complete(self, mock_get_settings):
        """Test validation with complete valid configuration."""
        mock_get_settings.return_value = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 587,
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': 'testpass123',
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        
        # Test
        is_valid, message = is_smtp_config_valid()
        
        # Verify
        assert is_valid is True
        assert message == "Configuration valid"
    
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_config_smtp_disabled(self, mock_get_settings):
        """Test validation when SMTP is disabled."""
        # When SMTP is disabled, get_smtp_settings returns None
        mock_get_settings.return_value = None
        
        # Test - this should raise a TypeError when trying to access None['SMTP_ENABLED']
        with pytest.raises(TypeError):
            is_smtp_config_valid()
    
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_config_missing_single_field(self, mock_get_settings):
        """Test validation with single missing required field."""
        mock_get_settings.return_value = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': None,  # Missing
            'MAIL_PORT': 587,
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': 'testpass123',
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        
        # Test
        is_valid, message = is_smtp_config_valid()
        
        # Verify
        assert is_valid is False
        assert message == "Missing required fields: SMTP Server"
    
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_config_missing_multiple_fields(self, mock_get_settings):
        """Test validation with multiple missing required fields."""
        mock_get_settings.return_value = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': None,
            'MAIL_PORT': None,
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': None,
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        
        # Test
        is_valid, message = is_smtp_config_valid()
        
        # Verify
        assert is_valid is False
        assert "Missing required fields:" in message
        assert "SMTP Server" in message
        assert "SMTP Port" in message
        assert "Password" in message
    
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_config_invalid_port_non_numeric(self, mock_get_settings):
        """Test validation with non-numeric port."""
        mock_get_settings.return_value = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 'invalid',
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': 'testpass123',
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        
        # Test
        is_valid, message = is_smtp_config_valid()
        
        # Verify
        assert is_valid is False
        assert message == "Port must be a valid number"
    
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_config_invalid_port_out_of_range(self, mock_get_settings):
        """Test validation with port out of range."""
        mock_get_settings.return_value = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 70000,  # Out of range
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': 'testpass123',
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        
        # Test
        is_valid, message = is_smtp_config_valid()
        
        # Verify
        assert is_valid is False
        assert message == "Invalid port number"
    
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_config_invalid_port_zero(self, mock_get_settings):
        """Test validation with zero port."""
        mock_get_settings.return_value = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 0,  # This will be caught as a missing field since 0 is falsy
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': 'testpass123',
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        
        # Test
        is_valid, message = is_smtp_config_valid()
        
        # Verify - 0 is falsy so it's treated as missing
        assert is_valid is False
        assert "Missing required fields: SMTP Port" in message


class TestIsServerReachable:
    """Test is_server_reachable function."""
    
    @patch('modules.utils_smtp.socket.create_connection')
    @patch('ssl.create_default_context')
    def test_server_reachable_port_465_success(self, mock_ssl_context, mock_socket):
        """Test successful connection to SMTPS port 465."""
        # Setup mocks
        mock_sock = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock
        
        mock_context = MagicMock()
        mock_ssl_context.return_value = mock_context
        mock_ssl_sock = MagicMock()
        mock_context.wrap_socket.return_value.__enter__.return_value = mock_ssl_sock
        
        # Test
        with patch('builtins.print') as mock_print:
            result = is_server_reachable('smtp.example.com', 465)
        
        # Verify
        assert result is True
        mock_socket.assert_called_once_with(('smtp.example.com', 465), timeout=5)
        mock_ssl_context.assert_called_once()
        mock_print.assert_any_call("Basic connection successful to smtp.example.com:465")
        mock_print.assert_any_call("Direct SSL/TLS connection successful to smtp.example.com:465")
    
    @patch('modules.utils_smtp.socket.create_connection')
    @patch('modules.utils_smtp.smtplib.SMTP')
    @patch('ssl.create_default_context')
    def test_server_reachable_port_587_success(self, mock_ssl_context, mock_smtp_class, mock_socket):
        """Test successful connection to SMTP port 587 with STARTTLS."""
        # Setup mocks
        mock_sock = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock
        
        mock_smtp = MagicMock()
        mock_smtp.has_extn.return_value = True
        mock_smtp_class.return_value = mock_smtp
        
        mock_context = MagicMock()
        mock_ssl_context.return_value = mock_context
        
        # Test
        with patch('builtins.print') as mock_print:
            result = is_server_reachable('smtp.example.com', 587)
        
        # Verify
        assert result is True
        mock_socket.assert_called_once_with(('smtp.example.com', 587), timeout=5)
        mock_smtp_class.assert_called_once_with('smtp.example.com', 587)
        mock_smtp.ehlo.assert_called()
        mock_smtp.has_extn.assert_called_with('STARTTLS')
        mock_smtp.starttls.assert_called_once_with(context=mock_context)
        mock_smtp.quit.assert_called_once()
        mock_print.assert_any_call("Basic connection successful to smtp.example.com:587")
        mock_print.assert_any_call("STARTTLS connection successful to smtp.example.com:587")
    
    @patch('modules.utils_smtp.socket.create_connection')
    def test_server_reachable_socket_timeout(self, mock_socket):
        """Test server unreachable due to socket timeout."""
        mock_socket.side_effect = socket.timeout()
        
        # Test
        with patch('builtins.print') as mock_print:
            result = is_server_reachable('smtp.example.com', 587)
        
        # Verify
        assert result is False
        mock_print.assert_called_with("Connection timeout to smtp.example.com:587")
    
    @patch('modules.utils_smtp.socket.create_connection')
    def test_server_reachable_ssl_error(self, mock_socket):
        """Test server unreachable due to SSL error."""
        mock_socket.side_effect = ssl.SSLError("SSL handshake failed")
        
        # Test
        with patch('builtins.print') as mock_print:
            result = is_server_reachable('smtp.example.com', 465)
        
        # Verify
        assert result is False
        # SSL error message includes the exception args tuple
        mock_print.assert_called_with("SSL/TLS error connecting to smtp.example.com:465: ('SSL handshake failed',)")
    
    @patch('modules.utils_smtp.socket.create_connection')
    def test_server_reachable_general_exception(self, mock_socket):
        """Test server unreachable due to general exception."""
        mock_socket.side_effect = ConnectionRefusedError("Connection refused")
        
        # Test
        with patch('builtins.print') as mock_print:
            result = is_server_reachable('smtp.example.com', 587)
        
        # Verify
        assert result is False
        mock_print.assert_called_with("Error connecting to smtp.example.com:587: Connection refused")


class TestSendEmail:
    """Test send_email function."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.test_to = "recipient@example.com"
        self.test_subject = "Test Subject"
        self.test_template = "<h1>Test Email</h1>"
    
    @patch('modules.utils_smtp.log_system_event')
    @patch('modules.utils_smtp.flash')
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_send_email_no_settings(self, mock_get_settings, mock_flash, mock_log):
        """Test send_email when SMTP settings are not configured."""
        mock_get_settings.return_value = None
        
        # Test
        with patch('builtins.print') as mock_print:
            result = send_email(self.test_to, self.test_subject, self.test_template)
        
        # Verify
        assert result is False
        mock_print.assert_any_call("SMTP settings not configured. Email not sent.")
        mock_flash.assert_called_with("SMTP settings not configured. Email not sent.", "error")
    
    @patch('modules.utils_smtp.log_system_event')
    @patch('modules.utils_smtp.flash')
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_send_email_smtp_disabled(self, mock_get_settings, mock_flash, mock_log):
        """Test send_email when SMTP is disabled."""
        mock_get_settings.return_value = {'SMTP_ENABLED': False}
        
        # Test
        with patch('builtins.print') as mock_print:
            result = send_email(self.test_to, self.test_subject, self.test_template)
        
        # Verify
        assert result is False
        mock_print.assert_any_call("SMTP is not enabled. Email not sent.")
        mock_flash.assert_called_with("SMTP is not enabled. Email not sent.", "error")
    
    @patch('modules.utils_smtp.log_system_event')
    @patch('modules.utils_smtp.flash')
    @patch('modules.utils_smtp.is_smtp_config_valid')
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_send_email_invalid_config(self, mock_get_settings, mock_is_valid, mock_flash, mock_log):
        """Test send_email with invalid SMTP configuration."""
        mock_get_settings.return_value = {'SMTP_ENABLED': True}
        mock_is_valid.return_value = (False, "Missing required fields: SMTP Server")
        
        # Test
        with patch('builtins.print') as mock_print:
            result = send_email(self.test_to, self.test_subject, self.test_template)
        
        # Verify
        assert result is False
        mock_print.assert_any_call("Invalid SMTP configuration: Missing required fields: SMTP Server")
        mock_flash.assert_called_with("Invalid SMTP configuration: Missing required fields: SMTP Server", "error")
    
    @patch('modules.utils_smtp.log_system_event')
    @patch('modules.utils_smtp.flash')
    @patch('modules.utils_smtp.is_server_reachable')
    @patch('modules.utils_smtp.is_smtp_config_valid')
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_send_email_server_unreachable(self, mock_get_settings, mock_is_valid, mock_is_reachable, mock_flash, mock_log):
        """Test send_email when server is unreachable."""
        mock_get_settings.return_value = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 587,
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        mock_is_valid.return_value = (True, "Configuration valid")
        mock_is_reachable.return_value = False
        
        # Test
        with patch('builtins.print') as mock_print:
            result = send_email(self.test_to, self.test_subject, self.test_template)
        
        # Verify
        assert result is False
        mock_print.assert_any_call("Mail server smtp.example.com:587 is unreachable. Email not sent.")
        mock_flash.assert_called_with("Mail server smtp.example.com:587 is unreachable. Email not sent.", "error")
        mock_log.assert_called_with(
            f"Failed to send email to {self.test_to}: Mail server unreachable",
            event_type='email',
            event_level='error'
        )
    
    @patch('modules.utils_smtp.log_system_event')
    @patch('modules.utils_smtp.flash')
    @patch('modules.utils_smtp.smtplib.SMTP')
    @patch('modules.utils_smtp.is_server_reachable')
    @patch('modules.utils_smtp.is_smtp_config_valid')
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_send_email_success(self, mock_get_settings, mock_is_valid, mock_is_reachable, mock_smtp_class, mock_flash, mock_log):
        """Test successful email sending."""
        # Setup mocks
        smtp_settings = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 587,
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': 'testpass123',
            'MAIL_USE_TLS': True,
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        mock_get_settings.return_value = smtp_settings
        mock_is_valid.return_value = (True, "Configuration valid")
        mock_is_reachable.return_value = True
        
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        
        # Test
        with patch('builtins.print') as mock_print:
            result = send_email(self.test_to, self.test_subject, self.test_template)
        
        # Verify
        assert result is True
        mock_server.set_debuglevel.assert_called_with(1)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_with('testuser@example.com', 'testpass123')
        mock_server.send_message.assert_called_once()
        
        # Verify success messages
        mock_print.assert_any_call(f"Email sent successfully to {self.test_to}")
        mock_flash.assert_called_with(f"Email sent successfully to {self.test_to}", "success")
        mock_log.assert_called_with(
            f"Email sent to {self.test_to} with subject: {self.test_subject}",
            event_type='email',
            event_level='information'
        )
    
    @patch('modules.utils_smtp.log_system_event')
    @patch('modules.utils_smtp.flash')
    @patch('modules.utils_smtp.smtplib.SMTP')
    @patch('modules.utils_smtp.is_server_reachable')
    @patch('modules.utils_smtp.is_smtp_config_valid')
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_send_email_auth_error(self, mock_get_settings, mock_is_valid, mock_is_reachable, mock_smtp_class, mock_flash, mock_log):
        """Test send_email with SMTP authentication error."""
        # Setup mocks
        smtp_settings = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 587,
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': 'wrongpass',
            'MAIL_USE_TLS': True,
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        mock_get_settings.return_value = smtp_settings
        mock_is_valid.return_value = (True, "Configuration valid")
        mock_is_reachable.return_value = True
        
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, "Authentication failed")
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        
        # Test
        with patch('builtins.print') as mock_print:
            result = send_email(self.test_to, self.test_subject, self.test_template)
        
        # Verify
        assert result is False
        mock_print.assert_any_call("SMTP Authentication failed: (535, 'Authentication failed')")
        mock_flash.assert_called_with("SMTP Authentication failed: (535, 'Authentication failed')", "error")
    
    @patch('modules.utils_smtp.log_system_event')
    @patch('modules.utils_smtp.flash')
    @patch('modules.utils_smtp.smtplib.SMTP')
    @patch('modules.utils_smtp.is_server_reachable')
    @patch('modules.utils_smtp.is_smtp_config_valid')
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_send_email_smtp_exception(self, mock_get_settings, mock_is_valid, mock_is_reachable, mock_smtp_class, mock_flash, mock_log):
        """Test send_email with SMTP protocol exception."""
        # Setup mocks
        smtp_settings = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 587,
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': 'testpass123',
            'MAIL_USE_TLS': True,
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        mock_get_settings.return_value = smtp_settings
        mock_is_valid.return_value = (True, "Configuration valid")
        mock_is_reachable.return_value = True
        
        mock_server = MagicMock()
        mock_server.send_message.side_effect = smtplib.SMTPException("Message rejected")
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        
        # Test
        with patch('builtins.print') as mock_print:
            result = send_email(self.test_to, self.test_subject, self.test_template)
        
        # Verify
        assert result is False
        mock_print.assert_any_call("SMTP error occurred: Message rejected")
        mock_flash.assert_called_with("SMTP error occurred: Message rejected", "error")
    
    @patch('modules.utils_smtp.log_system_event')
    @patch('modules.utils_smtp.flash')
    @patch('modules.utils_smtp.smtplib.SMTP')
    @patch('modules.utils_smtp.is_server_reachable')
    @patch('modules.utils_smtp.is_smtp_config_valid')
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_send_email_timeout_error(self, mock_get_settings, mock_is_valid, mock_is_reachable, mock_smtp_class, mock_flash, mock_log):
        """Test send_email with socket timeout."""
        # Setup mocks
        smtp_settings = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 587,
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': 'testpass123',
            'MAIL_USE_TLS': True,
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        mock_get_settings.return_value = smtp_settings
        mock_is_valid.return_value = (True, "Configuration valid")
        mock_is_reachable.return_value = True
        
        mock_smtp_class.return_value.__enter__.side_effect = socket.timeout("Connection timed out")
        
        # Test
        with patch('builtins.print') as mock_print:
            result = send_email(self.test_to, self.test_subject, self.test_template)
        
        # Verify
        assert result is False
        mock_print.assert_any_call("Connection timed out: Connection timed out")
        mock_flash.assert_called_with("Connection timed out while sending email", "error")
    
    @patch('modules.utils_smtp.log_system_event')
    @patch('modules.utils_smtp.flash')
    @patch('modules.utils_smtp.smtplib.SMTP')
    @patch('modules.utils_smtp.is_server_reachable')
    @patch('modules.utils_smtp.is_smtp_config_valid')
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_send_email_dns_error(self, mock_get_settings, mock_is_valid, mock_is_reachable, mock_smtp_class, mock_flash, mock_log):
        """Test send_email with DNS lookup failure."""
        # Setup mocks
        smtp_settings = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 587,
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': 'testpass123',
            'MAIL_USE_TLS': True,
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        mock_get_settings.return_value = smtp_settings
        mock_is_valid.return_value = (True, "Configuration valid")
        mock_is_reachable.return_value = True
        
        mock_smtp_class.return_value.__enter__.side_effect = socket.gaierror("DNS lookup failed")
        
        # Test
        with patch('builtins.print') as mock_print:
            result = send_email(self.test_to, self.test_subject, self.test_template)
        
        # Verify
        assert result is False
        mock_print.assert_any_call("DNS lookup failed: DNS lookup failed")
        mock_flash.assert_called_with("DNS lookup failed for SMTP server", "error")
    
    @patch('modules.utils_smtp.traceback.format_exc')
    @patch('modules.utils_smtp.log_system_event')
    @patch('modules.utils_smtp.flash')
    @patch('modules.utils_smtp.smtplib.SMTP')
    @patch('modules.utils_smtp.is_server_reachable')
    @patch('modules.utils_smtp.is_smtp_config_valid')
    @patch('modules.utils_smtp.get_smtp_settings')
    def test_send_email_unexpected_error(self, mock_get_settings, mock_is_valid, mock_is_reachable, 
                                       mock_smtp_class, mock_flash, mock_log, mock_traceback):
        """Test send_email with unexpected error."""
        # Setup mocks
        smtp_settings = {
            'SMTP_ENABLED': True,
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 587,
            'MAIL_USERNAME': 'testuser@example.com',
            'MAIL_PASSWORD': 'testpass123',
            'MAIL_USE_TLS': True,
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        mock_get_settings.return_value = smtp_settings
        mock_is_valid.return_value = (True, "Configuration valid")
        mock_is_reachable.return_value = True
        
        mock_smtp_class.return_value.__enter__.side_effect = ValueError("Unexpected error")
        mock_traceback.return_value = "Traceback details..."
        
        # Test
        with patch('builtins.print') as mock_print:
            result = send_email(self.test_to, self.test_subject, self.test_template)
        
        # Verify
        assert result is False
        mock_print.assert_any_call("Unexpected error occurred while sending email: Unexpected error")
        mock_print.assert_any_call("Error type: <class 'ValueError'>")
        mock_flash.assert_called_with("An unexpected error occurred while sending the email", "error")
        mock_log.assert_called_with(
            f"Failed to send email to {self.test_to}: Traceback details...",
            event_type='email',
            event_level='error'
        )


class TestSendPasswordResetEmail:
    """Test send_password_reset_email function."""
    
    @patch('modules.utils_smtp.send_email')
    @patch('modules.utils_smtp.url_for')
    def test_send_password_reset_email(self, mock_url_for, mock_send_email):
        """Test sending password reset email."""
        # Setup mocks
        mock_url_for.return_value = 'https://example.com/reset/abc123'
        mock_send_email.return_value = True
        
        # Test
        send_password_reset_email('user@example.com', 'abc123')
        
        # Verify URL generation
        mock_url_for.assert_called_once_with('main.reset_password', token='abc123', _external=True)
        
        # Verify send_email was called
        mock_send_email.assert_called_once()
        args, kwargs = mock_send_email.call_args
        
        # Check arguments
        assert args[0] == 'user@example.com'
        assert args[1] == "Ye Password Reset Request Arrr!"
        
        # Check that HTML content contains the reset URL
        html_content = args[2]
        assert 'https://example.com/reset/abc123' in html_content
        assert 'Password Reset Link' in html_content
        assert 'Captain Blackbeard' in html_content


class TestSendInviteEmail:
    """Test send_invite_email function."""
    
    @patch('modules.utils_smtp.send_email')
    @patch('modules.utils_smtp.render_template')
    def test_send_invite_email(self, mock_render_template, mock_send_email):
        """Test sending invite email."""
        # Setup mocks
        mock_render_template.return_value = '<h1>You are invited!</h1>'
        mock_send_email.return_value = True
        
        invite_url = 'https://example.com/invite/xyz789'
        
        # Test
        send_invite_email('newuser@example.com', invite_url)
        
        # Verify template rendering
        mock_render_template.assert_called_once_with('login/invite_email.html', invite_url=invite_url)
        
        # Verify send_email was called
        mock_send_email.assert_called_once_with(
            'newuser@example.com',
            "You're Invited!",
            '<h1>You are invited!</h1>'
        )