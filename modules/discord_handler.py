import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from discord_webhook import DiscordWebhook, DiscordEmbed
from requests.exceptions import RequestException, HTTPError, Timeout
from tenacity import retry, stop_after_attempt, wait_exponential

class DiscordWebhookHandler:
    def __init__(self, webhook_url: str, bot_name: str = None, bot_avatar_url: str = None):
        self.webhook_url = webhook_url
        self.bot_name = bot_name
        self.bot_avatar_url = bot_avatar_url
        self.max_retries = 3
        self.timeout = 10

    def validate_webhook_url(self) -> bool:
        """Validate the webhook URL format with proper domain validation to prevent SSRF attacks."""
        if not self.webhook_url or not isinstance(self.webhook_url, str):
            return False
        
        try:
            parsed_url = urlparse(self.webhook_url)
            
            # Ensure HTTPS is used
            if parsed_url.scheme != 'https':
                return False
            
            # Validate that the hostname is exactly one of Discord's domains
            allowed_domains = {'discord.com', 'discordapp.com'}
            if parsed_url.hostname not in allowed_domains:
                return False
            
            # Validate that the path starts with the webhook API endpoint
            if not parsed_url.path.startswith('/api/webhooks/'):
                return False
            
            return True
            
        except (ValueError, AttributeError):
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def send_webhook(self, embed: DiscordEmbed) -> bool:
        """Send webhook with retry mechanism and error handling."""
        try:
            if not self.validate_webhook_url():
                raise ValueError("Invalid Discord webhook URL")

            webhook = DiscordWebhook(
                url=self.webhook_url,
                rate_limit_retry=True,
                timeout=self.timeout
            )
            webhook.add_embed(embed)
            response = webhook.execute()
            
            if response and response.status_code in [200, 204]:
                print("Discord webhook sent successfully")
                return True
            elif response and response.status_code == 429:
                raise Exception("Discord webhook rate limited")
            else:
                raise Exception(f"Discord webhook failed with status code: {response.status_code}")

        except Timeout:
            print("Discord webhook request timed out")
            raise
        except HTTPError as e:
            print(f"HTTP error occurred: {str(e)}")
            raise
        except RequestException as e:
            print(f"Request error occurred: {str(e)}")
            raise
        except Exception as e:
            print(f"Unexpected error occurred: {str(e)}")
            raise

    def create_embed(self, 
                    title: str, 
                    description: Optional[str] = None, 
                    url: Optional[str] = None, 
                    color: str = "03b2f8",
                    fields: Optional[Dict[str, Any]] = None) -> DiscordEmbed:
        """Create a Discord embed with error handling."""
        try:
            embed = DiscordEmbed(
                title=title,
                description=description,
                url=url,
                color=color
            )

            if self.bot_name and self.bot_avatar_url:
                embed.set_author(
                    name=self.bot_name,
                    url=url,
                    icon_url=self.bot_avatar_url
                )

            if fields:
                for name, value in fields.items():
                    embed.add_embed_field(name=name, value=str(value))

            embed.set_timestamp()
            return embed

        except Exception as e:
            print(f"Error creating Discord embed: {str(e)}")
            raise
