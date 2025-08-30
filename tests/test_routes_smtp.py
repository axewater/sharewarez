import pytest
import json
from unittest.mock import patch, Mock, MagicMock
from uuid import uuid4

from modules import create_app, db
from modules.models import User, GlobalSettings
from modules.utils_smtp_test import SMTPTester


@pytest.fixture(scope='function')
def app():
    """Create and configure a test app using the actual database."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    
    yield app


@pytest.fixture(scope='function')  
def db_session(app):
    """Create a database session for testing with transaction rollback."""
    with app.app_context():
        # Start a transaction that will be rolled back after each test
        connection = db.engine.connect()
        transaction = connection.begin()
        
        # Bind the session to this transaction
        db.session.configure(bind=connection)
        
        yield db.session
        
        # Rollback the transaction to clean up
        transaction.rollback()
        connection.close()
        db.session.remove()


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user_uuid = str(uuid4())
    user = User(
        name=f'testuser_{user_uuid[:8]}',
        email=f'test_{user_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='user',
        user_id=user_uuid,
        avatarpath='newstyle/avatar_default.jpg',
        invite_quota=5
    )
    user.set_password('testpassword123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin_user(db_session):
    """Create a test admin user."""
    user_uuid = str(uuid4())
    user = User(
        name=f'adminuser_{user_uuid[:8]}',
        email=f'admin_{user_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='admin',
        user_id=user_uuid,
        avatarpath='newstyle/avatar_default.jpg',
        invite_quota=10
    )
    user.set_password('adminpassword123')
    db_session.add(user)
    db_session.commit()
    return user


def create_test_settings(db_session):
    """Helper function to create test global settings."""
    settings = GlobalSettings(
        smtp_enabled=True,
        smtp_server='smtp.example.com',
        smtp_port=587,
        smtp_username='test@example.com',
        smtp_password='testpassword',
        smtp_use_tls=True,
        smtp_default_sender='noreply@example.com'
    )
    db_session.add(settings)
    db_session.commit()
    return settings


class TestSmtpContextProcessor:
    """Test the SMTP context processor."""
    
    @patch('modules.routes_smtp.get_global_settings')
    def test_inject_settings_cached(self, mock_get_settings, app):
        """Test that inject_settings returns global settings."""
        # Mock the settings
        mock_settings = {
            'showSystemLogo': True,
            'showHelpButton': False,
            'siteName': 'Test Site'
        }
        mock_get_settings.return_value = mock_settings
        
        with app.app_context():
            from modules.routes_smtp import inject_settings
            result = inject_settings()
            
            assert result == mock_settings
            mock_get_settings.assert_called_once()


class TestSmtpSettings:
    """Test the smtp_settings route."""
    
    def test_get_requires_login(self, client):
        """Test that GET request requires login."""
        response = client.get('/admin/smtp_settings')
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_get_requires_admin(self, client, test_user):
        """Test that GET request requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/smtp_settings')
        assert response.status_code == 302  # Redirected by admin_required
    
    @patch('modules.routes_smtp.render_template')
    def test_get_success_no_settings(self, mock_render, client, admin_user, db_session):
        """Test GET request with no existing settings."""
        # Delete any existing settings first
        db_session.query(GlobalSettings).delete()
        db_session.commit()
        
        mock_render.return_value = 'rendered template'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/smtp_settings')
        assert response.status_code == 200
        
        # Verify template was rendered with correct arguments
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        assert args[0] == 'admin/admin_manage_smtp_settings.html'
        assert kwargs['settings'] is None
    
    @patch('modules.routes_smtp.render_template')
    def test_get_success_with_settings(self, mock_render, client, admin_user, db_session):
        """Test GET request with existing settings."""
        # Delete any default settings first, then use our test settings
        db_session.query(GlobalSettings).delete()
        db_session.commit()
        test_settings = create_test_settings(db_session)
        
        mock_render.return_value = 'rendered template'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/smtp_settings')
        assert response.status_code == 200
        
        # Verify template was rendered with settings
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        assert args[0] == 'admin/admin_manage_smtp_settings.html'
        assert kwargs['settings'].smtp_server == test_settings.smtp_server
    
    def test_post_requires_login(self, client):
        """Test that POST request requires login."""
        response = client.post('/admin/smtp_settings', json={})
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_post_requires_admin(self, client, test_user):
        """Test that POST request requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/smtp_settings', json={})
        assert response.status_code == 302  # Redirected by admin_required
    
    def test_post_create_new_settings_smtp_disabled(self, client, admin_user, db_session):
        """Test POST request creating new settings with SMTP disabled."""
        # Delete any existing settings first
        db_session.query(GlobalSettings).delete()
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': False,
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'smtp_username': 'test@example.com',
            'smtp_password': 'testpass',
            'smtp_use_tls': True,
            'smtp_default_sender': 'noreply@example.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 200
        
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'
        assert response_data['message'] == 'SMTP settings updated successfully'
        
        # Verify settings were created in database
        settings = GlobalSettings.query.first()
        assert settings is not None
        assert settings.smtp_enabled is False
        assert settings.smtp_server == 'smtp.example.com'
        # Note: smtp_port is not set when smtp_enabled is False, per the actual code logic
        assert settings.smtp_username == 'test@example.com'
        assert settings.smtp_password == 'testpass'
        assert settings.smtp_use_tls is True  # Default value
        assert settings.smtp_default_sender == 'noreply@example.com'
    
    def test_post_create_new_settings_smtp_enabled_valid(self, client, admin_user, db_session):
        """Test POST request creating new settings with SMTP enabled and valid data."""
        # Delete any existing settings first
        db_session.query(GlobalSettings).delete()
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': True,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'smtp_username': 'test@gmail.com',
            'smtp_password': 'testpass123',
            'smtp_use_tls': True,
            'smtp_default_sender': 'noreply@gmail.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 200
        
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'
        assert response_data['message'] == 'SMTP settings updated successfully'
        
        # Verify settings were created in database
        settings = GlobalSettings.query.first()
        assert settings is not None
        assert settings.smtp_enabled is True
        assert settings.smtp_server == 'smtp.gmail.com'
        assert settings.smtp_port == 587
        assert settings.smtp_username == 'test@gmail.com'
        assert settings.smtp_password == 'testpass123'
        assert settings.smtp_use_tls is True
        assert settings.smtp_default_sender == 'noreply@gmail.com'
    
    def test_post_update_existing_settings(self, client, admin_user, db_session):
        """Test POST request updating existing settings."""
        # Delete any default settings and use only our test settings
        db_session.query(GlobalSettings).delete()
        db_session.commit()
        test_settings = create_test_settings(db_session)
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': True,
            'smtp_server': 'smtp.updated.com',
            'smtp_port': 465,
            'smtp_username': 'updated@example.com',
            'smtp_password': 'newpassword',
            'smtp_use_tls': False,
            'smtp_default_sender': 'updated@example.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 200
        
        response_data = json.loads(response.data)
        assert response_data['status'] == 'success'
        
        # Verify settings were updated by querying fresh from DB
        updated_settings = GlobalSettings.query.first()
        assert updated_settings.smtp_server == 'smtp.updated.com'
        assert updated_settings.smtp_port == 465
        assert updated_settings.smtp_username == 'updated@example.com'
        assert updated_settings.smtp_password == 'newpassword'
        assert updated_settings.smtp_use_tls is False
        assert updated_settings.smtp_default_sender == 'updated@example.com'
    
    def test_post_smtp_enabled_missing_server(self, client, admin_user, db_session):
        """Test POST request with SMTP enabled but missing server."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': True,
            'smtp_port': 587,
            'smtp_username': 'test@example.com',
            'smtp_password': 'testpass',
            'smtp_default_sender': 'noreply@example.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 400
        
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert response_data['message'] == 'SMTP server is required when SMTP is enabled'
    
    def test_post_smtp_enabled_missing_port(self, client, admin_user, db_session):
        """Test POST request with SMTP enabled but missing port."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': True,
            'smtp_server': 'smtp.example.com',
            'smtp_username': 'test@example.com',
            'smtp_password': 'testpass',
            'smtp_default_sender': 'noreply@example.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 400
        
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert response_data['message'] == 'SMTP port is required when SMTP is enabled'
    
    def test_post_smtp_enabled_missing_username(self, client, admin_user, db_session):
        """Test POST request with SMTP enabled but missing username."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': True,
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'smtp_password': 'testpass',
            'smtp_default_sender': 'noreply@example.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 400
        
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert response_data['message'] == 'SMTP username is required when SMTP is enabled'
    
    def test_post_smtp_enabled_missing_password(self, client, admin_user, db_session):
        """Test POST request with SMTP enabled but missing password."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': True,
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'smtp_username': 'test@example.com',
            'smtp_default_sender': 'noreply@example.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 400
        
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert response_data['message'] == 'SMTP password is required when SMTP is enabled'
    
    def test_post_smtp_enabled_missing_default_sender(self, client, admin_user, db_session):
        """Test POST request with SMTP enabled but missing default sender."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': True,
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'smtp_username': 'test@example.com',
            'smtp_password': 'testpass'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 400
        
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert response_data['message'] == 'Default sender email is required when SMTP is enabled'
    
    def test_post_invalid_port_number_string(self, client, admin_user, db_session):
        """Test POST request with invalid port number (string)."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': True,
            'smtp_server': 'smtp.example.com',
            'smtp_port': 'invalid',
            'smtp_username': 'test@example.com',
            'smtp_password': 'testpass',
            'smtp_default_sender': 'noreply@example.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 400
        
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert response_data['message'] == 'SMTP port must be a valid number'
    
    def test_post_invalid_port_number_negative(self, client, admin_user, db_session):
        """Test POST request with invalid port number (negative)."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': True,
            'smtp_server': 'smtp.example.com',
            'smtp_port': -1,
            'smtp_username': 'test@example.com',
            'smtp_password': 'testpass',
            'smtp_default_sender': 'noreply@example.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 400
        
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert response_data['message'] == 'Invalid port number. Must be between 1 and 65535'
    
    def test_post_invalid_port_number_too_high(self, client, admin_user, db_session):
        """Test POST request with invalid port number (too high)."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': True,
            'smtp_server': 'smtp.example.com',
            'smtp_port': 70000,
            'smtp_username': 'test@example.com',
            'smtp_password': 'testpass',
            'smtp_default_sender': 'noreply@example.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 400
        
        response_data = json.loads(response.data)
        assert response_data['status'] == 'error'
        assert response_data['message'] == 'Invalid port number. Must be between 1 and 65535'
    
    def test_post_database_commit_error(self, client, admin_user, db_session):
        """Test POST request with database commit error."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': False,
            'smtp_server': 'smtp.example.com'
        }
        
        with patch('modules.routes_smtp.db.session.commit', side_effect=Exception('Database error')):
            response = client.post('/admin/smtp_settings', json=data)
            
            assert response.status_code == 500
            response_data = json.loads(response.data)
            assert response_data['status'] == 'error'
            assert response_data['message'] == 'Database error'
    
    def test_post_defaults_smtp_use_tls_true(self, client, admin_user, db_session):
        """Test POST request defaults smtp_use_tls to True."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_enabled': False,
            'smtp_server': 'smtp.example.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 200
        
        # Verify default value
        settings = GlobalSettings.query.first()
        assert settings.smtp_use_tls is True
    
    def test_post_defaults_smtp_enabled_false(self, client, admin_user, db_session):
        """Test POST request defaults smtp_enabled to False."""
        # Delete any existing settings first
        db_session.query(GlobalSettings).delete()
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        data = {
            'smtp_server': 'smtp.example.com'
        }
        
        response = client.post('/admin/smtp_settings', json=data)
        assert response.status_code == 200
        
        # Verify default value
        settings = GlobalSettings.query.first()
        assert settings.smtp_enabled is False


class TestSmtpTest:
    """Test the smtp_test route."""
    
    def test_post_requires_login(self, client):
        """Test that POST request requires login."""
        response = client.post('/admin/smtp_test')
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_post_requires_admin(self, client, test_user):
        """Test that POST request requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/smtp_test')
        assert response.status_code == 302  # Redirected by admin_required
    
    def test_post_no_settings(self, client, admin_user, db_session):
        """Test POST request with no SMTP settings configured."""
        # Delete any existing settings first
        db_session.query(GlobalSettings).delete()
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/smtp_test')
        assert response.status_code == 400
        
        response_data = json.loads(response.data)
        assert response_data['success'] is False
        assert response_data['message'] == 'SMTP settings not configured'
    
    @patch('modules.routes_smtp.SMTPTester')
    def test_post_success(self, mock_smtp_tester_class, client, admin_user, db_session):
        """Test POST request with successful SMTP test."""
        # Delete any default settings and use only our test settings
        db_session.query(GlobalSettings).delete()
        db_session.commit()
        test_settings = create_test_settings(db_session)
        
        # Mock SMTPTester
        mock_tester = MagicMock()
        mock_tester.test_connection.return_value = (True, 'Connection successful')
        mock_smtp_tester_class.return_value = mock_tester
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/smtp_test')
        assert response.status_code == 200
        
        response_data = json.loads(response.data)
        assert response_data['success'] is True
        assert response_data['result'] == 'Connection successful'
        
        # Verify SMTPTester was called correctly
        mock_smtp_tester_class.assert_called_once_with(debug=False)
        mock_tester.test_connection.assert_called_once_with(
            host='smtp.example.com',
            port=587,
            username='test@example.com',
            password='testpassword',
            use_tls=True,
            timeout=10
        )
    
    @patch('modules.routes_smtp.SMTPTester')
    def test_post_failure(self, mock_smtp_tester_class, client, admin_user, db_session):
        """Test POST request with failed SMTP test."""
        # Delete any default settings and use only our test settings
        db_session.query(GlobalSettings).delete()
        db_session.commit()
        test_settings = create_test_settings(db_session)
        
        # Mock SMTPTester
        mock_tester = MagicMock()
        mock_tester.test_connection.return_value = (False, 'Connection failed: Authentication error')
        mock_smtp_tester_class.return_value = mock_tester
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/smtp_test')
        assert response.status_code == 200
        
        response_data = json.loads(response.data)
        assert response_data['success'] is False
        assert response_data['message'] == 'Connection failed: Authentication error'
        
        # Verify SMTPTester was called correctly
        mock_smtp_tester_class.assert_called_once_with(debug=False)
        mock_tester.test_connection.assert_called_once_with(
            host='smtp.example.com',
            port=587,
            username='test@example.com',
            password='testpassword',
            use_tls=True,
            timeout=10
        )
    
    @patch('modules.routes_smtp.SMTPTester')
    @patch('builtins.print')
    def test_post_debug_print(self, mock_print, mock_smtp_tester_class, client, admin_user, db_session):
        """Test POST request includes debug print statement."""
        # Delete any default settings and use only our test settings
        db_session.query(GlobalSettings).delete()
        db_session.commit()
        test_settings = create_test_settings(db_session)
        
        # Mock SMTPTester
        mock_tester = MagicMock()
        mock_tester.test_connection.return_value = (True, 'Connection successful')
        mock_smtp_tester_class.return_value = mock_tester
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/smtp_test')
        assert response.status_code == 200
        
        # Verify debug print was called
        mock_print.assert_called_once_with('Testing SMTP connection using settings: smtp.example.com:587')