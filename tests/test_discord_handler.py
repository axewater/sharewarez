import unittest
from unittest.mock import patch, MagicMock, Mock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.discord_handler import DiscordWebhookHandler
from discord_webhook import DiscordEmbed
from requests.exceptions import RequestException, HTTPError, Timeout
from tenacity import RetryError


class TestDiscordWebhookHandler(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.valid_webhook_url = "https://discord.com/api/webhooks/123456789/abcdef"
        self.bot_name = "TestBot"
        self.bot_avatar_url = "https://example.com/avatar.png"
        self.handler = DiscordWebhookHandler(
            webhook_url=self.valid_webhook_url,
            bot_name=self.bot_name,
            bot_avatar_url=self.bot_avatar_url
        )
    
    # Constructor Tests
    def test_init_with_required_params(self):
        """Test initialization with only required parameters."""
        handler = DiscordWebhookHandler("https://discord.com/api/webhooks/123/abc")
        self.assertEqual(handler.webhook_url, "https://discord.com/api/webhooks/123/abc")
        self.assertIsNone(handler.bot_name)
        self.assertIsNone(handler.bot_avatar_url)
        self.assertEqual(handler.max_retries, 3)
        self.assertEqual(handler.timeout, 10)
    
    def test_init_with_all_params(self):
        """Test initialization with all parameters."""
        self.assertEqual(self.handler.webhook_url, self.valid_webhook_url)
        self.assertEqual(self.handler.bot_name, self.bot_name)
        self.assertEqual(self.handler.bot_avatar_url, self.bot_avatar_url)
        self.assertEqual(self.handler.max_retries, 3)
        self.assertEqual(self.handler.timeout, 10)
    
    # URL Validation Tests
    def test_validate_webhook_url_valid_discord_com(self):
        """Test validation passes for valid discord.com webhook URL."""
        handler = DiscordWebhookHandler("https://discord.com/api/webhooks/123456789/abcdef")
        self.assertTrue(handler.validate_webhook_url())
    
    def test_validate_webhook_url_valid_discordapp_com(self):
        """Test validation passes for valid discordapp.com webhook URL."""
        handler = DiscordWebhookHandler("https://discordapp.com/api/webhooks/123456789/abcdef")
        self.assertTrue(handler.validate_webhook_url())
    
    def test_validate_webhook_url_invalid_scheme_http(self):
        """Test validation fails for HTTP (non-HTTPS) URL."""
        handler = DiscordWebhookHandler("http://discord.com/api/webhooks/123456789/abcdef")
        self.assertFalse(handler.validate_webhook_url())
    
    def test_validate_webhook_url_invalid_scheme_ftp(self):
        """Test validation fails for non-HTTP schemes."""
        handler = DiscordWebhookHandler("ftp://discord.com/api/webhooks/123456789/abcdef")
        self.assertFalse(handler.validate_webhook_url())
    
    def test_validate_webhook_url_invalid_domain(self):
        """Test validation fails for invalid domains (SSRF protection)."""
        invalid_domains = [
            "https://evil.com/api/webhooks/123456789/abcdef",
            "https://localhost/api/webhooks/123456789/abcdef",
            "https://127.0.0.1/api/webhooks/123456789/abcdef",
            "https://10.0.0.1/api/webhooks/123456789/abcdef",
            "https://discord.evil.com/api/webhooks/123456789/abcdef"
        ]
        for url in invalid_domains:
            handler = DiscordWebhookHandler(url)
            self.assertFalse(handler.validate_webhook_url(), f"Should reject {url}")
    
    def test_validate_webhook_url_invalid_path(self):
        """Test validation fails for invalid webhook paths."""
        invalid_paths = [
            "https://discord.com/api/v9/webhooks/123456789/abcdef",
            "https://discord.com/webhooks/123456789/abcdef", 
            "https://discord.com/api/webhook/123456789/abcdef",
            "https://discord.com/api/webhooks",
            "https://discord.com/"
        ]
        for url in invalid_paths:
            handler = DiscordWebhookHandler(url)
            self.assertFalse(handler.validate_webhook_url(), f"Should reject {url}")
    
    def test_validate_webhook_url_empty_or_none(self):
        """Test validation fails for empty or None URLs."""
        for invalid_url in [None, "", " "]:
            handler = DiscordWebhookHandler(invalid_url)
            self.assertFalse(handler.validate_webhook_url())
    
    def test_validate_webhook_url_non_string(self):
        """Test validation fails for non-string inputs."""
        for invalid_url in [123, [], {}, True]:
            handler = DiscordWebhookHandler(invalid_url)
            self.assertFalse(handler.validate_webhook_url())
    
    def test_validate_webhook_url_malformed(self):
        """Test validation fails for malformed URLs."""
        malformed_urls = [
            "not-a-url",
            "https://",
            "https:discord.com",
            "discord.com/api/webhooks/123"
        ]
        for url in malformed_urls:
            handler = DiscordWebhookHandler(url)
            self.assertFalse(handler.validate_webhook_url(), f"Should reject {url}")
    
    # Embed Creation Tests
    def test_create_embed_basic(self):
        """Test creating a basic embed with title only."""
        embed = self.handler.create_embed("Test Title")
        
        self.assertIsInstance(embed, DiscordEmbed)
        self.assertEqual(embed.title, "Test Title")
        self.assertEqual(embed.color, 242424)  # Default color converted to int
    
    def test_create_embed_with_all_params(self):
        """Test creating embed with all parameters."""
        embed = self.handler.create_embed(
            title="Test Title",
            description="Test Description", 
            url="https://example.com",
            color="ff0000"
        )
        
        self.assertEqual(embed.title, "Test Title")
        self.assertEqual(embed.description, "Test Description")
        self.assertEqual(embed.url, "https://example.com")
        self.assertEqual(embed.color, 16711680)  # ff0000 converted to int
    
    def test_create_embed_with_fields(self):
        """Test creating embed with custom fields."""
        fields = {
            "Field 1": "Value 1",
            "Field 2": 123,
            "Field 3": True
        }
        
        with patch.object(DiscordEmbed, 'add_embed_field') as mock_add_field:
            embed = self.handler.create_embed("Title", fields=fields)
            
            self.assertEqual(mock_add_field.call_count, 3)
            mock_add_field.assert_any_call(name="Field 1", value="Value 1")
            mock_add_field.assert_any_call(name="Field 2", value="123")
            mock_add_field.assert_any_call(name="Field 3", value="True")
    
    def test_create_embed_with_bot_author(self):
        """Test embed includes bot author when configured."""
        with patch.object(DiscordEmbed, 'set_author') as mock_set_author:
            embed = self.handler.create_embed("Title", url="https://example.com")
            
            mock_set_author.assert_called_once_with(
                name=self.bot_name,
                url="https://example.com",
                icon_url=self.bot_avatar_url
            )
    
    def test_create_embed_without_bot_author(self):
        """Test embed without bot author when not configured."""
        handler = DiscordWebhookHandler(self.valid_webhook_url)  # No bot info
        
        with patch.object(DiscordEmbed, 'set_author') as mock_set_author:
            embed = handler.create_embed("Title")
            mock_set_author.assert_not_called()
    
    def test_create_embed_sets_timestamp(self):
        """Test embed always sets timestamp."""
        with patch.object(DiscordEmbed, 'set_timestamp') as mock_set_timestamp:
            embed = self.handler.create_embed("Title")
            mock_set_timestamp.assert_called_once()
    
    def test_create_embed_error_handling(self):
        """Test error handling in embed creation."""
        with patch('modules.discord_handler.DiscordEmbed') as mock_embed:
            mock_embed.side_effect = Exception("Embed creation failed")
            
            with self.assertRaises(Exception):
                self.handler.create_embed("Title")
    
    # Webhook Sending Tests
    @patch('modules.discord_handler.DiscordWebhook')
    def test_send_webhook_success(self, mock_webhook_class):
        """Test successful webhook sending."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        
        mock_webhook = Mock()
        mock_webhook.execute.return_value = mock_response
        mock_webhook_class.return_value = mock_webhook
        
        # Create test embed
        embed = DiscordEmbed(title="Test")
        
        # Test successful send
        result = self.handler.send_webhook(embed)
        
        self.assertTrue(result)
        mock_webhook_class.assert_called_once_with(
            url=self.valid_webhook_url,
            rate_limit_retry=True,
            timeout=10
        )
        mock_webhook.add_embed.assert_called_once_with(embed)
        mock_webhook.execute.assert_called_once()
    
    def test_send_webhook_invalid_url(self):
        """Test webhook sending fails with invalid URL."""
        handler = DiscordWebhookHandler("https://evil.com/webhook")
        embed = DiscordEmbed(title="Test")
        
        # Test that invalid URL raises ValueError (with retry it becomes RetryError)
        with self.assertRaises((ValueError, RetryError)):
            result = handler.send_webhook(embed)
    
    @patch('modules.discord_handler.DiscordWebhook')
    def test_send_webhook_rate_limited(self, mock_webhook_class):
        """Test webhook sending handles rate limiting."""
        mock_response = Mock()
        mock_response.status_code = 429
        
        mock_webhook = Mock()
        mock_webhook.execute.return_value = mock_response
        mock_webhook_class.return_value = mock_webhook
        
        embed = DiscordEmbed(title="Test")
        
        # Test with actual retry behavior
        embed = DiscordEmbed(title="Test")
        
        with self.assertRaises(RetryError):
            handler = DiscordWebhookHandler(self.valid_webhook_url)  
            handler.send_webhook(embed)
    
    @patch('modules.discord_handler.DiscordWebhook')
    def test_send_webhook_http_error(self, mock_webhook_class):
        """Test webhook sending handles HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 404
        
        mock_webhook = Mock()
        mock_webhook.execute.return_value = mock_response
        mock_webhook_class.return_value = mock_webhook
        
        embed = DiscordEmbed(title="Test")
        
        with self.assertRaises(RetryError):
            handler = DiscordWebhookHandler(self.valid_webhook_url)
            handler.send_webhook(embed)
    
    @patch('modules.discord_handler.DiscordWebhook')
    def test_send_webhook_timeout(self, mock_webhook_class):
        """Test webhook sending handles timeout."""
        mock_webhook = Mock()
        mock_webhook.execute.side_effect = Timeout("Request timed out")
        mock_webhook_class.return_value = mock_webhook
        
        embed = DiscordEmbed(title="Test")
        
        with self.assertRaises(RetryError):
            handler = DiscordWebhookHandler(self.valid_webhook_url)
            handler.send_webhook(embed)
    
    @patch('modules.discord_handler.DiscordWebhook')
    def test_send_webhook_request_exception(self, mock_webhook_class):
        """Test webhook sending handles request exceptions."""
        mock_webhook = Mock()
        mock_webhook.execute.side_effect = RequestException("Network error")
        mock_webhook_class.return_value = mock_webhook
        
        embed = DiscordEmbed(title="Test")
        
        with self.assertRaises(RetryError):
            handler = DiscordWebhookHandler(self.valid_webhook_url)
            handler.send_webhook(embed)
    
    @patch('modules.discord_handler.DiscordWebhook')
    def test_send_webhook_status_204(self, mock_webhook_class):
        """Test webhook sending accepts 204 status code."""
        mock_response = Mock()
        mock_response.status_code = 204
        
        mock_webhook = Mock()
        mock_webhook.execute.return_value = mock_response
        mock_webhook_class.return_value = mock_webhook
        
        embed = DiscordEmbed(title="Test")
        result = self.handler.send_webhook(embed)
        
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()