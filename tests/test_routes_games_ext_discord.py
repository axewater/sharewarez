import pytest
import json
from uuid import uuid4
from unittest.mock import patch, MagicMock
from modules import create_app, db
from modules.models import User, GlobalSettings, Game, Library
from sqlalchemy import select


class TestDiscordNotificationRoute:
    """Test class for Discord notification route functionality."""
    
    @pytest.fixture(autouse=True)
    def cleanup_global_settings(self, app):
        """Clear GlobalSettings before and after each test for isolation."""
        with app.app_context():
            # Clear before test
            from sqlalchemy import delete
            db.session.execute(delete(GlobalSettings))
            db.session.commit()
        
        yield
        
        with app.app_context():
            # Clear after test
            db.session.execute(delete(GlobalSettings))
            db.session.commit()
    
    @pytest.fixture
    def app(self):
        """Create a test Flask app."""
        app = create_app()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return app.test_client()
    
    @pytest.fixture
    def admin_user(self, app):
        """Create an admin user for testing."""
        with app.app_context():
            admin_uuid = str(uuid4())
            admin = User(
                name=f"admin_{admin_uuid[:8]}", 
                email=f"admin_{admin_uuid[:8]}@test.com", 
                role="admin",
                user_id=admin_uuid
            )
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            # Return the ID instead of the object to avoid session issues
            return admin.id
    
    @pytest.fixture
    def regular_user(self, app):
        """Create a regular user for testing."""
        with app.app_context():
            user_uuid = str(uuid4())
            user = User(
                name=f"user_{user_uuid[:8]}", 
                email=f"user_{user_uuid[:8]}@test.com", 
                role="user",
                user_id=user_uuid
            )
            user.set_password("user123")
            db.session.add(user)
            db.session.commit()
            return user.id
    
    @pytest.fixture
    def test_game(self, app):
        """Create a test game."""
        with app.app_context():
            # Create a library first - need to import LibraryPlatform
            from modules.models import LibraryPlatform
            library = Library(
                name="Test Library",
                platform=LibraryPlatform.PCWIN
            )
            db.session.add(library)
            db.session.flush()  # Get the library UUID
            
            # Create a game
            game = Game(
                name="Test Game",
                library_uuid=library.uuid,
                full_disk_path="/test/game/path"
            )
            db.session.add(game)
            db.session.commit()
            # Return the UUID instead of the object to avoid session issues
            return game.uuid
    
    def test_trigger_discord_notification_requires_login(self, client):
        """Test that the route requires user login."""
        response = client.post('/trigger_discord_notification/test-uuid')
        assert response.status_code == 302  # Redirect to login
    
    def test_trigger_discord_notification_requires_admin(self, client, regular_user, app):
        """Test that the route requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user)
            sess['_fresh'] = True
            
        response = client.post('/trigger_discord_notification/test-uuid')
        data = json.loads(response.data)
        
        assert response.status_code == 403
        assert data['success'] is False
        assert 'Admin access required' in data['message']
    
    def test_trigger_discord_notification_no_webhook_url(self, client, admin_user, app):
        """Test notification when Discord webhook URL is empty."""
        with app.app_context():
            # Create settings with empty webhook URL
            settings = GlobalSettings(
                discord_webhook_url='',  # Empty string
                discord_notify_manual_trigger=False
            )
            db.session.add(settings)
            db.session.commit()
            
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user)
            sess['_fresh'] = True
            
        response = client.post('/trigger_discord_notification/test-uuid')
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert data['success'] is False
        assert 'not configured' in data['message']
    
    def test_trigger_discord_notification_manual_trigger_disabled(self, client, admin_user, app):
        """Test notification when manual triggers are disabled."""
        with app.app_context():
            # Create settings with Discord configured but manual trigger disabled
            settings = GlobalSettings(
                discord_webhook_url='https://discord.com/api/webhooks/123/test',
                discord_notify_manual_trigger=False
            )
            db.session.add(settings)
            db.session.commit()
            db.session.flush()  # Ensure settings are written to database
            
            # Setup session INSIDE the context
            with client.session_transaction() as sess:
                sess['_user_id'] = str(admin_user)
                sess['_fresh'] = True
            
            # Make request INSIDE the context
            response = client.post('/trigger_discord_notification/test-uuid')
            data = json.loads(response.data)
            
            assert response.status_code == 403
            assert data['success'] is False
            assert 'not enabled' in data['message']
    
    def test_trigger_discord_notification_game_not_found(self, client, admin_user, app):
        """Test notification when game doesn't exist."""
        with app.app_context():
            # Create settings with Discord configured and manual trigger enabled
            settings = GlobalSettings(
                discord_webhook_url='https://discord.com/api/webhooks/123/test',
                discord_notify_manual_trigger=True
            )
            db.session.add(settings)
            db.session.commit()
            db.session.flush()  # Ensure settings are written to database
            
            # Setup session INSIDE the context
            with client.session_transaction() as sess:
                sess['_user_id'] = str(admin_user)
                sess['_fresh'] = True
            
            # Make request INSIDE the context
            response = client.post('/trigger_discord_notification/nonexistent-uuid')
            data = json.loads(response.data)
            
            assert response.status_code == 404
            assert data['success'] is False
            assert 'not found' in data['message']
    
    @patch('modules.routes_games_ext.discord.discord_webhook')
    def test_trigger_discord_notification_success(self, mock_discord_webhook, client, admin_user, test_game, app):
        """Test successful Discord notification."""
        with app.app_context():
            # Create settings with Discord configured and manual trigger enabled
            settings = GlobalSettings(
                discord_webhook_url='https://discord.com/api/webhooks/123/test',
                discord_notify_manual_trigger=True
            )
            db.session.add(settings)
            db.session.commit()
            
            # Setup session INSIDE the context
            with client.session_transaction() as sess:
                sess['_user_id'] = str(admin_user)
                sess['_fresh'] = True
            
            # Make request INSIDE the context
            response = client.post(f'/trigger_discord_notification/{test_game}')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        assert 'notification sent' in data['message'].lower()
        mock_discord_webhook.assert_called_once_with(test_game, manual_trigger=True)
    
    @patch('modules.routes_games_ext.discord.discord_webhook')
    def test_trigger_discord_notification_webhook_error(self, mock_discord_webhook, client, admin_user, test_game, app):
        """Test Discord notification when webhook fails."""
        with app.app_context():
            # Create settings with Discord configured and manual trigger enabled
            settings = GlobalSettings(
                discord_webhook_url='https://discord.com/api/webhooks/123/test',
                discord_notify_manual_trigger=True
            )
            db.session.add(settings)
            db.session.commit()
            
            # Make the discord_webhook function raise an exception
            mock_discord_webhook.side_effect = Exception("Webhook failed")
            
            # Setup session INSIDE the context
            with client.session_transaction() as sess:
                sess['_user_id'] = str(admin_user)
                sess['_fresh'] = True
            
            # Make request INSIDE the context
            response = client.post(f'/trigger_discord_notification/{test_game}')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert data['success'] is False
        assert 'Failed to send' in data['message']