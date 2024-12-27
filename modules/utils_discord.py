from discord_webhook import DiscordWebhook, DiscordEmbed
from modules.models import Game, Library, GlobalSettings
from modules.utils_igdb_api import get_cover_url
from modules.utils_functions import format_size
import os, time
from datetime import datetime

def discord_webhook(game_uuid):
    """Send Discord notification for new games."""
    settings = GlobalSettings.query.first()
    if not settings or not settings.discord_webhook_url:
        print("Discord webhook URL not configured")
        return
        
    if not settings.discord_notify_new_games:
        print("Discord notifications for new games are disabled")
        return

    game = discord_game_by_uuid(game_uuid)
    game_size = format_size(game.size)
    game_library = get_library_by_uuid(game.library_uuid)
    
    discord_webhook = settings.discord_webhook_url
    discord_bot_name = settings.discord_bot_name
    discord_bot_avatar_url = settings.discord_bot_avatar_url
    
    site_url = settings.site_url
    cover_url = get_cover_url(game.igdb_id)

    webhook = DiscordWebhook(url=f"{discord_webhook}", rate_limit_retry=True)
    embed = DiscordEmbed(
        title=f"{game.name}", 
        description=f"{game.summary}", 
        url=f"{site_url}/game_details/{game.uuid}", 
        color="03b2f8"
    )
    
    embed.set_author(
        name=f"{discord_bot_name}", 
        url=f"{site_url}", 
        icon_url=f"{discord_bot_avatar_url}"
    )
    embed.set_image(url=f"{cover_url}")
    embed.set_footer(text="This game is now available for download")
    embed.set_timestamp()
    embed.add_embed_field(name="Library", value=f"{game_library.name}")
    embed.add_embed_field(name="Size", value=f"{game_size}")
    
    webhook.add_embed(embed)
    webhook.execute()

def discord_update(path, event, folder_name, game_path, file_name, file_size, game, game_library):
    """Send Discord notification for game updates and extras."""
    settings = GlobalSettings.query.first()
    update_folder = settings.update_folder_name if settings else 'updates'
    extras_folder = settings.extras_folder_name if settings else 'extras'
    
    if not settings or not settings.discord_webhook_url:
        print("Discord webhook URL not configured")
        return

    discord_webhook = settings.discord_webhook_url
    discord_bot_name = settings.discord_bot_name
    discord_bot_avatar_url = settings.discord_bot_avatar_url
    site_url = settings.site_url
    cover_url = get_cover_url(game.igdb_id)

    webhook = DiscordWebhook(url=f"{discord_webhook}", rate_limit_retry=True)
    
    if event == "created_update" and settings.discord_notify_game_updates:
        embed = create_update_embed(game, site_url, cover_url, game_library, file_name, file_size)
    elif event == "created_extra" and settings.discord_notify_game_extras:
        embed = create_extra_embed(game, site_url, cover_url, game_library, file_name, file_size)
    elif event == "modified" and settings.discord_notify_game_updates:
        embed = create_modified_embed(game, site_url, cover_url, game_library, file_name, file_size)
    else:
        return

    webhook.add_embed(embed)
    webhook.execute()

def create_update_embed(game, site_url, cover_url, game_library, file_name, file_size):
    embed = DiscordEmbed(
        title=f"Update File Available for {game.name}",
        url=f"{site_url}/game_details/{game.uuid}",
        color="21f704"
    )
    set_common_embed_properties(embed, site_url, cover_url)
    embed.set_footer(text="This game has an update available for download")
    add_common_embed_fields(embed, game_library, file_name, file_size)
    return embed

def create_extra_embed(game, site_url, cover_url, game_library, file_name, file_size):
    embed = DiscordEmbed(
        title=f"Extra File Available for {game.name}",
        url=f"{site_url}/game_details/{game.uuid}",
        color="f304f7"
    )
    set_common_embed_properties(embed, site_url, cover_url)
    embed.set_footer(text="This game has an extra file available for download")
    add_common_embed_fields(embed, game_library, file_name, file_size)
    return embed

def create_modified_embed(game, site_url, cover_url, game_library, file_name, file_size):
    embed = DiscordEmbed(
        title=f"Main Game Update Available for {game.name}",
        url=f"{site_url}/game_details/{game.uuid}",
        color="f71604"
    )
    set_common_embed_properties(embed, site_url, cover_url)
    embed.set_footer(text="The main file for this game has been updated and is available for download")
    add_common_embed_fields(embed, game_library, file_name, file_size)
    return embed

def set_common_embed_properties(embed, site_url, cover_url):
    settings = GlobalSettings.query.first()
    embed.set_author(
        name=settings.discord_bot_name,
        url=site_url,
        icon_url=settings.discord_bot_avatar_url
    )
    embed.set_image(url=cover_url)
    embed.set_timestamp()

def add_common_embed_fields(embed, game_library, file_name, file_size):
    embed.add_embed_field(name="Library", value=f"{game_library.name}")
    embed.add_embed_field(name="File", value=f"{file_name}")
    embed.add_embed_field(name="Size", value=f"{file_size}")

def discord_game_by_uuid(game_uuid):
    """Get game by UUID."""
    game = Game.query.filter_by(uuid=game_uuid).first()
    if game:
        print(f"Game found: {game.name} (UUID: {game.uuid})")
        return game
    print(f"Game not found for UUID: {game_uuid}")
    return None

def get_library_by_uuid(uuid):
    """Get library by UUID."""
    library = Library.query.filter_by(uuid=uuid).first()
    if library:
        print(f"Library found: {library.name} (UUID: {library.uuid})")
        return library
    print(f"Library not found for UUID: {uuid}")
    return None
