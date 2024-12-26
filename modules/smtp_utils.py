import smtplib, socket, traceback
from email.message import EmailMessage
from flask import flash, current_app, url_for
from modules.models import GlobalSettings

def get_smtp_settings():
    """Get SMTP settings from database."""
    settings = GlobalSettings.query.first()
    
    if settings and settings.smtp_enabled:
        return {
            'MAIL_SERVER': settings.smtp_server,
            'MAIL_PORT': settings.smtp_port,
            'MAIL_USERNAME': settings.smtp_username,
            'MAIL_PASSWORD': settings.smtp_password,
            'MAIL_USE_TLS': settings.smtp_use_tls,
            'MAIL_DEFAULT_SENDER': settings.smtp_default_sender,
            'SMTP_ENABLED': settings.smtp_enabled,
            'SERVER_HOSTNAME': settings.smtp_server
        }
    
    return None

def is_smtp_config_valid():
    """
    Check if the SMTP configuration is valid and complete.
    Returns tuple (bool, str) indicating validity and error message if any.
    """
    smtp_settings = get_smtp_settings()
    
    if not smtp_settings['SMTP_ENABLED']:
        return False, "SMTP is not enabled"
    
    # Enhanced validation for required fields with detailed error messages
    required_fields = {
        'MAIL_SERVER': 'SMTP Server',
        'MAIL_PORT': 'SMTP Port',
        'MAIL_USERNAME': 'Username',
        'MAIL_PASSWORD': 'Password',
        'MAIL_DEFAULT_SENDER': 'Default Sender Email'
    }
    
    missing_fields = []
    for field, display_name in required_fields.items():
        if not smtp_settings[field]:
            missing_fields.append(display_name)
    
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    try:
        port = int(smtp_settings['MAIL_PORT'])
        if port <= 0 or port > 65535:
            return False, "Invalid port number"
    except ValueError:
        return False, "Port must be a valid number"
    
    return True, "Configuration valid"

def is_server_reachable(server, port):
    """
    Check if the mail server is reachable and supports SSL/TLS if required.
    Implements proper STARTTLS handling for different SMTP ports.
    """
    import ssl
    
    try:
        # First try basic socket connection
        with socket.create_connection((server, port), timeout=5) as sock:
            print(f"Basic connection successful to {server}:{port}")
            
            # Handle different SMTP security protocols
            if port == 465:  # SMTPS - Direct SSL/TLS
                context = ssl.create_default_context()
                with context.wrap_socket(sock, server_hostname=server) as ssl_sock:
                    print(f"Direct SSL/TLS connection successful to {server}:{port}")
            elif port == 587:  # SMTP with STARTTLS
                smtp = smtplib.SMTP(server, port)
                smtp.ehlo()
                if smtp.has_extn('STARTTLS'):
                    context = ssl.create_default_context()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                    print(f"STARTTLS connection successful to {server}:{port}")
                smtp.quit()
            return True
    except ssl.SSLError as e:
        print(f"SSL/TLS error connecting to {server}:{port}: {e}")
        return False
    except socket.timeout:
        print(f"Connection timeout to {server}:{port}")
        return False
    except Exception as e:
        print(f"Error connecting to {server}:{port}: {e}")
        return False

def send_email(to, subject, template):
    """
    Send an email with robust error logging and pre-send checks.
    """
    print("\n=== Starting Email Send Process ===")
    smtp_settings = get_smtp_settings()
    
    if not smtp_settings:
        print("SMTP settings not configured. Email not sent.")
        flash("SMTP settings not configured. Email not sent.", "error")
        return False

    if not smtp_settings.get('SMTP_ENABLED'):
        print("SMTP is not enabled. Email not sent.")
        flash("SMTP is not enabled. Email not sent.", "error")
        return False

    is_valid, error_message = is_smtp_config_valid()
    if not is_valid:
        print(f"Invalid SMTP configuration: {error_message}")
        flash(f"Invalid SMTP configuration: {error_message}", "error")
        return False

    mail_server = smtp_settings['MAIL_SERVER']
    mail_port = smtp_settings['MAIL_PORT']
    
    print(f"Attempting connection to {mail_server}:{mail_port}")
    print(f"Using username: {smtp_settings['MAIL_USERNAME']}")
    print(f"From address: {smtp_settings['MAIL_DEFAULT_SENDER']}")
    print(f"To address: {to}")
    print(f"Subject: {subject}")

    if not is_server_reachable(mail_server, mail_port):
        print(f"Mail server {mail_server}:{mail_port} is unreachable. Email not sent.")
        flash(f"Mail server {mail_server}:{mail_port} is unreachable. Email not sent.", "error")
        return False

    try:
        print("Creating message object...")
        msg = EmailMessage()
        msg.set_content(template, subtype='html')  # Set HTML content
        msg['Subject'] = subject
        msg['From'] = smtp_settings['MAIL_DEFAULT_SENDER']
        msg['To'] = to
        
        print("Attempting to send email...")
        print("=== SMTP Transaction Start ===")
        with smtplib.SMTP(mail_server, mail_port, timeout=30) as server:
            print("1. Server connection established")
            server.set_debuglevel(1)  # Enable SMTP debug logging
            
            if smtp_settings['MAIL_USE_TLS']:
                print("2. Starting TLS handshake")
                server.starttls()
                print("3. TLS handshake completed")
            
            print("4. Attempting login")
            server.login(smtp_settings['MAIL_USERNAME'], smtp_settings['MAIL_PASSWORD'])
            print("5. Login successful")
            
            print("6. Sending message")
            server.send_message(msg)
            print("7. Message sent successfully")
            
        print("=== SMTP Transaction Complete ===")
        print(f"Email sent successfully to {to}")
        flash(f"Email sent successfully to {to}", "success")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"SMTP Authentication failed: {e}")
        flash(f"SMTP Authentication failed: {e}", "error")
    except smtplib.SMTPException as e:
        print(f"SMTP error occurred: {str(e)}")
        flash(f"SMTP error occurred: {str(e)}", "error")
    except socket.timeout as e:
        print(f"Connection timed out: {str(e)}")
        flash("Connection timed out while sending email", "error")
    except socket.gaierror as e:
        print(f"DNS lookup failed: {str(e)}")
        flash("DNS lookup failed for SMTP server", "error")
    except Exception as e:
        print(f"Unexpected error occurred while sending email: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error details: {traceback.format_exc()}")
        flash("An unexpected error occurred while sending the email", "error")
    
    print("=== Email Send Process Failed ===\n")
    return False


def send_password_reset_email(user_email, token):
    reset_url = url_for('main.reset_password', token=token, _external=True)
    html = f'''<p>Ahoy there!</p>

<p>Ye be wantin' to reset yer password, aye? No worries, we got ye covered! Jus' click on the link below to set a new course for yer password:</p>

<p><a href="{reset_url}">Password Reset Link</a></p>

<p>If ye didn't request this, ye can just ignore this message and continue sailin' the digital seas.</p>

<p>Fair winds and followin' seas,</p>

<p>Captain Blackbeard</p>'''

    subject = "Ye Password Reset Request Arrr!"
    send_email(user_email, subject, html)