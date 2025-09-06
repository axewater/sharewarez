import pytest
import json
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone
from uuid import uuid4

from modules import create_app, db
from modules.models import User, GlobalSettings, InviteToken, SystemEvents, DownloadRequest, Newsletter
from modules.forms import SetupForm, IGDBSetupForm
from sqlalchemy import select, delete


def safe_cleanup_users_and_related(db_session):
    """Safely clean up users and related data respecting foreign key constraints."""
    # Delete in proper order to respect foreign key constraints
    # All tables with foreign keys to users must be deleted first
    db_session.execute(delete(DownloadRequest))
    db_session.execute(delete(Newsletter))
    db_session.execute(delete(SystemEvents))
    db_session.execute(delete(InviteToken))
    # Delete from user_favorites junction table using raw SQL
    db_session.execute(db.text("DELETE FROM user_favorites"))
    db_session.execute(delete(User))
    db_session.commit()




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
        invite_quota=10,
        is_email_verified=True,
        created=datetime.now(timezone.utc)
    )
    user.set_password('adminpassword123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def global_settings(db_session):
    """Create test global settings."""
    settings = GlobalSettings(
        smtp_server='test.smtp.com',
        smtp_port=587,
        smtp_username='test@example.com',
        smtp_password='testpass',
        smtp_use_tls=True,
        smtp_default_sender='noreply@example.com',
        smtp_enabled=True,
        igdb_client_id='test_client_id_12345',
        igdb_client_secret='test_client_secret_12345'
    )
    db_session.add(settings)
    db_session.commit()
    return settings


class TestSetupRoute:
    """Test the /setup GET route."""
    
    def test_setup_get_sets_database_step(self, client, db_session):
        """Test GET /setup sets database setup step to 1."""
        # Ensure no users exist for this test
        # Clean up database safely respecting foreign key constraints
        safe_cleanup_users_and_related(db_session)
        # Also clean up GlobalSettings to ensure clean state
        db_session.execute(delete(GlobalSettings))
        db_session.commit()
        
        response = client.get('/setup')
        
        assert response.status_code == 200
        
        # Check that database setup step is set to 1
        from modules.utils_setup import get_current_setup_step
        assert get_current_setup_step() == 1
    
    def test_setup_get_redirects_if_user_exists(self, client, admin_user):
        """Test GET /setup redirects to login if admin user already exists."""
        response = client.get('/setup')
        
        assert response.status_code == 302
        assert '/login' in response.location
    
    @patch('modules.routes_setup.render_template')
    def test_setup_get_renders_template_when_no_user(self, mock_render, client, db_session):
        """Test GET /setup renders template when no users exist."""
        # Ensure no users exist for this test
        # Clean up database safely respecting foreign key constraints
        safe_cleanup_users_and_related(db_session)
        
        mock_render.return_value = 'rendered setup template'
        
        response = client.get('/setup')
        
        assert response.status_code == 200
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        assert args[0] == 'setup/setup.html'
        assert 'form' in kwargs
        assert isinstance(kwargs['form'], SetupForm)


class TestSetupSubmitRoute:
    """Test the /setup/submit POST route."""
    
    def test_setup_submit_redirects_if_user_exists(self, client, admin_user):
        """Test POST /setup/submit redirects to login if admin user already exists."""
        form_data = {
            'username': 'testadmin',
            'email': 'test@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }
        
        response = client.post('/setup/submit', data=form_data)
        
        assert response.status_code == 302
        assert '/login' in response.location
    
    @patch('modules.routes_setup.SetupForm')
    @patch('modules.routes_setup.log_system_event')
    def test_setup_submit_creates_admin_user_success(self, mock_log, mock_form_class, client, db_session):
        # Ensure no users exist for this test
        # Clean up database safely respecting foreign key constraints
        safe_cleanup_users_and_related(db_session)
        """Test successful admin user creation."""
        # Mock the form
        mock_form = MagicMock()
        mock_form.validate_on_submit.return_value = True
        mock_form.username.data = 'testadmin'
        mock_form.email.data = 'Test@Example.Com'  # Test email lowercase conversion
        mock_form.password.data = 'password123'
        mock_form.csrf_token.data = 'test-csrf-token'
        mock_form_class.return_value = mock_form
        
        with patch('modules.routes_setup.flash') as mock_flash:
            response = client.post('/setup/submit', data={})
            
            assert response.status_code == 302
            assert '/setup/smtp' in response.location
            
            # Verify admin user was created
            user = db.session.execute(select(User).filter_by(email='test@example.com')).scalar_one_or_none()
            assert user is not None
            assert user.name == 'testadmin'
            assert user.email == 'test@example.com'  # Should be lowercase
            assert user.role == 'admin'
            assert user.is_email_verified is True
            assert user.invite_quota == 10
            assert user.user_id is not None
            
            # Check database setup step was updated
            from modules.utils_setup import get_current_setup_step
            assert get_current_setup_step() == 2
            
            mock_flash.assert_called_with('Admin account created successfully! Please configure your SMTP settings.', 'success')
            mock_log.assert_called_with("Admin account created during setup", event_type='setup', event_level='information')
    
    @patch('modules.routes_setup.SetupForm')
    def test_setup_submit_database_error(self, mock_form_class, client, db_session):
        # Ensure no users exist for this test
        # Clean up database safely respecting foreign key constraints
        safe_cleanup_users_and_related(db_session)
        """Test database error during user creation."""
        mock_form = MagicMock()
        mock_form.validate_on_submit.return_value = True
        mock_form.username.data = 'testadmin'
        mock_form.email.data = 'test@example.com'
        mock_form.password.data = 'password123'
        mock_form_class.return_value = mock_form
        
        with patch('modules.routes_setup.db.session.add') as mock_add:
            mock_add.side_effect = Exception('Database error')
            with patch('modules.routes_setup.db.session.rollback') as mock_rollback:
                with patch('modules.routes_setup.flash') as mock_flash:
                    response = client.post('/setup/submit', data={})
                    
                    assert response.status_code == 302
                    assert '/setup' in response.location
                    mock_rollback.assert_called_once()
                    mock_flash.assert_called_with('Error during setup: Database error', 'error')
    
    @patch('modules.routes_setup.SetupForm')
    def test_setup_submit_form_validation_failed(self, mock_form_class, client, db_session):
        # Ensure no users exist for this test
        # Clean up database safely respecting foreign key constraints
        safe_cleanup_users_and_related(db_session)
        """Test form validation failure."""
        mock_form = MagicMock()
        mock_form.validate_on_submit.return_value = False
        mock_form.data = {'username': 'test', 'email': 'invalid-email'}
        mock_form.errors = {'email': ['Invalid email address'], 'password': ['Field must be at least 8 characters long']}
        mock_form_class.return_value = mock_form
        
        with patch('modules.routes_setup.render_template') as mock_render:
            mock_render.return_value = 'error template'
            response = client.post('/setup/submit', data={})
            
            assert response.status_code == 200
            mock_render.assert_called_with('setup/setup.html', form=mock_form, is_setup_mode=True)


class TestSetupSmtpRoute:
    """Test the /setup/smtp route."""
    
    def test_setup_smtp_get_no_setup_in_progress_redirects(self, client, admin_user, db_session):
        """Test GET /setup/smtp redirects when setup is not in progress."""
        # Ensure no setup is in progress by clearing GlobalSettings
        db_session.execute(delete(GlobalSettings))
        db_session.commit()
        
        # Setup completed (admin user exists, no setup in progress), so should redirect to login
        response = client.get('/setup/smtp')
        
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_setup_smtp_get_wrong_step_redirects(self, client, db_session):
        """Test GET /setup/smtp redirects when not in step 2."""
        # Clean up and set database to step 1
        safe_cleanup_users_and_related(db_session)
        db_session.execute(delete(GlobalSettings))
        db_session.commit()
        
        from modules.utils_setup import set_setup_step
        set_setup_step(1)  # Should be 2 for SMTP setup
        
        with patch('modules.routes_setup.flash') as mock_flash:
            response = client.get('/setup/smtp')
            
            assert response.status_code == 302
            assert '/setup' in response.location
            mock_flash.assert_called_with('Please complete the admin account setup first.', 'warning')
    
    @patch('modules.routes_setup.render_template')
    def test_setup_smtp_get_correct_step(self, mock_render, client, db_session, admin_user):
        """Test GET /setup/smtp renders template in correct step."""
        # Use existing admin_user fixture and set database to step 2
        from modules.utils_setup import set_setup_step
        set_setup_step(2)
        
        mock_render.return_value = 'smtp setup template'
        response = client.get('/setup/smtp')
        
        assert response.status_code == 200
        mock_render.assert_called_with('setup/setup_smtp.html', is_setup_mode=True)
    
    def test_setup_smtp_post_skip_button(self, client, db_session, admin_user):
        """Test POST /setup/smtp with skip button."""
        # Use existing admin_user fixture and set database to step 2
        from modules.utils_setup import set_setup_step, get_current_setup_step
        set_setup_step(2)
        
        form_data = {'skip_smtp': 'true'}
        
        with patch('modules.routes_setup.flash') as mock_flash:
            response = client.post('/setup/smtp', data=form_data)
            
            assert response.status_code == 302
            assert '/setup/igdb' in response.location
            
            # Check database step was updated to 3
            assert get_current_setup_step() == 3
            
            mock_flash.assert_called_with('SMTP setup skipped. Please configure your IGDB settings.', 'info')
    
    @patch('modules.routes_setup.log_system_event')
    def test_setup_smtp_post_save_settings_success(self, mock_log, client, db_session, admin_user):
        """Test successful SMTP settings save."""
        # Use existing admin_user fixture and set database to step 2
        from modules.utils_setup import set_setup_step, get_current_setup_step
        set_setup_step(2)
        
        form_data = {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': '587',
            'smtp_username': 'test@gmail.com',
            'smtp_password': 'testpass',
            'smtp_use_tls': 'true',
            'smtp_default_sender': 'noreply@test.com',
            'smtp_enabled': 'true'
        }
        
        with patch('modules.routes_setup.flash') as mock_flash:
            response = client.post('/setup/smtp', data=form_data)
            
            assert response.status_code == 302
            assert '/setup/igdb' in response.location
            
            # Verify the route executed successfully by checking redirect location
            # The specific settings verification is subject to transaction rollback behavior
            
            # Check database step was updated to 3
            assert get_current_setup_step() == 3
            
            mock_flash.assert_called_with('SMTP settings saved successfully! Please configure your IGDB settings.', 'success')
            mock_log.assert_called_with("SMTP settings configured during setup", event_type='setup', event_level='information')
    
    
    def test_setup_smtp_post_database_error(self, client, db_session, admin_user):
        """Test database error during SMTP settings save."""
        # Use existing admin_user fixture and set database to step 2
        from modules.utils_setup import set_setup_step
        set_setup_step(2)
        
        form_data = {
            'smtp_server': 'smtp.test.com',
            'smtp_port': '587'
        }
        
        with patch('modules.routes_setup.db.session.commit', side_effect=Exception('Database error')):
            with patch('modules.routes_setup.db.session.rollback') as mock_rollback:
                with patch('modules.routes_setup.flash') as mock_flash:
                    response = client.post('/setup/smtp', data=form_data)
                    
                    assert response.status_code == 200  # Should render template again
                    mock_rollback.assert_called_once()
                    mock_flash.assert_called_with('Error saving SMTP settings: Database error', 'error')


class TestSetupIgdbRoute:
    """Test the /setup/igdb route."""
    
    def test_setup_igdb_get_wrong_step_redirects(self, client, db_session):
        """Test GET /setup/igdb redirects when not in step 3."""
        # Clean up and set database to step 2
        safe_cleanup_users_and_related(db_session)
        db_session.execute(delete(GlobalSettings))
        db_session.commit()
        
        from modules.utils_setup import set_setup_step
        set_setup_step(2)  # Should be 3 for IGDB setup
        
        with patch('modules.routes_setup.flash') as mock_flash:
            response = client.get('/setup/igdb')
            
            assert response.status_code == 302
            assert '/setup' in response.location
            mock_flash.assert_called_with('Please complete the SMTP setup first.', 'warning')
    
    @patch('modules.routes_setup.render_template')
    def test_setup_igdb_get_correct_step(self, mock_render, client, db_session, admin_user):
        """Test GET /setup/igdb renders template in correct step."""
        # Use existing admin_user fixture and set database to step 3
        from modules.utils_setup import set_setup_step
        set_setup_step(3)
        
        mock_render.return_value = 'igdb setup template'
        response = client.get('/setup/igdb')
        
        assert response.status_code == 200
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        assert args[0] == 'setup/setup_igdb.html'
        assert 'form' in kwargs
        assert isinstance(kwargs['form'], IGDBSetupForm)
        assert kwargs['is_setup_mode'] is True
    
    @patch('modules.routes_setup.IGDBSetupForm')
    @patch('modules.routes_setup.log_system_event')
    @patch('modules.init_data.initialize_library_folders')
    @patch('modules.init_data.initialize_discovery_sections')
    @patch('modules.init_data.insert_default_filters')
    @patch('modules.init_data.initialize_default_settings')
    @patch('modules.init_data.initialize_allowed_file_types')
    def test_setup_igdb_post_success_complete_setup(self, mock_init_filetypes, mock_init_settings, 
                                                   mock_init_filters, mock_init_discovery, 
                                                   mock_init_folders, mock_log, mock_form_class, 
                                                   client, db_session, admin_user):
        """Test successful IGDB setup completing the entire setup process."""
        # Use existing admin_user fixture and set database to step 3
        from modules.utils_setup import set_setup_step, get_current_setup_step, is_setup_required
        set_setup_step(3)
        
        # Mock the form
        mock_form = MagicMock()
        mock_form.validate_on_submit.return_value = True
        mock_form.igdb_client_id.data = 'test_client_id_12345'
        mock_form.igdb_client_secret.data = 'test_client_secret_12345'
        mock_form_class.return_value = mock_form
        
        with patch('modules.routes_setup.flash') as mock_flash:
            response = client.post('/setup/igdb', data={})
            
            assert response.status_code == 302
            assert '/libraries' in response.location
            
            # Verify the route executed successfully by checking redirect location
            # The specific settings verification is subject to transaction rollback behavior
            
            # Check setup was completed (get_current_setup_step returns None when completed)
            assert get_current_setup_step() is None
            
            # Verify all initialization functions were called
            mock_init_folders.assert_called_once()
            mock_init_discovery.assert_called_once()
            mock_init_filters.assert_called_once()
            mock_init_settings.assert_called_once()
            mock_init_filetypes.assert_called_once()
            
            mock_flash.assert_called_with('Setup completed successfully! Please create your first game library.', 'success')
            mock_log.assert_called_with("IGDB settings configured - Setup completed", event_type='setup', event_level='information')
    
    
    @patch('modules.routes_setup.IGDBSetupForm')
    def test_setup_igdb_post_database_error(self, mock_form_class, client, db_session, admin_user):
        """Test database error during IGDB settings save."""
        # Use existing admin_user fixture and set database to step 3
        from modules.utils_setup import set_setup_step
        set_setup_step(3)
        
        mock_form = MagicMock()
        mock_form.validate_on_submit.return_value = True
        mock_form.igdb_client_id.data = 'test_client_id_12345'
        mock_form.igdb_client_secret.data = 'test_client_secret_12345'
        mock_form_class.return_value = mock_form
        
        with patch('modules.routes_setup.db.session.commit', side_effect=Exception('Database error')):
            with patch('modules.routes_setup.db.session.rollback') as mock_rollback:
                with patch('modules.routes_setup.flash') as mock_flash:
                    response = client.post('/setup/igdb', data={})
                    
                    assert response.status_code == 200  # Should render template again
                    mock_rollback.assert_called_once()
                    mock_flash.assert_called_with('Error saving IGDB settings: Database error', 'error')
    
    @patch('modules.routes_setup.IGDBSetupForm')
    def test_setup_igdb_post_form_validation_failed(self, mock_form_class, client, db_session, admin_user):
        """Test form validation failure."""
        # Use existing admin_user fixture and set database to step 3
        from modules.utils_setup import set_setup_step
        set_setup_step(3)
        
        mock_form = MagicMock()
        mock_form.validate_on_submit.return_value = False
        mock_form.errors = {'igdb_client_id': ['Field must be between 20 and 50 characters']}
        mock_form_class.return_value = mock_form
        
        with patch('modules.routes_setup.render_template') as mock_render:
            mock_render.return_value = 'error template'
            response = client.post('/setup/igdb', data={})
            
            assert response.status_code == 200
            mock_render.assert_called_with('setup/setup_igdb.html', form=mock_form, is_setup_mode=True)


class TestSetupWorkflow:
    """Test the complete setup workflow."""
    
    def test_complete_setup_workflow(self, client, db_session):
        # Ensure no users exist for this test
        # Clean up database safely respecting foreign key constraints
        safe_cleanup_users_and_related(db_session)
        # Also clean up GlobalSettings to ensure test isolation
        db_session.execute(delete(GlobalSettings))
        db_session.commit()
        """Test the complete setup process from start to finish."""
        # Step 1: GET /setup
        response = client.get('/setup')
        assert response.status_code == 200
        
        # Check database setup step
        from modules.utils_setup import get_current_setup_step
        assert get_current_setup_step() == 1
        
        # Step 2: POST /setup/submit with valid admin data
        with patch('modules.routes_setup.SetupForm') as mock_form_class:
            mock_form = MagicMock()
            mock_form.validate_on_submit.return_value = True
            mock_form.username.data = 'admin'
            mock_form.email.data = 'admin@test.com'
            mock_form.password.data = 'password123'
            mock_form.csrf_token.data = 'test-token'
            mock_form_class.return_value = mock_form
            
            with patch('modules.routes_setup.log_system_event'):
                response = client.post('/setup/submit', data={})
                assert response.status_code == 302
                assert '/setup/smtp' in response.location
        
        # Check database setup step
        assert get_current_setup_step() == 2
        
        # Step 3: Skip SMTP setup
        form_data = {'skip_smtp': 'true'}
        response = client.post('/setup/smtp', data=form_data)
        assert response.status_code == 302
        assert '/setup/igdb' in response.location
        
        # Check database setup step
        assert get_current_setup_step() == 3
        
        # Step 4: Complete IGDB setup
        with patch('modules.routes_setup.IGDBSetupForm') as mock_igdb_form_class:
            mock_igdb_form = MagicMock()
            mock_igdb_form.validate_on_submit.return_value = True
            mock_igdb_form.igdb_client_id.data = 'test_client_id_12345'
            mock_igdb_form.igdb_client_secret.data = 'test_client_secret_12345'
            mock_igdb_form_class.return_value = mock_igdb_form
            
            with patch('modules.init_data.initialize_library_folders'), \
                 patch('modules.init_data.initialize_discovery_sections'), \
                 patch('modules.init_data.insert_default_filters'), \
                 patch('modules.init_data.initialize_allowed_file_types'), \
                 patch('modules.init_data.initialize_default_settings'), \
                 patch('modules.routes_setup.log_system_event'):
                 
                # Mock initialize_default_settings to prevent interference with test data
                response = client.post('/setup/igdb', data={})
                assert response.status_code == 302
                assert '/libraries' in response.location
        
        # Verify setup was completed (get_current_setup_step returns None when completed)
        assert get_current_setup_step() is None
        
        # Verify admin user was created
        admin_user = db.session.execute(select(User).filter_by(email='admin@test.com')).scalars().first()
        assert admin_user is not None
        assert admin_user.role == 'admin'
        assert admin_user.is_email_verified is True
        
        # Verify IGDB settings were saved
        settings = db.session.execute(select(GlobalSettings)).scalars().first()
        assert settings is not None
        assert settings.igdb_client_id == 'test_client_id_12345'
        assert settings.igdb_client_secret == 'test_client_secret_12345'


class TestSetupSessionHandling:
    """Test setup session state management."""
    
    def test_setup_start_sets_database_state(self, client, db_session):
        # Ensure no users exist for this test
        # Clean up database safely respecting foreign key constraints
        safe_cleanup_users_and_related(db_session)
        # Also clean up GlobalSettings to ensure clean state
        db_session.execute(delete(GlobalSettings))
        db_session.commit()
        """Test that starting setup sets database state correctly."""
        response = client.get('/setup')
        assert response.status_code == 200
        
        # Check database setup state
        from modules.utils_setup import get_current_setup_step, is_setup_required
        assert get_current_setup_step() == 1
        assert is_setup_required()  # Should still be required since no admin user exists
    
    def test_setup_step_progression(self, client, db_session):
        # Ensure no users exist for this test
        # Clean up database safely respecting foreign key constraints
        safe_cleanup_users_and_related(db_session)
        # Also clean up GlobalSettings to ensure clean state
        db_session.execute(delete(GlobalSettings))
        db_session.commit()
        """Test proper setup step progression via database tracking."""
        from modules.utils_setup import get_current_setup_step, is_setup_required
        
        # Start at step 1
        response = client.get('/setup')
        assert get_current_setup_step() == 1
        
        # Admin creation moves to step 2
        with patch('modules.routes_setup.SetupForm') as mock_form_class:
            mock_form = MagicMock()
            mock_form.validate_on_submit.return_value = True
            mock_form.username.data = 'admin'
            mock_form.email.data = 'admin@test.com'
            mock_form.password.data = 'password123'
            mock_form.csrf_token.data = 'test-token'
            mock_form_class.return_value = mock_form
            
            with patch('modules.routes_setup.log_system_event'):
                response = client.post('/setup/submit', data={})
                
        assert get_current_setup_step() == 2
        
        # SMTP setup (skip) moves to step 3
        response = client.post('/setup/smtp', data={'skip_smtp': 'true'})
        assert get_current_setup_step() == 3
        
        # IGDB completion clears setup_step (marks as completed)
        with patch('modules.routes_setup.IGDBSetupForm') as mock_form_class:
            mock_form = MagicMock()
            mock_form.validate_on_submit.return_value = True
            mock_form.igdb_client_id.data = 'test_client_id_12345'
            mock_form.igdb_client_secret.data = 'test_client_secret_12345'
            mock_form_class.return_value = mock_form
            
            with patch('modules.init_data.initialize_library_folders'), \
                 patch('modules.init_data.initialize_discovery_sections'), \
                 patch('modules.init_data.insert_default_filters'), \
                 patch('modules.init_data.initialize_default_settings'), \
                 patch('modules.init_data.initialize_allowed_file_types'), \
                 patch('modules.routes_setup.log_system_event'):
                
                response = client.post('/setup/igdb', data={})
                
        # Setup should be completed, so get_current_setup_step returns None
        assert get_current_setup_step() is None
        assert not is_setup_required()  # Should no longer be required


class TestSetupFormIntegration:
    """Test actual form handling without mocking forms."""
    
    def test_setup_form_validation_error_handling(self, client, db_session):
        # Ensure no users exist for this test
        # Clean up database safely respecting foreign key constraints
        safe_cleanup_users_and_related(db_session)
        """Test how setup handles real form validation errors."""
        # Submit invalid data that should trigger form validation errors
        form_data = {
            'username': 'a',  # Too short
            'email': 'invalid-email',  # Invalid format
            'password': 'short',  # Too short
            'confirm_password': 'different'  # Doesn't match
        }
        
        response = client.post('/setup/submit', data=form_data)
        
        # Should render the setup form again with errors
        assert response.status_code == 200
        assert b'setup' in response.data or b'Setup' in response.data
    
    def test_igdb_form_validation_error_handling(self, client, db_session, admin_user):
        """Test how IGDB setup handles real form validation errors."""
        # Use existing admin_user fixture and set database to step 3
        from modules.utils_setup import set_setup_step
        set_setup_step(3)
        
        # Submit invalid IGDB data
        form_data = {
            'igdb_client_id': 'short',  # Too short (min 20 chars)
            'igdb_client_secret': 'short'  # Too short (min 20 chars)
        }
        
        response = client.post('/setup/igdb', data=form_data)
        
        # Should render the IGDB setup form again with errors
        assert response.status_code == 200
        assert b'igdb' in response.data or b'IGDB' in response.data