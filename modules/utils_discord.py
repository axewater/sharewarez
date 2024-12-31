from discord_webhook import DiscordWebhook, DiscordEmbed
from flask import current_app
from modules.models import GlobalSettings, Library, Game, GameURL, db
import os
import time
from datetime import datetime
from modules.utils_game_core import get_folder_size_in_bytes_updates
from modules.utils_igdb_api import get_cover_url


def discord_get_game_by_uuid(game_uuid):
    print(f"Searching for game UUID: {game_uuid}")
    game = Game.query.filter_by(uuid=game_uuid).first()
    if game:
        print(f"Game ID {game.id} with name {game.name} and UUID {game.uuid} relating to IGDB ID {game.igdb_id} found")
        return game
    else:
        print("Game not found")
        return None

def format_size(size_in_bytes):
    try:
        if size_in_bytes is None:
            return '0 MB'  # Fallback value if size_in_bytes is None
        else:
            # Define size units
            units = ['KB', 'MB', 'GB', 'TB', 'PB', 'EB']
            size = size_in_bytes / 1024  # Start with KB
            unit_index = 0
            while size >= 1024 and unit_index < len(units) - 1:
                size /= 1024
                unit_index += 1
            return f"{size:.2f} {units[unit_index]}"
    except Exception as e:
        print(f"An error occurred: {e}")
        return '0 MB'  # Fallback value for any other errors



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




def discord_webhook(game_uuid): #Used for notifying of new games.
    # Check if Discord webhook URL is configured
    settings = GlobalSettings.query.first()
    if not settings or not settings.discord_webhook_url:
        print("Discord webhook URL not configured")
        return
        
    # Check if Discord notifications are enabled for new games
    if not settings.discord_notify_new_games:
        print("Discord notifications for new games are disabled")
        return

    newgame = discord_get_game_by_uuid(game_uuid)
    newgame_size = format_size(newgame.size)
    newgame_library = get_library_by_uuid(newgame.library_uuid)
    
    # Get Discord settings from database first, fallback to config
    discord_webhook = settings.discord_webhook_url
    discord_bot_name = settings.discord_bot_name
    discord_bot_avatar_url = settings.discord_bot_avatar_url
    
    site_url = settings.site_url
    cover_url = get_cover_url(newgame.igdb_id)
    # if rate_limit_retry is True then in the event that you are being rate 
    # limited by Discord your webhook will automatically be sent once the 
    # rate limit has been lifted
    webhook = DiscordWebhook(url=f"{discord_webhook}", rate_limit_retry=True)
    # create embed object for webhook
    embed = DiscordEmbed(title=f"{newgame.name}", description=f"{newgame.summary}", url=f"{site_url}/game_details/{newgame.uuid}", color="03b2f8")
    # set author
    embed.set_author(name=f"{discord_bot_name}", url=f"{site_url}", icon_url=f"{discord_bot_avatar_url}")
    # set cover image
    embed.set_image(url=f"{cover_url}")
    # set footer
    embed.set_footer(text="This game is now available for download")
    # set timestamp (default is now) accepted types are int, float and datetime
    embed.set_timestamp()
    # add fields to embed
    # Set `inline=False` for the embed field to occupy the whole line
    embed.add_embed_field(name="Library", value=f"{newgame_library.name}")
    embed.add_embed_field(name="Size", value=f"{newgame_size}")
    # add embed object to webhook
    webhook.add_embed(embed)
    response = webhook.execute()
        
def discord_update(path,event, folder_name, game_path, file_name, file_size, game, game_library): #Used for notifying of game and file updates.
    global settings
    settings = GlobalSettings.query.first()
    
    #Get custom folder names and Settings
    update_folder = settings.update_folder_name
    extras_folder = settings.extras_folder_name

    # Check if Discord webhook URL is configured   
    if not settings or not settings.discord_webhook_url:
        print("Discord webhook URL not configured")
        return

    #Check if event is an update file.
    if event == "created_update":           
        # Check if Discord notifications are enabled for game updates
        if not settings.discord_notify_game_updates:
            print("Discord notifications for game updates are disabled")
            return
        
        print("Processing Discord notification for game file update.")
        
        # Get Discord settings from database first, fallback to config
        discord_webhook = settings.discord_webhook_url
        discord_bot_name = settings.discord_bot_name
        discord_bot_avatar_url = settings.discord_bot_avatar_url
        
        site_url = settings.site_url
        cover_url = get_cover_url(game.igdb_id)
        # if rate_limit_retry is True then in the event that you are being rate 
        # limited by Discord your webhook will automatically be sent once the 
        # rate limit has been lifted
        webhook = DiscordWebhook(url=f"{discord_webhook}", rate_limit_retry=True)
        # create embed object for webhook
        embed = DiscordEmbed(title=f"Update File Available for {game.name}", url=f"{site_url}/game_details/{game.uuid}", color="21f704")
        # set author
        embed.set_author(name=f"{discord_bot_name}", url=f"{site_url}", icon_url=f"{discord_bot_avatar_url}")
        # set cover image
        embed.set_image(url=f"{cover_url}")
        # set footer
        embed.set_footer(text="This game has an update available for download")
        # set timestamp (default is now) accepted types are int, float and datetime
        embed.set_timestamp()
        # add fields to embed
        # Set `inline=False` for the embed field to occupy the whole line
        embed.add_embed_field(name="Library", value=f"{game_library.name}")
        embed.add_embed_field(name="File", value=f"{file_name}")
        embed.add_embed_field(name="Size", value=f"{file_size}")
        # add embed object to webhook
        webhook.add_embed(embed)
        response = webhook.execute()
        
    #Check if event is an extra file.
    elif event == "created_extra":   
        # Check if Discord notifications are enabled for game extras
        if not settings.discord_notify_game_extras:
            print("Discord notifications for game extras are disabled")
            return
        
        print("Processing new extra file.")
        
        # Get Discord settings from database first, fallback to config
        discord_webhook = settings.discord_webhook_url if settings and settings.discord_webhook_url else current_app.config['DISCORD_WEBHOOK_URL']
        discord_bot_name = settings.discord_bot_name if settings and settings.discord_bot_name else current_app.config['DISCORD_BOT_NAME']
        discord_bot_avatar_url = settings.discord_bot_avatar_url
        
        site_url = settings.site_url
        cover_url = get_cover_url(game.igdb_id)
        # if rate_limit_retry is True then in the event that you are being rate 
        # limited by Discord your webhook will automatically be sent once the 
        # rate limit has been lifted
        webhook = DiscordWebhook(url=f"{discord_webhook}", rate_limit_retry=True)
        # create embed object for webhook
        embed = DiscordEmbed(title=f"Extra File Available for {game.name}", url=f"{site_url}/game_details/{game.uuid}", color="f304f7")
        # set author
        embed.set_author(name=f"{discord_bot_name}", url=f"{site_url}", icon_url=f"{discord_bot_avatar_url}")
        # set cover image
        embed.set_image(url=f"{cover_url}")
        # set footer
        embed.set_footer(text="This game has an extra file available for download")
        # set timestamp (default is now) accepted types are int, float and datetime
        embed.set_timestamp()
        # add fields to embed
        # Set `inline=False` for the embed field to occupy the whole line
        embed.add_embed_field(name="Library", value=f"{game_library.name}")
        embed.add_embed_field(name="File", value=f"{file_name}")
        embed.add_embed_field(name="Size", value=f"{file_size}")
        # add embed object to webhook
        webhook.add_embed(embed)
        response = webhook.execute()

    elif event == "modified":
        # Check if Discord notifications are enabled for game updates
        if not settings.discord_notify_game_updates:
            print("Discord notifications for game updates are disabled.")
            return
            
        # Get Discord settings from database first, fallback to config
        discord_webhook = settings.discord_webhook_url
        discord_bot_name = settings.discord_bot_name
        discord_bot_avatar_url = settings.discord_bot_avatar_url
        
        site_url = settings.site_url
        cover_url = get_cover_url(game.igdb_id)
        # if rate_limit_retry is True then in the event that you are being rate 
        # limited by Discord your webhook will automatically be sent once the 
        # rate limit has been lifted
        webhook = DiscordWebhook(url=f"{discord_webhook}", rate_limit_retry=True)
        # create embed object for webhook
        embed = DiscordEmbed(title=f"Main Game Update Available for {game.name}", url=f"{site_url}/game_details/{game.uuid}", color="f71604")
        # set author
        embed.set_author(name=f"{discord_bot_name}", url=f"{site_url}", icon_url=f"{discord_bot_avatar_url}")
        # set cover image
        embed.set_image(url=f"{cover_url}")
        # set footer
        embed.set_footer(text=f"The main file for this game has been updated and is available for download.")
        # set timestamp (default is now) accepted types are int, float and datetime
        embed.set_timestamp()
        # add fields to embed
        # Set `inline=False` for the embed field to occupy the whole line
        embed.add_embed_field(name="Library", value=f"{game_library.name}")
        embed.add_embed_field(name="File", value=f"{file_name}")
        embed.add_embed_field(name="Size", value=f"{file_size}")
        # add embed object to webhook
        webhook.add_embed(embed)
        response = webhook.execute()
    
def get_library_by_uuid(uuid):
    print(f"Searching for Library UUID: {uuid}")
    library = Library.query.filter_by(uuid=uuid).first()
    if library:
        print(f"Library with name {library.name} and UUID {library.uuid} found")
        return library
    else:
        print("Library not found")
        return None
        

    
def update_game_last_updated(game_uuid, updated_time):
    game = discord_get_game_by_uuid(game_uuid)
    game.last_updated = updated_time
    db.session.commit()
    return None

global last_game_path
last_game_path = ''
global last_update_time
last_update_time = time.time()
global first_run
first_run = 1

def notifications_manager(path, event, game_uuid=None):
    global last_game_path
    global settings
    settings = GlobalSettings.query.first()
    
    update_folder = settings.update_folder_name
    extras_folder = settings.extras_folder_name
    
    #If fired by Watchdog
    print(f"Processing {event} event for game located at path {path}")
    #Process the created event and fire notifications.
    if event == "created":
        if os.name == "nt":
            folder_name = path.split('\\')[-2]
            game_path = path.rpartition('\\')[0]
            game_path = game_path.rpartition('\\')[0]
            file_name = path.split('\\')[-1]
        else:
            folder_name = path.split('/')[-2]
            game_path = path.rpartition('/')[0]
            game_path = game_path.rpartition('/')[0]
            file_name = path.split('/')[-1]
        print(f"Getting game located at path {game_path}")
        
        #Process the folder
        if update_folder.lower() == folder_name.lower():
            event = "created_update"
        elif extras_folder.lower() == folder_name.lower():
            event = "created_extra"
        
        if os.path.isfile(path):
            file_size = os.path.getsize(path)
        else:
            file_size = get_folder_size_in_bytes(path)
        file_size = format_size(file_size)
        game = get_game_by_full_disk_path(game_path, path)
        
        if game:
            updated_time = datetime.utcnow()
            game_library = get_library_by_uuid(game.library_uuid)
            if event == "created_update":
                update_game_last_updated(game.uuid, updated_time)
        
        else:
            print("No matching update notifications for this file.")
            return
         
        #Send Discord notification if enabled.
        if settings.discord_notify_game_updates or settings.discord_notify_game_extras:
            discord_update(path,event, folder_name, game_path, file_name, file_size, game, game_library)     
    
    #Process modified event and fire notifications.
    elif event == "modified":
        if os.name == "nt":
            game_path = path.rpartition('\\')[0]
            file_name = path.split('\\')[-1]
            folder_name = path.split('\\')[-2]
            file_ext = path.split('.')[-1]
        else:
            game_path = path.rpartition('/')[0]
            file_name = path.split('/')[-1]
        print(f"Getting game located at path {game_path} with file path {path}")
        
        if folder_name.lower() == update_folder.lower() or folder_name.lower() == extras_folder.lower():
            print("This is an update or extra folder. Not processing.")
            return
        
        game = get_game_by_full_disk_path(game_path, path)
        
        number_of_files = len([f for f in os.listdir(game_path) if os.path.isfile(os.path.join(game_path, f)) and f.split('.')[-1] != 'txt' and f.split('.')[-1] != 'nfo'])
        
        if number_of_files > 1:
            elapsed_seconds = time.time() - last_update_time
            elapsed_minutes = elapsed_seconds / 60
            if last_game_path == game_path and elapsed_minutes < 60:
                print(f"This game folder contains {number_of_files} game files and this file will not be included in the update notifications. Last updated {int(elapsed_minutes)} minutes ago.")
                return

            file_size = get_folder_size_in_bytes_updates(game_path)
            last_game_path = game_path
            if os.name == "nt":
                file_name = path.split('\\')[-2]
            else:
                file_name = path.split('/')[-2]
        else:
            file_size = os.path.getsize(path)
            last_game_path = game_path

        #If OS is Windows and the exe file detected is a not a main game file change, ignore it. If main game file change, check to see if size actually changed.
        if os.name == "nt":
            if game:
                if update_folder.lower() in path.lower() or extras_folder.lower() in path.lower() and file_ext == "exe":
                    print(f"The extension {file_ext} will not used for {folder_name}")
                    return
                else:
                    if file_size == game.size:
                        print(f"There is no change in {file_name}. File size is {file_size} and original size is {game.size}.")
                        return
                    else:
                        print(f"There is a change in {file_name} at path {game_path}. New file size is {file_size} and original size is {game.size}.")
            else:
                print(f"No found game.")
                return
                
        if game.full_disk_path == game_path:
            print(f"Updating new game size as {file_size} and original size is {game.size}. Path is {path}")
            update_game_size(game.uuid, file_size)
                    
        file_size = format_size(file_size)
            
        if game:
            updated_time = datetime.utcnow()
            game_library = get_library_by_uuid(game.library_uuid)
            
            # Get Discord settings from database first, fallback to config
            discord_webhook = settings.discord_webhook_url if settings and settings.discord_webhook_url else current_app.config['DISCORD_WEBHOOK_URL']
            discord_bot_name = settings.discord_bot_name if settings and settings.discord_bot_name else current_app.config['DISCORD_BOT_NAME']
            discord_bot_avatar_url = settings.discord_bot_avatar_url if settings and settings.discord_bot_avatar_url else current_app.config['DISCORD_BOT_AVATAR_URL']
            
            site_url = current_app.config['SITE_URL']
            cover_url = get_cover_url(game.igdb_id)
            # if rate_limit_retry is True then in the event that you are being rate 
            # limited by Discord your webhook will automatically be sent once the 
            # rate limit has been lifted
            webhook = DiscordWebhook(url=f"{discord_webhook}", rate_limit_retry=True)
            # create embed object for webhook
            embed = DiscordEmbed(title=f"Main Game Update Available for {game.name}", url=f"{site_url}/game_details/{game.uuid}", color="f71604")
            # set author
            embed.set_author(name=f"{discord_bot_name}", url=f"{site_url}", icon_url=f"{discord_bot_avatar_url}")
            # set cover image
            embed.set_image(url=f"{cover_url}")
            # set footer
            embed.set_footer(text=f"The main file for this game has been updated and is available for download.")
            # set timestamp (default is now) accepted types are int, float and datetime
            embed.set_timestamp()
            # add fields to embed
            # Set `inline=False` for the embed field to occupy the whole line
            embed.add_embed_field(name="Library", value=f"{game_library.name}")
            embed.add_embed_field(name="File", value=f"{file_name}")
            embed.add_embed_field(name="Size", value=f"{file_size}")
            # add embed object to webhook
            webhook.add_embed(embed)
            response = webhook.execute()
    
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
    game = discord_get_game_by_uuid(game_uuid)
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
