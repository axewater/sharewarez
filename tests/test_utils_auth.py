import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from flask import url_for, request
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from modules import create_app, db
from modules.models import User
from modules.utils_auth import load_user, _authenticate_and_redirect, admin_required


def safe_cleanup_database(db_session):
    """Safely clean up database records respecting foreign key constraints.""" 
    from sqlalchemy import delete
    
    db_session.execute(delete(User))
    db_session.commit()




@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        name=f'testuser_{unique_id}',
        email=f'test_{unique_id}@example.com',
        role='user',
        state=True,
        user_id=f'test-user-id-{unique_id}'
    )
    user.set_password('testpassword123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_admin_user(db_session):
    """Create a test admin user."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    admin = User(
        name=f'admin_{unique_id}',
        email=f'admin_{unique_id}@example.com',
        role='admin',
        state=True,
        user_id=f'admin-user-id-{unique_id}'
    )
    admin.set_password('adminpassword123')
    db_session.add(admin)
    db_session.commit()
    return admin


class TestLoadUser:
    """Test the load_user function for Flask-Login."""
    
    def test_load_user_existing_user(self, app, db_session, test_user):
        """Test loading an existing user by ID."""
        with app.app_context():
            loaded_user = load_user(test_user.id)
            assert loaded_user is not None
            assert loaded_user.id == test_user.id
            assert loaded_user.name == test_user.name
            assert loaded_user.email == test_user.email
    
    def test_load_user_nonexistent_user(self, app, db_session):
        """Test loading a non-existent user returns None."""
        with app.app_context():
            loaded_user = load_user(99999)
            assert loaded_user is None
    
    def test_load_user_invalid_id_format(self, app, db_session):
        """Test loading with invalid ID format raises ValueError."""
        with app.app_context():
            with pytest.raises(ValueError):
                load_user('invalid_id')


class TestAuthenticateAndRedirect:
    """Test the _authenticate_and_redirect function."""
    
    @patch('modules.utils_auth.login_user')
    @patch('modules.utils_auth.flash')
    @patch('modules.utils_auth.redirect')
    @patch('modules.utils_auth.url_for')
    def test_successful_authentication(self, mock_url_for, mock_redirect, 
                                     mock_flash, mock_login_user, app, db_session, test_user):
        """Test successful authentication with valid credentials."""
        with app.app_context():
            with app.test_request_context('/?next='):
                # Setup mocks
                mock_url_for.return_value = '/discover'
                mock_redirect.return_value = 'redirect_response'
                
                # Call the function
                result = _authenticate_and_redirect(test_user.name, 'testpassword123')
                
                # Verify user was logged in
                mock_login_user.assert_called_once()
                args, kwargs = mock_login_user.call_args
                assert args[0].id == test_user.id  # Compare by ID
                assert kwargs['remember'] is True
                
                # Verify redirect to discover page
                mock_url_for.assert_called_with('discover.discover')
                mock_redirect.assert_called_with('/discover')
                
                # Verify flash was not called (no error)
                mock_flash.assert_not_called()
                
                # Note: lastlogin update is tested separately in integration tests
                # since mocking makes it difficult to verify DB state changes
                
                assert result == 'redirect_response'
    
    @patch('modules.utils_auth.flash')
    @patch('modules.utils_auth.redirect')
    @patch('modules.utils_auth.url_for')
    def test_invalid_username(self, mock_url_for, mock_redirect, mock_flash, app, db_session):
        """Test authentication with invalid username."""
        with app.app_context():
            # Setup mocks
            mock_url_for.return_value = '/login'
            mock_redirect.return_value = 'login_redirect'
            
            # Call the function
            result = _authenticate_and_redirect('nonexistent', 'password')
            
            # Verify error flash message
            mock_flash.assert_called_once_with('Invalid username or password', 'error')
            
            # Verify redirect to login
            mock_url_for.assert_called_with('login.login')
            mock_redirect.assert_called_with('/login')
            
            assert result == 'login_redirect'
    
    @patch('modules.utils_auth.flash')
    @patch('modules.utils_auth.redirect')
    @patch('modules.utils_auth.url_for')
    def test_invalid_password(self, mock_url_for, mock_redirect, mock_flash, 
                            app, db_session, test_user):
        """Test authentication with valid username but invalid password."""
        with app.app_context():
            # Setup mocks
            mock_url_for.return_value = '/login'
            mock_redirect.return_value = 'login_redirect'
            
            # Call the function
            result = _authenticate_and_redirect(test_user.name, 'wrongpassword')
            
            # Verify error flash message
            mock_flash.assert_called_once_with('Invalid username or password', 'error')
            
            # Verify redirect to login
            mock_url_for.assert_called_with('login.login')
            mock_redirect.assert_called_with('/login')
            
            assert result == 'login_redirect'
    
    @patch('modules.utils_auth.login_user')
    @patch('modules.utils_auth.redirect')
    def test_redirect_to_next_page(self, mock_redirect, mock_login_user, 
                                 app, db_session, test_user):
        """Test redirect to 'next' page after successful authentication."""
        with app.app_context():
            with app.test_request_context('/?next=/admin/dashboard'):
                # Setup mocks - simulate 'next' parameter
                mock_redirect.return_value = 'next_page_redirect'
                
                # Call the function
                result = _authenticate_and_redirect(test_user.name, 'testpassword123')
                
                # Verify redirect to the 'next' page
                mock_redirect.assert_called_with('/admin/dashboard')
                assert result == 'next_page_redirect'
    
    @patch('modules.utils_auth.login_user')
    @patch('modules.utils_auth.redirect')
    @patch('modules.utils_auth.url_for')
    def test_prevent_external_redirect(self, mock_url_for, mock_redirect, 
                                     mock_login_user, app, db_session, test_user):
        """Test that external redirects are prevented for security."""
        with app.app_context():
            with app.test_request_context('/?next=http://evil.com/steal'):
                # Setup mocks - simulate external URL in 'next' parameter
                mock_url_for.return_value = '/discover'
                mock_redirect.return_value = 'safe_redirect'
                
                # Call the function
                result = _authenticate_and_redirect(test_user.name, 'testpassword123')
                
                # Verify redirect goes to discover page, not external URL
                mock_url_for.assert_called_with('discover.discover')
                mock_redirect.assert_called_with('/discover')
                assert result == 'safe_redirect'
    
    @patch('modules.utils_auth.login_user')
    @patch('modules.utils_auth.redirect')
    @patch('modules.utils_auth.url_for')
    def test_case_insensitive_username(self, mock_url_for, mock_redirect,
                                     mock_login_user, app, db_session, test_user):
        """Test that username matching is case-insensitive."""
        with app.app_context():
            with app.test_request_context('/?next='):
                # Setup mocks
                mock_url_for.return_value = '/discover'
                mock_redirect.return_value = 'redirect_response'
                
                # Call the function with different case username
                result = _authenticate_and_redirect(test_user.name.upper(), 'testpassword123')
                
                # Verify user was still logged in despite case difference
                mock_login_user.assert_called_once()
                args, kwargs = mock_login_user.call_args
                assert args[0].id == test_user.id  # Compare by ID
                assert kwargs['remember'] is True
                assert result == 'redirect_response'


class TestAdminRequired:
    """Test the admin_required decorator."""
    
    def test_unauthenticated_user_denied(self, app, client):
        """Test that unauthenticated users are redirected to login."""
        
        @admin_required
        def protected_view():
            return 'admin content'
        
        with app.app_context():
            with patch('modules.utils_auth.current_user') as mock_user:
                mock_user.is_authenticated = False
                
                with patch('modules.utils_auth.flash') as mock_flash:
                    with patch('modules.utils_auth.redirect') as mock_redirect:
                        with patch('modules.utils_auth.url_for') as mock_url_for:
                            mock_url_for.return_value = '/login'
                            mock_redirect.return_value = 'login_redirect'
                            
                            result = protected_view()
                            
                            # Verify flash message and redirect
                            mock_flash.assert_called_once_with(
                                "You must be an admin to access this page.", "danger"
                            )
                            mock_url_for.assert_called_with('login.login')
                            mock_redirect.assert_called_with('/login')
                            assert result == 'login_redirect'
    
    def test_non_admin_user_denied(self, app, client):
        """Test that authenticated non-admin users are denied access."""
        
        @admin_required
        def protected_view():
            return 'admin content'
        
        with app.app_context():
            with patch('modules.utils_auth.current_user') as mock_user:
                mock_user.is_authenticated = True
                mock_user.role = 'user'  # Not admin
                
                with patch('modules.utils_auth.flash') as mock_flash:
                    with patch('modules.utils_auth.redirect') as mock_redirect:
                        with patch('modules.utils_auth.url_for') as mock_url_for:
                            mock_url_for.return_value = '/login'
                            mock_redirect.return_value = 'login_redirect'
                            
                            result = protected_view()
                            
                            # Verify flash message and redirect
                            mock_flash.assert_called_once_with(
                                "You must be an admin to access this page.", "danger"
                            )
                            mock_url_for.assert_called_with('login.login')
                            mock_redirect.assert_called_with('/login')
                            assert result == 'login_redirect'
    
    def test_admin_user_allowed(self, app, client):
        """Test that admin users can access protected views."""
        
        @admin_required
        def protected_view():
            return 'admin content'
        
        with app.app_context():
            with patch('modules.utils_auth.current_user') as mock_user:
                mock_user.is_authenticated = True
                mock_user.role = 'admin'  # Admin role
                
                result = protected_view()
                
                # Verify the protected view was executed
                assert result == 'admin content'
    
    def test_decorator_preserves_function_metadata(self, app):
        """Test that the decorator preserves the original function's metadata."""
        
        @admin_required
        def protected_view():
            """This is a protected admin view."""
            return 'admin content'
        
        # Verify function name and docstring are preserved
        assert protected_view.__name__ == 'protected_view'
        assert protected_view.__doc__ == 'This is a protected admin view.'
    
    def test_decorator_with_arguments(self, app, client):
        """Test that the decorator works with functions that have arguments."""
        
        @admin_required
        def protected_view_with_args(arg1, arg2, kwarg1=None):
            return f'admin content: {arg1}, {arg2}, {kwarg1}'
        
        with app.app_context():
            with patch('modules.utils_auth.current_user') as mock_user:
                mock_user.is_authenticated = True
                mock_user.role = 'admin'
                
                result = protected_view_with_args('test1', 'test2', kwarg1='test3')
                
                # Verify arguments are passed correctly
                assert result == 'admin content: test1, test2, test3'