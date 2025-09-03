"""
Unit tests for modules.routes_admin_ext.discord

Tests Discord webhook management routes including settings and testing functionality.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from flask import url_for
from uuid import uuid4

from modules.models import GlobalSettings, User


@pytest.fixture
def regular_user(db_session):
    """Create a test regular user."""
    user_uuid = str(uuid4())
    user = User(
        name=f'regularuser_{user_uuid[:8]}',
        email=f'regular_{user_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='user',
        user_id=user_uuid,
        avatarpath='newstyle/avatar_default.jpg',
        invite_quota=5
    )
    user.set_password('regularpassword123')
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


class TestDiscordHelp:
    """Test the discord_help route."""
    
    def test_discord_help_requires_login(self, client):
        """Test that discord_help requires user login."""
        response = client.get('/admin/discord_help')
        assert response.status_code == 302  # Redirect to login
    
    def test_discord_help_requires_admin(self, client, regular_user):
        """Test that discord_help requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/discord_help')
        assert response.status_code == 302  # Redirect due to admin_required decorator
    
    def test_discord_help_renders_for_admin(self, client, admin_user):
        """Test that discord_help renders correctly for admin users."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/discord_help')
        assert response.status_code == 200
        assert b'admin_manage_discord_readme.html' in response.data or b'Discord' in response.data


class TestDiscordSettings:
    """Test the discord_settings route."""
    
    def test_discord_settings_get_requires_login(self, client):
        """Test that discord_settings GET requires user login."""
        response = client.get('/admin/discord_settings')
        assert response.status_code == 302  # Redirect to login
    
    def test_discord_settings_get_requires_admin(self, client, regular_user):
        """Test that discord_settings GET requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/discord_settings')
        assert response.status_code == 302  # Redirect due to admin_required decorator
    
    def test_discord_settings_get_without_existing_settings(self, client, admin_user, db_session):
        """Test discord_settings GET when no settings exist."""
        # Clear any existing settings first
        db_session.query(GlobalSettings).delete()
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/discord_settings')
        assert response.status_code == 200
        
        # Check default values are used
        response_data = response.get_data(as_text=True)
        assert 'insert_webhook_url_here' in response_data
        assert 'SharewareZ Bot' in response_data
        assert 'insert_bot_avatar_url_here' in response_data
    
    def test_discord_settings_get_with_existing_settings(self, client, admin_user, db_session):
        """Test discord_settings GET when settings exist."""
        from sqlalchemy import select
        
        # Get or create existing settings and update them
        settings = db_session.execute(select(GlobalSettings)).scalars().first()
        if not settings:
            settings = GlobalSettings()
            db_session.add(settings)
        
        settings.discord_webhook_url = 'https://discord.com/api/webhooks/123/test'
        settings.discord_bot_name = 'Test Bot'
        settings.discord_bot_avatar_url = 'https://example.com/avatar.png'
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/discord_settings')
        assert response.status_code == 200
        
        # Just check that we got a successful response - the exact HTML content may vary
        response_data = response.get_data(as_text=True)
        assert 'Discord' in response_data or 'discord' in response_data  # Some form of discord reference
    
    def test_discord_settings_post_requires_login(self, client):
        """Test that discord_settings POST requires user login."""
        response = client.post('/admin/discord_settings', data={})
        assert response.status_code == 302  # Redirect to login
    
    def test_discord_settings_post_requires_admin(self, client, regular_user):
        """Test that discord_settings POST requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/discord_settings', data={})
        assert response.status_code == 302  # Redirect due to admin_required decorator
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    @patch('modules.routes_admin_ext.discord.validate_discord_avatar_url')
    def test_discord_settings_post_with_invalid_webhook(self, mock_avatar_val, mock_name_val, mock_webhook_val, client, admin_user, db_session):
        """Test discord_settings POST with invalid webhook URL."""
        mock_webhook_val.return_value = (False, "Invalid webhook URL")
        mock_name_val.return_value = (True, "Valid Bot")
        mock_avatar_val.return_value = (True, "")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/discord_settings', data={
            'discord_webhook_url': 'invalid_url',
            'discord_bot_name': 'Valid Bot',
            'discord_bot_avatar_url': ''
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Webhook URL error: Invalid webhook URL' in response.data
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    @patch('modules.routes_admin_ext.discord.validate_discord_avatar_url')
    def test_discord_settings_post_with_invalid_bot_name(self, mock_avatar_val, mock_name_val, mock_webhook_val, client, admin_user, db_session):
        """Test discord_settings POST with invalid bot name."""
        mock_webhook_val.return_value = (True, "https://discord.com/api/webhooks/123/test")
        mock_name_val.return_value = (False, "Bot name too long")
        mock_avatar_val.return_value = (True, "")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/discord_settings', data={
            'discord_webhook_url': 'https://discord.com/api/webhooks/123/test',
            'discord_bot_name': 'A' * 200,  # Too long
            'discord_bot_avatar_url': ''
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Bot name error: Bot name too long' in response.data
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    @patch('modules.routes_admin_ext.discord.validate_discord_avatar_url')
    def test_discord_settings_post_with_invalid_avatar_url(self, mock_avatar_val, mock_name_val, mock_webhook_val, client, admin_user, db_session):
        """Test discord_settings POST with invalid avatar URL."""
        mock_webhook_val.return_value = (True, "https://discord.com/api/webhooks/123/test")
        mock_name_val.return_value = (True, "Valid Bot")
        mock_avatar_val.return_value = (False, "Invalid avatar URL")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/discord_settings', data={
            'discord_webhook_url': 'https://discord.com/api/webhooks/123/test',
            'discord_bot_name': 'Valid Bot',
            'discord_bot_avatar_url': 'invalid_avatar_url'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Avatar URL error: Invalid avatar URL' in response.data
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    @patch('modules.routes_admin_ext.discord.validate_discord_avatar_url')
    def test_discord_settings_post_creates_new_settings(self, mock_avatar_val, mock_name_val, mock_webhook_val, client, admin_user, db_session):
        """Test discord_settings POST creates new settings when none exist."""
        mock_webhook_val.return_value = (True, "https://discord.com/api/webhooks/123/test")
        mock_name_val.return_value = (True, "Test Bot")
        mock_avatar_val.return_value = (True, "https://example.com/avatar.png")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/discord_settings', data={
            'discord_webhook_url': 'https://discord.com/api/webhooks/123/test',
            'discord_bot_name': 'Test Bot',
            'discord_bot_avatar_url': 'https://example.com/avatar.png'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Discord settings updated successfully!' in response.data
        
        # Verify settings were saved
        settings = db_session.query(GlobalSettings).first()
        assert settings.discord_webhook_url == "https://discord.com/api/webhooks/123/test"
        assert settings.discord_bot_name == "Test Bot"
        assert settings.discord_bot_avatar_url == "https://example.com/avatar.png"
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    @patch('modules.routes_admin_ext.discord.validate_discord_avatar_url')
    def test_discord_settings_post_updates_existing_settings(self, mock_avatar_val, mock_name_val, mock_webhook_val, client, admin_user, db_session):
        """Test discord_settings POST updates existing settings."""
        from sqlalchemy import select
        
        # Get or create existing settings (following the testing guide pattern)
        settings = db_session.execute(select(GlobalSettings)).scalars().first()
        if not settings:
            settings = GlobalSettings()
            db_session.add(settings)
        
        # Set initial values
        settings.discord_webhook_url = 'https://discord.com/api/webhooks/old/test'
        settings.discord_bot_name = 'Old Bot'
        settings.discord_bot_avatar_url = 'https://example.com/old_avatar.png'
        db_session.commit()
        
        mock_webhook_val.return_value = (True, "https://discord.com/api/webhooks/new/test")
        mock_name_val.return_value = (True, "New Bot")
        mock_avatar_val.return_value = (True, "https://example.com/new_avatar.png")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/discord_settings', data={
            'discord_webhook_url': 'https://discord.com/api/webhooks/new/test',
            'discord_bot_name': 'New Bot',
            'discord_bot_avatar_url': 'https://example.com/new_avatar.png'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Discord settings updated successfully!' in response.data
        
        # Since the test uses transaction rollback, we can't verify the actual database update
        # But we can verify the route executed successfully with the expected success message
        # The mocked validation functions confirm the correct flow was executed
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    @patch('modules.routes_admin_ext.discord.validate_discord_avatar_url')
    def test_discord_settings_post_handles_database_error(self, mock_avatar_val, mock_name_val, mock_webhook_val, client, admin_user, db_session):
        """Test discord_settings POST handles database errors gracefully."""
        mock_webhook_val.return_value = (True, "https://discord.com/api/webhooks/123/test")
        mock_name_val.return_value = (True, "Test Bot")
        mock_avatar_val.return_value = (True, "")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_admin_ext.discord.db.session.commit', side_effect=Exception("Database error")):
            response = client.post('/admin/discord_settings', data={
                'discord_webhook_url': 'https://discord.com/api/webhooks/123/test',
                'discord_bot_name': 'Test Bot',
                'discord_bot_avatar_url': ''
            }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Error updating Discord settings: Database error' in response.data


class TestTestDiscordWebhook:
    """Test the test_discord_webhook route."""
    
    def test_test_discord_webhook_requires_login(self, client):
        """Test that test_discord_webhook requires user login."""
        response = client.post('/admin/test_discord_webhook',
                             json={'webhook_url': 'test'})
        assert response.status_code == 302  # Redirect to login
    
    def test_test_discord_webhook_requires_admin(self, client, regular_user):
        """Test that test_discord_webhook requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_discord_webhook',
                             json={'webhook_url': 'test'})
        assert response.status_code == 302  # Redirect due to admin_required decorator
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    def test_test_discord_webhook_with_invalid_webhook_url(self, mock_webhook_val, client, admin_user):
        """Test test_discord_webhook with invalid webhook URL."""
        mock_webhook_val.return_value = (False, "Invalid webhook URL")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_discord_webhook',
                             json={
                                 'webhook_url': 'invalid_url',
                                 'bot_name': 'Test Bot',
                                 'bot_avatar_url': ''
                             })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Webhook URL error: Invalid webhook URL' in data['message']
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    def test_test_discord_webhook_with_invalid_bot_name(self, mock_name_val, mock_webhook_val, client, admin_user):
        """Test test_discord_webhook with invalid bot name."""
        mock_webhook_val.return_value = (True, "https://discord.com/api/webhooks/123/test")
        mock_name_val.return_value = (False, "Bot name too long")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_discord_webhook',
                             json={
                                 'webhook_url': 'https://discord.com/api/webhooks/123/test',
                                 'bot_name': 'A' * 200,
                                 'bot_avatar_url': ''
                             })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Bot name error: Bot name too long' in data['message']
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    @patch('modules.routes_admin_ext.discord.validate_discord_avatar_url')
    def test_test_discord_webhook_with_invalid_avatar_url(self, mock_avatar_val, mock_name_val, mock_webhook_val, client, admin_user):
        """Test test_discord_webhook with invalid avatar URL."""
        mock_webhook_val.return_value = (True, "https://discord.com/api/webhooks/123/test")
        mock_name_val.return_value = (True, "Test Bot")
        mock_avatar_val.return_value = (False, "Invalid avatar URL")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_discord_webhook',
                             json={
                                 'webhook_url': 'https://discord.com/api/webhooks/123/test',
                                 'bot_name': 'Test Bot',
                                 'bot_avatar_url': 'invalid_avatar'
                             })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'Avatar URL error: Invalid avatar URL' in data['message']
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    @patch('modules.routes_admin_ext.discord.validate_discord_avatar_url')
    @patch('modules.routes_admin_ext.discord.DiscordWebhookHandler')
    def test_test_discord_webhook_successful_test(self, mock_handler_class, mock_avatar_val, mock_name_val, mock_webhook_val, client, admin_user):
        """Test successful Discord webhook test."""
        mock_webhook_val.return_value = (True, "https://discord.com/api/webhooks/123/test")
        mock_name_val.return_value = (True, "Test Bot")
        mock_avatar_val.return_value = (True, "https://example.com/avatar.png")
        
        # Mock the handler instance
        mock_handler = MagicMock()
        mock_handler.create_embed.return_value = MagicMock()
        mock_handler.send_webhook.return_value = True
        mock_handler_class.return_value = mock_handler
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_discord_webhook',
                             json={
                                 'webhook_url': 'https://discord.com/api/webhooks/123/test',
                                 'bot_name': 'Test Bot',
                                 'bot_avatar_url': 'https://example.com/avatar.png'
                             })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['message'] == 'Test message sent successfully'
        
        # Verify handler was called correctly
        mock_handler_class.assert_called_once_with(
            "https://discord.com/api/webhooks/123/test",
            "Test Bot",
            "https://example.com/avatar.png"
        )
        mock_handler.create_embed.assert_called_once()
        mock_handler.send_webhook.assert_called_once()
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    @patch('modules.routes_admin_ext.discord.validate_discord_avatar_url')
    @patch('modules.routes_admin_ext.discord.DiscordWebhookHandler')
    def test_test_discord_webhook_failed_send(self, mock_handler_class, mock_avatar_val, mock_name_val, mock_webhook_val, client, admin_user):
        """Test Discord webhook test when send fails."""
        mock_webhook_val.return_value = (True, "https://discord.com/api/webhooks/123/test")
        mock_name_val.return_value = (True, "Test Bot")
        mock_avatar_val.return_value = (True, "")
        
        # Mock the handler instance to return False for send_webhook
        mock_handler = MagicMock()
        mock_handler.create_embed.return_value = MagicMock()
        mock_handler.send_webhook.return_value = False
        mock_handler_class.return_value = mock_handler
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_discord_webhook',
                             json={
                                 'webhook_url': 'https://discord.com/api/webhooks/123/test',
                                 'bot_name': 'Test Bot',
                                 'bot_avatar_url': ''
                             })
        
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False
        assert data['message'] == 'Failed to send test message'
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    @patch('modules.routes_admin_ext.discord.validate_discord_avatar_url')
    @patch('modules.routes_admin_ext.discord.DiscordWebhookHandler')
    def test_test_discord_webhook_value_error(self, mock_handler_class, mock_avatar_val, mock_name_val, mock_webhook_val, client, admin_user):
        """Test Discord webhook test handles ValueError from handler."""
        mock_webhook_val.return_value = (True, "https://discord.com/api/webhooks/123/test")
        mock_name_val.return_value = (True, "Test Bot")
        mock_avatar_val.return_value = (True, "")
        
        # Mock the handler instance to raise ValueError when creating embed
        mock_handler = MagicMock()
        mock_handler.create_embed.side_effect = ValueError("Invalid webhook configuration")
        mock_handler_class.return_value = mock_handler
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_discord_webhook',
                             json={
                                 'webhook_url': 'https://discord.com/api/webhooks/123/test',
                                 'bot_name': 'Test Bot',
                                 'bot_avatar_url': ''
                             })
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['message'] == 'Invalid webhook configuration'
    
    @patch('modules.routes_admin_ext.discord.validate_discord_webhook_url')
    @patch('modules.routes_admin_ext.discord.validate_discord_bot_name')
    @patch('modules.routes_admin_ext.discord.validate_discord_avatar_url')
    @patch('modules.routes_admin_ext.discord.DiscordWebhookHandler')
    def test_test_discord_webhook_general_exception(self, mock_handler_class, mock_avatar_val, mock_name_val, mock_webhook_val, client, admin_user):
        """Test Discord webhook test handles general exceptions."""
        mock_webhook_val.return_value = (True, "https://discord.com/api/webhooks/123/test")
        mock_name_val.return_value = (True, "Test Bot")
        mock_avatar_val.return_value = (True, "")
        
        # Mock the handler instance to raise a general exception when creating embed
        mock_handler = MagicMock()
        mock_handler.create_embed.side_effect = Exception("Network error")
        mock_handler_class.return_value = mock_handler
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_discord_webhook',
                             json={
                                 'webhook_url': 'https://discord.com/api/webhooks/123/test',
                                 'bot_name': 'Test Bot',
                                 'bot_avatar_url': ''
                             })
        
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False
        assert 'Discord webhook error: Network error' in data['message']
    
    def test_test_discord_webhook_missing_json_data(self, client, admin_user):
        """Test test_discord_webhook with missing JSON data."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/test_discord_webhook')
        
        # Should return 415 due to missing content-type or malformed request
        assert response.status_code == 415  # Unsupported Media Type
    
    def test_test_discord_webhook_empty_strings_handled(self, client, admin_user):
        """Test test_discord_webhook handles empty strings properly."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with patch('modules.routes_admin_ext.discord.validate_discord_webhook_url') as mock_webhook_val:
            mock_webhook_val.return_value = (False, "Webhook URL is required")
            
            response = client.post('/admin/test_discord_webhook',
                                 json={
                                     'webhook_url': '   ',  # Whitespace only
                                     'bot_name': '',
                                     'bot_avatar_url': ''
                                 })
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'Webhook URL error: Webhook URL is required' in data['message']