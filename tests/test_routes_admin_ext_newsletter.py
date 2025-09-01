import pytest
from flask import url_for
from unittest.mock import patch, MagicMock
from modules.models import User, Newsletter, GlobalSettings
from modules import db
from uuid import uuid4


@pytest.fixture
def admin_user(db_session):
    """Create an admin user."""
    admin_uuid = str(uuid4())
    unique_id = str(uuid4())[:8]
    admin = User(
        user_id=admin_uuid,
        name=f'TestAdmin_{unique_id}',
        email=f'admin_{unique_id}@test.com',
        role='admin',
        is_email_verified=True
    )
    admin.set_password('testpass123')
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture
def regular_user(db_session):
    """Create a regular user."""
    user_uuid = str(uuid4())
    unique_id = str(uuid4())[:8]
    user = User(
        user_id=user_uuid,
        name=f'TestUser_{unique_id}',
        email=f'user_{unique_id}@test.com',
        role='user',
        is_email_verified=True
    )
    user.set_password('testpass123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def global_settings_smtp_enabled(db_session):
    """Create GlobalSettings with SMTP enabled and configured."""
    # Clear existing settings
    db_session.query(GlobalSettings).delete()
    db_session.commit()
    
    settings = GlobalSettings(
        settings={'enableNewsletterFeature': True},
        smtp_enabled=True,
        smtp_server='smtp.test.com',
        smtp_port=587,
        smtp_username='test@test.com',
        smtp_password='testpass',
        smtp_use_tls=True,
        smtp_default_sender='noreply@test.com'
    )
    db_session.add(settings)
    db_session.commit()
    return settings


@pytest.fixture
def global_settings_smtp_disabled(db_session):
    """Create GlobalSettings with SMTP disabled."""
    # Clear existing settings
    db_session.query(GlobalSettings).delete()
    db_session.commit()
    
    settings = GlobalSettings(
        settings={'enableNewsletterFeature': True},
        smtp_enabled=False
    )
    db_session.add(settings)
    db_session.commit()
    return settings


@pytest.fixture
def global_settings_newsletter_disabled(db_session):
    """Create GlobalSettings with newsletter feature disabled."""
    # Clear existing settings
    db_session.query(GlobalSettings).delete()
    db_session.commit()
    
    settings = GlobalSettings(
        settings={'enableNewsletterFeature': False},
        smtp_enabled=True,
        smtp_server='smtp.test.com',
        smtp_port=587,
        smtp_username='test@test.com',
        smtp_password='testpass',
        smtp_use_tls=True,
        smtp_default_sender='noreply@test.com'
    )
    db_session.add(settings)
    db_session.commit()
    return settings


@pytest.fixture
def global_settings_no_sender(db_session):
    """Create GlobalSettings with SMTP enabled but no default sender."""
    # Clear existing settings
    db_session.query(GlobalSettings).delete()
    db_session.commit()
    
    settings = GlobalSettings(
        settings={'enableNewsletterFeature': True},
        smtp_enabled=True,
        smtp_server='smtp.test.com',
        smtp_port=587,
        smtp_username='test@test.com',
        smtp_password='testpass',
        smtp_use_tls=True,
        smtp_default_sender=None
    )
    db_session.add(settings)
    db_session.commit()
    return settings


@pytest.fixture
def sample_newsletter(db_session, admin_user):
    """Create a sample newsletter record."""
    # Clear existing newsletters
    db_session.query(Newsletter).delete()
    db_session.commit()
    
    newsletter = Newsletter(
        subject='Test Newsletter',
        content='<p>This is a test newsletter content</p>',
        sender_id=admin_user.id,
        recipient_count=2,
        recipients=['test1@test.com', 'test2@test.com'],
        status='sent'
    )
    db_session.add(newsletter)
    db_session.commit()
    return newsletter


class TestNewsletterRoute:
    
    def test_newsletter_requires_login(self, client):
        """Test that newsletter page requires login."""
        response = client.get('/admin/newsletter')
        assert response.status_code == 302
        assert 'login' in response.location

    def test_newsletter_requires_admin(self, client, regular_user):
        """Test that newsletter page requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/newsletter')
        assert response.status_code == 302

    def test_newsletter_smtp_not_enabled(self, client, admin_user, global_settings_smtp_disabled):
        """Test newsletter page when SMTP is not enabled."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/newsletter', follow_redirects=True)
        assert response.status_code == 200
        assert b'SMTP is not configured or enabled' in response.data

    def test_newsletter_feature_disabled(self, client, admin_user, global_settings_newsletter_disabled):
        """Test newsletter page when newsletter feature is disabled."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/newsletter', follow_redirects=True)
        assert response.status_code == 200
        assert b'Newsletter feature is disabled' in response.data

    def test_newsletter_no_sender_configured(self, client, admin_user, global_settings_no_sender):
        """Test newsletter page when no default sender is configured."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/newsletter', follow_redirects=True)
        assert response.status_code == 200
        assert b'SMTP default sender email is not configured' in response.data

    def test_newsletter_get_request_success(self, client, admin_user, global_settings_smtp_enabled, sample_newsletter):
        """Test successful GET request to newsletter page."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/newsletter')
        assert response.status_code == 200
        assert b'Newsletter' in response.data
        assert b'Test Newsletter' in response.data

    @patch('modules.routes_admin_ext.newsletter.mail.send')
    def test_newsletter_post_success(self, mock_mail_send, client, admin_user, global_settings_smtp_enabled, db_session):
        """Test successful newsletter sending via POST."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # Clear existing newsletters
        db_session.query(Newsletter).delete()
        db_session.commit()

        data = {
            'subject': 'Test Newsletter Subject',
            'content': '<p>Test newsletter content</p>',
            'recipients': 'test1@test.com,test2@test.com',
            'send': 'Send'
        }

        response = client.post('/admin/newsletter', data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b'Newsletter sent successfully!' in response.data

        # Verify newsletter was created in database
        newsletter = db_session.query(Newsletter).filter_by(subject='Test Newsletter Subject').first()
        assert newsletter is not None
        assert newsletter.status == 'sent'
        assert newsletter.recipient_count == 2
        assert newsletter.recipients == ['test1@test.com', 'test2@test.com']
        assert newsletter.sender_id == admin_user.id

        # Verify email was attempted to be sent
        mock_mail_send.assert_called_once()

    @patch('modules.routes_admin_ext.newsletter.mail.send')
    def test_newsletter_post_email_failure(self, mock_mail_send, client, admin_user, global_settings_smtp_enabled, db_session):
        """Test newsletter sending when email fails."""
        mock_mail_send.side_effect = Exception('SMTP connection failed')

        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # Clear existing newsletters
        db_session.query(Newsletter).delete()
        db_session.commit()

        data = {
            'subject': 'Failed Newsletter',
            'content': '<p>This will fail</p>',
            'recipients': 'test@test.com',
            'send': 'Send'
        }

        response = client.post('/admin/newsletter', data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b'SMTP connection failed' in response.data

        # Verify newsletter was created but marked as failed
        newsletter = db_session.query(Newsletter).filter_by(subject='Failed Newsletter').first()
        assert newsletter is not None
        assert newsletter.status == 'failed'
        assert newsletter.error_message == 'SMTP connection failed'

    def test_newsletter_post_invalid_form(self, client, admin_user, global_settings_smtp_enabled):
        """Test POST with invalid form data."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # Missing required fields
        data = {
            'subject': '',  # Empty subject
            'content': '',  # Empty content
            'recipients': 'test@test.com',
            'send': 'Send'
        }

        response = client.get('/admin/newsletter')
        assert response.status_code == 200


class TestViewNewsletterRoute:
    
    def test_view_newsletter_requires_login(self, client):
        """Test that view newsletter page requires login."""
        response = client.get('/admin/newsletter/1')
        assert response.status_code == 302
        assert 'login' in response.location

    def test_view_newsletter_requires_admin(self, client, regular_user):
        """Test that view newsletter page requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/newsletter/1')
        assert response.status_code == 302

    def test_view_newsletter_success(self, client, admin_user, sample_newsletter):
        """Test successful viewing of a newsletter."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get(f'/admin/newsletter/{sample_newsletter.id}')
        assert response.status_code == 200
        assert b'Test Newsletter' in response.data
        assert b'This is a test newsletter content' in response.data

    def test_view_newsletter_not_found(self, client, admin_user, global_settings_smtp_enabled):
        """Test viewing a non-existent newsletter returns 404."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/newsletter/99999')
        assert response.status_code == 404


class TestNewsletterIntegration:
    """Integration tests for newsletter functionality."""
    
    @patch('modules.routes_admin_ext.newsletter.mail.send')
    def test_newsletter_workflow_complete(self, mock_mail_send, client, admin_user, global_settings_smtp_enabled, db_session):
        """Test complete newsletter workflow from creation to viewing."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # Clear existing newsletters
        db_session.query(Newsletter).delete()
        db_session.commit()

        # Step 1: Create and send newsletter
        data = {
            'subject': 'Integration Test Newsletter',
            'content': '<h1>Integration Test</h1><p>Testing complete workflow</p>',
            'recipients': 'user1@test.com,user2@test.com,user3@test.com',
            'send': 'Send'
        }

        response = client.post('/admin/newsletter', data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b'Newsletter sent successfully!' in response.data

        # Step 2: Verify newsletter exists in database
        newsletter = db_session.query(Newsletter).filter_by(subject='Integration Test Newsletter').first()
        assert newsletter is not None
        assert newsletter.status == 'sent'
        assert newsletter.recipient_count == 3

        # Step 3: View the created newsletter
        response = client.get(f'/admin/newsletter/{newsletter.id}')
        assert response.status_code == 200
        assert b'Integration Test Newsletter' in response.data
        assert b'Integration Test' in response.data
        assert b'Testing complete workflow' in response.data

        # Step 4: Verify it appears in newsletter list
        response = client.get('/admin/newsletter')
        assert response.status_code == 200
        assert b'Integration Test Newsletter' in response.data

    def test_newsletter_recipients_parsing(self, client, admin_user, global_settings_smtp_enabled, db_session):
        """Test that recipients are properly parsed from comma-separated string."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # Clear existing newsletters
        db_session.query(Newsletter).delete()
        db_session.commit()

        # Test various recipient formats
        with patch('modules.routes_admin_ext.newsletter.mail.send'):
            data = {
                'subject': 'Recipient Test',
                'content': '<p>Testing recipients</p>',
                'recipients': 'user1@test.com, user2@test.com ,user3@test.com,  user4@test.com  ',
                'send': 'Send'
            }

            response = client.post('/admin/newsletter', data=data, follow_redirects=True)
            assert response.status_code == 200

            newsletter = db_session.query(Newsletter).filter_by(subject='Recipient Test').first()
            assert newsletter is not None
            # Recipients should be stored as a list, even with spaces
            expected_recipients = ['user1@test.com', ' user2@test.com ', 'user3@test.com', '  user4@test.com  ']
            assert newsletter.recipients == expected_recipients
            assert newsletter.recipient_count == 4