from discord_webhook import DiscordWebhook, DiscordEmbed
from flask import current_app
from modules.models import GlobalSettings, Library, Game, GameURL, db
import os
import time
from datetime import datetime
from modules.utils_igdb_api import get_cover_url
from modules.utils_functions import format_size

def get_folder_size_in_bytes(folder_path):
    if os.path.isfile(folder_path):
        return os.path.getsize(folder_path)
    
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
    return max(total_size, 1)  # Ensure the size is at least 1 byte


def discord_webhook(game_uuid):
    """
    Sends a Discord notification for the given game UUID 
    if Discord notifications are enabled and webhook URL is configured.
    """
    print(f"Discord notifications: Starting for game UUID '{game_uuid}'.")

    # Get global settings once
    settings = GlobalSettings.query.first()

    # Return early if settings or webhook URL are not properly configured
    if not settings or not settings.discord_webhook_url:
        print("Discord notifications: Webhook URL not configured. Exiting.")
        return

    # Return early if notifications for new games are disabled
    if not settings.discord_notify_new_games:
        print("Discord notifications: Disabled for new games. Exiting.")
        return

    # Retrieve the game by UUID
    new_game = Game.query.filter_by(uuid=game_uuid).first()
    if not new_game:
        print(f"Discord notifications: Game with UUID '{game_uuid}' could not be found. Exiting.")
        return

    # Prepare game info
    new_game_size = format_size(new_game.size)
    new_game_library = get_library_by_uuid(new_game.library_uuid)
    cover_url = get_cover_url(new_game.igdb_id)

    # Log some useful details
    print(f"Discord notifications: Found game '{new_game.name}' in library '{new_game_library.name}'")
    print(f"Discord notifications: Size: {new_game_size}, Cover URL: {cover_url}")

    # Extract needed settings
    discord_webhook_url = settings.discord_webhook_url
    discord_bot_name = settings.discord_bot_name
    discord_bot_avatar_url = settings.discord_bot_avatar_url
    site_url = settings.site_url

    # Initialize Discord webhook and embed
    webhook = DiscordWebhook(url=discord_webhook_url, rate_limit_retry=True)
    embed = DiscordEmbed(
        title=new_game.name,
        description=new_game.summary or "",  # Fallback if summary is None
        url=f"{site_url}/game_details/{new_game.uuid}",
        color="03b2f8"
    )

    # Populate embed details
    embed.set_author(name=discord_bot_name, url=site_url, icon_url=discord_bot_avatar_url)
    embed.set_image(url=cover_url)
    embed.set_footer(text="This game is now available for download")
    embed.set_timestamp()
    embed.add_embed_field(name="Library", value=new_game_library.name)
    embed.add_embed_field(name="Size", value=new_game_size)

    # Add the embed to the webhook and execute
    webhook.add_embed(embed)
    response = webhook.execute()

    # Print the response for debugging/confirmation
    print(f"Discord notifications: Webhook executed. Response: {response}")

        
    
def get_library_by_uuid(uuid):
    print(f"Searching for Library UUID: {uuid}")
    library = Library.query.filter_by(uuid=uuid).first()
    if library:
        print(f"Library with name {library.name} and UUID {library.uuid} found")
        return library
    else:
        print("Library not found")
        return None
        
def get_game_name_by_uuid(uuid):
    print(f"Searching for game UUID: {uuid}")
    game = Game.query.filter_by(uuid=uuid).first()
    if game:
        print(f"Game with name {game.name} and UUID {game.uuid} found")
        return game.name
    else:
        print("Game not found")
        return None
        
def update_game_size(game_uuid, size):
    game = Game.query.filter_by(uuid=game_uuid).first()
    if game:
        game.size = size
        db.session.commit()
    return None


def get_game_by_full_disk_path(game_path, file_path=None):
    """
    Get a game from the database by its full disk path.
    
    Args:
        game_path (str): The full path to the game directory
        file_path (str, optional): Path to a specific file within the game directory
        
    Returns:
        Game: Game object if found, None otherwise
    """
    try:
        # First try exact match
        game = Game.query.filter_by(full_disk_path=game_path).first()
        if game:
            return game
            
        # If no exact match and file_path provided, try parent directory
        if file_path:
            parent_path = os.path.dirname(file_path)
            return Game.query.filter_by(full_disk_path=parent_path).first()
            
        return None
    except Exception as e:
        print(f"Error finding game by path {game_path}: {e}")
        return None
