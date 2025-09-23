import unittest
from unittest.mock import patch, MagicMock
import sys
import os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask
from flask_wtf import CSRFProtect
from wtforms.validators import ValidationError

# Import forms to test
from modules.forms import (
    SetupForm, LoginForm, ResetPasswordRequestForm, AutoScanForm,
    WhitelistForm, EditProfileForm, ScanFolderForm, InviteForm,
    UserDetailForm, UserPasswordForm, NewsletterForm, EditUserForm,
    UserManagementForm, CreateUserForm, IGDBApiForm, AddGameForm,
    ClearDownloadRequestsForm, ReleaseGroupForm, RegistrationForm,
    UserPreferencesForm, LibraryForm, ThemeUploadForm, IGDBSetupForm,
    UpdateUnmatchedFolderForm
)


class TestFormsInitialization(unittest.TestCase):
    """Test form initialization and basic field validation."""

    def setUp(self):
        """Set up Flask app context for testing."""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        self.app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        """Clean up Flask app context."""
        self.ctx.pop()

    def test_setup_form_initialization(self):
        """Test SetupForm initializes with correct fields."""
        form = SetupForm()
        self.assertIn('username', form._fields)
        self.assertIn('email', form._fields)
        self.assertIn('password', form._fields)
        self.assertIn('confirm_password', form._fields)

    def test_login_form_initialization(self):
        """Test LoginForm initializes with correct fields."""
        form = LoginForm()
        self.assertIn('username', form._fields)
        self.assertIn('password', form._fields)

    def test_auto_scan_form_initialization(self):
        """Test AutoScanForm initializes with correct fields."""
        form = AutoScanForm()
        self.assertIn('folder_path', form._fields)
        self.assertIn('library_uuid', form._fields)
        self.assertIn('scan_mode', form._fields)
        self.assertIn('remove_missing', form._fields)
        self.assertIn('download_missing_images', form._fields)
        # Test default scan mode
        self.assertEqual(form.scan_mode.default, 'folders')

    def test_igdb_setup_form_initialization(self):
        """Test IGDBSetupForm initializes with correct fields."""
        form = IGDBSetupForm()
        self.assertIn('igdb_client_id', form._fields)
        self.assertIn('igdb_client_secret', form._fields)

    def test_library_form_initialization(self):
        """Test LibraryForm initializes with correct fields."""
        form = LibraryForm()
        self.assertIn('name', form._fields)
        self.assertIn('platform', form._fields)
        self.assertIn('image', form._fields)


class TestFormValidation(unittest.TestCase):
    """Test form field validation."""

    def setUp(self):
        """Set up Flask app context for testing."""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        """Clean up Flask app context."""
        self.ctx.pop()

    def test_setup_form_valid_data(self):
        """Test SetupForm with valid data."""
        form_data = {
            'username': 'testadmin',
            'email': 'admin@test.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }
        form = SetupForm(data=form_data)
        self.assertTrue(form.validate())

    def test_setup_form_invalid_username_length(self):
        """Test SetupForm with invalid username length."""
        form_data = {
            'username': 'ab',  # Too short
            'email': 'admin@test.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }
        form = SetupForm(data=form_data)
        self.assertFalse(form.validate())
        self.assertIn('Field must be between 3 and 64 characters long', str(form.username.errors))

    def test_setup_form_invalid_username_pattern(self):
        """Test SetupForm with invalid username pattern."""
        form_data = {
            'username': 'test-admin',  # Contains hyphen (invalid)
            'email': 'admin@test.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }
        form = SetupForm(data=form_data)
        self.assertFalse(form.validate())

    def test_setup_form_password_mismatch(self):
        """Test SetupForm with password mismatch."""
        form_data = {
            'username': 'testadmin',
            'email': 'admin@test.com',
            'password': 'password123',
            'confirm_password': 'different123'
        }
        form = SetupForm(data=form_data)
        self.assertFalse(form.validate())
        self.assertIn('Passwords must match', str(form.confirm_password.errors))

    def test_setup_form_short_password(self):
        """Test SetupForm with short password."""
        form_data = {
            'username': 'testadmin',
            'email': 'admin@test.com',
            'password': '1234567',  # 7 characters (too short)
            'confirm_password': '1234567'
        }
        form = SetupForm(data=form_data)
        self.assertFalse(form.validate())

    def test_reset_password_form_invalid_email(self):
        """Test ResetPasswordRequestForm with invalid email."""
        form_data = {'email': 'invalid-email'}
        form = ResetPasswordRequestForm(data=form_data)
        self.assertFalse(form.validate())

    def test_whitelist_form_valid_email(self):
        """Test WhitelistForm with valid email."""
        form_data = {'email': 'user@test.com'}
        form = WhitelistForm(data=form_data)
        self.assertTrue(form.validate())

    def test_invite_form_valid_email(self):
        """Test InviteForm with valid email."""
        form_data = {'email': 'invite@test.com'}
        form = InviteForm(data=form_data)
        self.assertTrue(form.validate())

    def test_user_password_form_valid_data(self):
        """Test UserPasswordForm with valid data."""
        form_data = {
            'password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }
        form = UserPasswordForm(data=form_data)
        self.assertTrue(form.validate())

    def test_user_password_form_short_password(self):
        """Test UserPasswordForm with short password."""
        form_data = {
            'password': '1234567',  # 7 characters
            'confirm_password': '1234567'
        }
        form = UserPasswordForm(data=form_data)
        self.assertFalse(form.validate())

    def test_newsletter_form_valid_data(self):
        """Test NewsletterForm with valid data."""
        form_data = {
            'subject': 'Test Newsletter',
            'content': 'This is test content for the newsletter.'
        }
        form = NewsletterForm(data=form_data)
        self.assertTrue(form.validate())

    def test_newsletter_form_missing_required_fields(self):
        """Test NewsletterForm with missing required fields."""
        form_data = {'subject': 'Test Newsletter'}  # Missing content
        form = NewsletterForm(data=form_data)
        self.assertFalse(form.validate())

    def test_igdb_setup_form_valid_data(self):
        """Test IGDBSetupForm with valid data."""
        form_data = {
            'igdb_client_id': 'abcdefghijklmnopqrstuvwxyz12345',  # 31 chars
            'igdb_client_secret': 'zyxwvutsrqponmlkjihgfedcba54321'  # 31 chars
        }
        form = IGDBSetupForm(data=form_data)
        self.assertTrue(form.validate())

    def test_igdb_setup_form_short_client_id(self):
        """Test IGDBSetupForm with short client ID."""
        form_data = {
            'igdb_client_id': 'short',  # Too short
            'igdb_client_secret': 'zyxwvutsrqponmlkjihgfedcba54321'
        }
        form = IGDBSetupForm(data=form_data)
        self.assertFalse(form.validate())

    def test_theme_upload_form_initialization(self):
        """Test ThemeUploadForm initializes correctly."""
        form = ThemeUploadForm()
        self.assertIn('theme_zip', form._fields)


class TestCustomValidators(unittest.TestCase):
    """Test custom validators in forms."""

    def setUp(self):
        """Set up Flask app context for testing."""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        """Clean up Flask app context."""
        self.ctx.pop()

    def test_create_user_form_reserved_username(self):
        """Test CreateUserForm rejects reserved username."""
        form_data = {
            'username': 'system',
            'email': 'test@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }
        form = CreateUserForm(data=form_data)
        self.assertFalse(form.validate())
        # Check that the custom validation error is raised
        with self.assertRaises(ValidationError):
            form.validate_username(form.username)

    def test_create_user_form_invalid_username_pattern(self):
        """Test CreateUserForm with invalid username pattern."""
        form_data = {
            'username': 'test@user',  # Contains @ (invalid)
            'email': 'test@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }
        form = CreateUserForm(data=form_data)
        self.assertFalse(form.validate())

    def test_create_user_form_username_length_validation(self):
        """Test CreateUserForm username length validation."""
        # Test too short
        form_data = {
            'username': 'ab',
            'email': 'test@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }
        form = CreateUserForm(data=form_data)
        with self.assertRaises(ValidationError):
            form.validate_username(form.username)

        # Test too long
        form_data['username'] = 'a' * 65  # 65 characters
        form = CreateUserForm(data=form_data)
        with self.assertRaises(ValidationError):
            form.validate_username(form.username)

    def test_registration_form_reserved_username(self):
        """Test RegistrationForm rejects reserved username."""
        form_data = {
            'username': 'SYSTEM',  # Should be case-insensitive
            'email': 'test@example.com',
            'password': 'password123'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.validate())

    def test_registration_form_valid_username(self):
        """Test RegistrationForm with valid username."""
        form_data = {
            'username': 'validuser123',
            'email': 'test@example.com',
            'password': 'password123'
        }
        form = RegistrationForm(data=form_data)
        self.assertTrue(form.validate())


class TestFormChoices(unittest.TestCase):
    """Test form choices and select fields."""

    def setUp(self):
        """Set up Flask app context for testing."""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        """Clean up Flask app context."""
        self.ctx.pop()

    def test_igdb_api_form_endpoint_choices(self):
        """Test IGDBApiForm has correct endpoint choices."""
        form = IGDBApiForm()
        expected_endpoints = [
            'https://api.igdb.com/v4/games',
            'https://api.igdb.com/v4/search',
            'https://api.igdb.com/v4/screenshots',
            'https://api.igdb.com/v4/covers',
            'https://api.igdb.com/v4/game_videos',
            'https://api.igdb.com/v4/keywords',
            'https://api.igdb.com/v4/involved_companies',
            'https://api.igdb.com/v4/platforms'
        ]
        form_choices = [choice[0] for choice in form.endpoint.choices]
        for endpoint in expected_endpoints:
            self.assertIn(endpoint, form_choices)

    def test_user_preferences_form_choices(self):
        """Test UserPreferencesForm has correct choices."""
        with patch('modules.forms.ThemeManager') as mock_theme_manager:
            mock_instance = MagicMock()
            mock_instance.get_installed_themes.return_value = [
                {'name': 'dark'},
                {'name': 'light'}
            ]
            mock_theme_manager.return_value = mock_instance
            
            form = UserPreferencesForm()
            
            # Test items per page choices
            expected_items = ['16', '20', '50', '100', '500', '1000']
            form_choices = [choice[0] for choice in form.items_per_page.choices]
            for item in expected_items:
                self.assertIn(item, form_choices)
            
            # Test sort choices
            expected_sorts = ['name', 'rating', 'first_release_date', 'date_identified', 'size']
            form_choices = [choice[0] for choice in form.default_sort.choices]
            for sort in expected_sorts:
                self.assertIn(sort, form_choices)

    def test_release_group_form_choices(self):
        """Test ReleaseGroupForm case-sensitive choices."""
        form = ReleaseGroupForm()
        expected_choices = [('no', 'No'), ('yes', 'Yes')]
        self.assertEqual(form.case_sensitive.choices, expected_choices)
        self.assertEqual(form.case_sensitive.default, 'no')

    def test_scan_folder_form_scan_mode_choices(self):
        """Test ScanFolderForm scan mode choices."""
        form = ScanFolderForm()
        expected_choices = [('folders', 'My Games are Folders'), ('files', 'My Games are Files')]
        self.assertEqual(form.scan_mode.choices, expected_choices)
        self.assertEqual(form.scan_mode.default, 'folders')


class TestFormSpecialCases(unittest.TestCase):
    """Test special cases and edge conditions in forms."""

    def setUp(self):
        """Set up Flask app context for testing."""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        """Clean up Flask app context."""
        self.ctx.pop()

    def test_update_unmatched_folder_form_hidden_fields(self):
        """Test UpdateUnmatchedFolderForm hidden fields."""
        form = UpdateUnmatchedFolderForm()
        self.assertEqual(form.new_status.default, 'Ignore')
        self.assertTrue(hasattr(form, 'folder_id'))

    def test_csrf_protect_form_empty(self):
        """Test CsrfProtectForm is empty."""
        from modules.forms import CsrfProtectForm, CsrfForm
        csrf_form = CsrfProtectForm()
        # Should have no fields except CSRF token
        field_names = [name for name in csrf_form._fields.keys() if name != 'csrf_token']
        self.assertEqual(len(field_names), 0)
        
        csrf_form2 = CsrfForm()
        field_names2 = [name for name in csrf_form2._fields.keys() if name != 'csrf_token']
        self.assertEqual(len(field_names2), 0)

    def test_clear_download_requests_form_simple(self):
        """Test ClearDownloadRequestsForm has only submit button."""
        form = ClearDownloadRequestsForm()
        field_names = [name for name in form._fields.keys() if name != 'csrf_token']
        self.assertEqual(field_names, ['submit'])

    @patch('modules.forms.comma_separated_urls')
    def test_add_game_form_video_urls_validator(self, mock_validator):
        """Test AddGameForm uses comma_separated_urls validator."""
        mock_validator.return_value = True
        form = AddGameForm()
        self.assertIn('video_urls', form._fields)

    def test_edit_profile_form_file_validation(self):
        """Test EditProfileForm file validation."""
        form = EditProfileForm()
        self.assertIn('avatar', form._fields)
        # The field should have FileAllowed validator for images

    def test_user_management_form_optional_fields(self):
        """Test UserManagementForm optional field validators."""
        form = UserManagementForm()
        # Check that is_email_verified and about have Optional validators
        self.assertIn('is_email_verified', form._fields)
        self.assertIn('about', form._fields)

    def test_library_form_file_field(self):
        """Test LibraryForm image file field."""
        form = LibraryForm()
        self.assertIn('image', form._fields)
        # Should allow image files only


if __name__ == '__main__':
    unittest.main()