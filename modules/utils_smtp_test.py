import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import socket
import ssl
import argparse
import sys
from getpass import getpass
from typing import Dict, Tuple, Union, Optional
from modules.utils_logging import log_system_event

class SMTPTester:
    def __init__(self, debug: bool = False):
        """
        Initialize SMTP tester.
        
        Args:
            debug: If True, enables SMTP debug output
        """
        self.debug = debug
        if debug:
            try:
                log_system_event("SMTP debug mode enabled - sensitive data may be logged", 
                               event_type='security', event_level='warning')
            except Exception:
                # If we can't log (e.g., no Flask context), just continue
                pass
    
    def _secure_debug_filter(self, message: str) -> str:
        """
        Filter debug messages to remove sensitive authentication data.
        
        Args:
            message: Original debug message
            
        Returns:
            Sanitized debug message
        """
        import re
        # Redact common authentication patterns
        patterns = [
            (r'AUTH\s+\w+\s+[A-Za-z0-9+/=]+', 'AUTH [METHOD] [CREDENTIALS_REDACTED]'),
            (r'PASS\s+.*', 'PASS [PASSWORD_REDACTED]'),
            (r'USER\s+.*', 'USER [USERNAME_REDACTED]'),
        ]
        
        sanitized = message
        for pattern, replacement in patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    def _validate_inputs(self, host: str, port: int) -> Tuple[bool, str]:
        """
        Validate host and port parameters for security.
        
        Args:
            host: SMTP server hostname
            port: SMTP server port
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        import re
        
        # Validate port range
        if not isinstance(port, int) or port <= 0 or port > 65535:
            return False, "Invalid port number. Must be between 1 and 65535"
        
        # Validate hostname format (basic validation)
        if not host or not isinstance(host, str):
            return False, "Invalid hostname"
        
        # Check for potentially dangerous characters first
        dangerous_chars = ['<', '>', '"', "'", '&', '|', ';', '`', '$', '(', ')', '{', '}', '[', ']']
        if any(char in host for char in dangerous_chars):
            return False, "Hostname contains invalid characters"
        
        # Check for basic hostname format (allows IP addresses and domain names)
        hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$|^([0-9]{1,3}\.){3}[0-9]{1,3}$'
        if not re.match(hostname_pattern, host) or len(host) > 255:
            return False, "Invalid hostname format"
            
        return True, ""

    def test_connection(
        self,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
        timeout: int = 10
    ) -> Tuple[bool, Union[str, Dict]]:
        """
        Test SMTP connection without sending actual emails.
        
        Args:
            host: SMTP server hostname
            port: SMTP server port
            username: Optional username for authentication
            password: Optional password for authentication
            use_tls: Whether to use STARTTLS
            timeout: Connection timeout in seconds
        
        Returns:
            Tuple of (success, result)
            - success is a boolean indicating if the test was successful
            - result is either an error message string or a dict with server details
        """
        # Validate inputs first
        is_valid, validation_error = self._validate_inputs(host, port)
        if not is_valid:
            return False, validation_error
            
        try:
            # First test basic socket connection
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            
            # Initialize SMTP connection
            smtp = smtplib.SMTP(host, port, timeout=timeout)
            if self.debug:
                smtp.set_debuglevel(1)
            
            try:
                # Initial EHLO
                server_info = smtp.ehlo()
                supported_features = smtp.esmtp_features

                # Handle TLS if enabled
                if use_tls:
                    if smtp.has_extn('STARTTLS'):
                        # Create strict SSL context for security
                        context = ssl.create_default_context()
                        context.check_hostname = True
                        context.verify_mode = ssl.CERT_REQUIRED
                        smtp.starttls(context=context)
                        smtp.ehlo()  # Say hello again after STARTTLS
                    else:
                        return False, "STARTTLS not supported by server (not found in extensions)"

                # Test authentication if credentials provided
                if username and password:
                    try:
                        smtp.login(username, password)
                        auth_status = "Authentication successful"
                    except smtplib.SMTPAuthenticationError:
                        return False, "Authentication failed - invalid credentials"
                else:
                    auth_status = "No authentication attempted"

                # Get supported authentication methods
                auth_methods = []
                if 'auth' in supported_features:
                    auth_methods = supported_features['auth'].split()

                # Collect server capabilities
                capabilities = {
                    'STARTTLS': 'STARTTLS' in smtp.esmtp_features,
                    'Authentication Methods': auth_methods,
                    'Size Limit': smtp.esmtp_features.get('size', 'Not specified'),
                    'Pipeline': 'PIPELINING' in smtp.esmtp_features,
                    '8BITMIME': '8BITMIME' in smtp.esmtp_features
                }

                smtp.quit()
                
                log_system_event("SMTP connection test completed successfully", event_type='test', event_level='information')
                return True, {
                    'status': 'Connection successful',
                    'auth_status': auth_status,
                    'server_greeting': server_info[0].decode() if isinstance(server_info[0], bytes) else str(server_info[0]),
                    'capabilities': capabilities
                }

            except smtplib.SMTPException as e:
                log_system_event("SMTP connection test failed", event_type='test', event_level='information')
                return False, f"SMTP error: {str(e)}"
            finally:
                try:
                    smtp.quit()
                except (smtplib.SMTPException, OSError, AttributeError):
                    # Ignore cleanup errors - connection may already be closed
                    pass

        except socket.timeout:
            return False, "Connection timed out"
        except socket.gaierror:
            return False, "DNS lookup failed"
        except ssl.SSLError as e:
            return False, f"SSL/TLS error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

def main():
    """Command line interface for SMTP testing"""
    parser = argparse.ArgumentParser(description='Test SMTP server configuration')
    parser.add_argument('--host', required=True, help='SMTP server hostname')
    parser.add_argument('--port', type=int, required=True, help='SMTP server port')
    parser.add_argument('--username', help='SMTP username (if authentication required)')
    parser.add_argument('--no-tls', action='store_true', help='Disable TLS/SSL')
    parser.add_argument('--timeout', type=int, default=10, help='Connection timeout in seconds')
    parser.add_argument('--debug', action='store_true', help='Enable SMTP debug output')
    
    args = parser.parse_args()
    
    # Handle password - always prompt securely for security
    password = None
    if args.username:
        password = getpass('Enter SMTP password: ')
    
    # Create tester instance
    tester = SMTPTester(debug=args.debug)
    success, result = tester.test_connection(
        host=args.host,
        port=args.port,
        username=args.username,
        password=password,
        use_tls=not args.no_tls,
        timeout=args.timeout
    )
    
    if success:
        print("\n✅ SMTP Configuration Test Successful!")
        print("\nServer Information:")
        for key, value in result.items():
            if isinstance(value, dict):
                print(f"\n{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"{key}: {value}")
    else:
        print(f"\n❌ SMTP Configuration Test Failed: {result}")
        sys.exit(1)

if __name__ == "__main__":
    main()
