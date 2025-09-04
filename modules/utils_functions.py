import os
from PIL import Image as PILImage
import requests
import re
import html
from urllib.parse import urlparse
from wtforms.validators import ValidationError
from modules import db
from modules.models import ReleaseGroup, Library, Game
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from modules.models import GlobalSettings
from flask import url_for, current_app
from modules.utils_security import is_safe_path, get_allowed_base_directories

def format_size(size_in_bytes):
    """Format file size from bytes to human-readable format."""
    try:
        if size_in_bytes is None:
            return '0 MB'
        units = ['KB', 'MB', 'GB', 'TB', 'PB', 'EB']
        size = size_in_bytes / 1024  # Start with KB
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        return f"{size:.2f} {units[unit_index]}"
    except Exception as e:
        print(f"An error occurred: {e}")
        return '0 MB'


def square_image(image, size):
    """Create a square image with the given size."""
    image.thumbnail((size, size))
    if image.size[0] != size or image.size[1] != size:
        new_image = PILImage.new('RGB', (size, size), color='black')
        offset = ((size - image.size[0]) // 2, (size - image.size[1]) // 2)
        new_image.paste(image, offset)
        image = new_image
    return image

def get_folder_size_in_bytes(folder_path, timeout=300):
    """Calculate the total size of a folder in bytes.
    
    Args:
        folder_path (str): Path to the folder
        timeout (int): Maximum time in seconds to spend calculating size
    
    Returns:
        int: Total size in bytes, or 0 if there was an error
    """
    try:
        # Validate folder path security (only if we're in an application context)
        try:
            if current_app:
                allowed_bases = get_allowed_base_directories(current_app)
                if not allowed_bases:
                    print(f"Security error: No allowed base directories configured for path: {folder_path}")
                    return 0

                is_safe, error_message = is_safe_path(folder_path, allowed_bases)
                if not is_safe:
                    print(f"Security error: Path validation failed for {folder_path}: {error_message}")
                    return 0
        except RuntimeError:
            # Working outside of application context - skip validation for now
            # This is expected during unit tests
            pass
        # Check if path exists and is accessible
        if not os.path.exists(folder_path):
            print(f"Error: Path does not exist: {folder_path}")
            return 0
            
        # Handle single file case first
        if os.path.isfile(folder_path):
            return os.path.getsize(folder_path)
            
        if not os.access(folder_path, os.R_OK):
            print(f"Error: No read permission for path: {folder_path}")
            return 0

        total_size = 0
        for dirpath, dirnames, filenames in os.walk(folder_path):
            try:
                # Skip if we can't access the directory
                if not os.access(dirpath, os.R_OK):
                    print(f"Warning: Skipping inaccessible directory: {dirpath}")
                    continue

                for f in filenames:
                    try:
                        fp = os.path.join(dirpath, f)
                        # Skip symlinks unless they point to regular files
                        if os.path.islink(fp):
                            continue
                        if os.path.exists(fp):
                            total_size += os.path.getsize(fp)
                    except (OSError, IOError) as e:
                        print(f"Error processing file {f}: {e}")
                        continue
            except (OSError, IOError) as e:
                print(f"Error accessing directory {dirpath}: {e}")
                continue

        return max(total_size, 1)

    except Exception as e:
        print(f"Unexpected error calculating folder size: {e}")
        return 0


def get_folder_size_in_bytes_updates(folder_path, timeout=300):
    """Calculate folder size excluding update and extras folders."""
    try:
        # Validate folder path security (only if we're in an application context)
        try:
            if current_app:
                allowed_bases = get_allowed_base_directories(current_app)
                if not allowed_bases:
                    print(f"Security error: No allowed base directories configured for path: {folder_path}")
                    return 0

                is_safe, error_message = is_safe_path(folder_path, allowed_bases)
                if not is_safe:
                    print(f"Security error: Path validation failed for {folder_path}: {error_message}")
                    return 0
        except RuntimeError:
            # Working outside of application context - skip validation for now  
            # This is expected during unit tests
            pass
        # Handle single file case first
        if os.path.isfile(folder_path):
            return os.path.getsize(folder_path)
            
        if not os.path.exists(folder_path):
            print(f"Error: Path does not exist: {folder_path}")
            return 0
            
        if not os.access(folder_path, os.R_OK):
            print(f"Error: No read permission for path: {folder_path}")
            return 0

        settings = db.session.execute(select(GlobalSettings)).scalars().first()
        total_size = 0
        
        for dirpath, dirnames, filenames in os.walk(folder_path):
            try:
                # Skip if we can't access the directory
                if not os.access(dirpath, os.R_OK):
                    print(f"Warning: Skipping inaccessible directory: {dirpath}")
                    continue

                # Check if current directory should be excluded
                should_process = True
                if settings:
                    if (settings.update_folder_name and settings.update_folder_name.lower() in dirpath.lower()) or \
                       (settings.extras_folder_name and settings.extras_folder_name.lower() in dirpath.lower()):
                        should_process = False

                if should_process:
                    for f in filenames:
                        try:
                            fp = os.path.join(dirpath, f)
                            if os.path.islink(fp):
                                continue
                            if os.path.exists(fp):
                                total_size += os.path.getsize(fp)
                        except (OSError, IOError) as e:
                            print(f"Error processing file {f}: {e}")
                            continue

            except (OSError, IOError) as e:
                print(f"Error accessing directory {dirpath}: {e}")
                continue

        return max(total_size, 1)

    except Exception as e:
        print(f"Unexpected error calculating folder size: {e}")
        return 0


def read_first_nfo_content(full_disk_path):
    """Read the content of the first NFO file found in the given path."""
    print(f"Searching for NFO file in: {full_disk_path}")
    
    # Validate folder path security (only if we're in an application context)
    try:
        if current_app:
            allowed_bases = get_allowed_base_directories(current_app)
            if not allowed_bases:
                print(f"Security error: No allowed base directories configured for path: {full_disk_path}")
                return None

            is_safe, error_message = is_safe_path(full_disk_path, allowed_bases)
            if not is_safe:
                print(f"Security error: Path validation failed for {full_disk_path}: {error_message}")
                return None
    except RuntimeError:
        # Working outside of application context - skip validation for now  
        # This is expected during unit tests
        pass
    
    if os.path.isfile(full_disk_path):
        print("Path is a file, not a directory. Skipping NFO scan.")
        return None
        
    try:
        for file in os.listdir(full_disk_path):
            if file.lower().endswith('.nfo'):
                nfo_path = os.path.join(full_disk_path, file)
                print(f"Found NFO file: {nfo_path}")
                
                try:
                    with open(nfo_path, 'r', encoding='utf-8', errors='ignore') as nfo_file:
                        content = nfo_file.read()
                        sanitized_content = content.replace('\x00', '')
                        print(f"Successfully read NFO content (length: {len(sanitized_content)})")
                        return sanitized_content
                except Exception as e:
                    print(f"Error reading NFO file {nfo_path}: {str(e)}")
                    continue
                    
    except Exception as e:
        print(f"Error accessing directory {full_disk_path}: {str(e)}")
    
    print("No NFO file found")
    return None

def download_image(url, save_path):
    """Download an image from a URL and save it to the specified path."""
    if not url.startswith(('http://', 'https://')):
        url = 'https:' + url

    url = url.replace('/t_thumb/', '/t_original/')

    try:
        response = requests.get(url)
        if response.status_code == 200:
            directory = os.path.dirname(save_path)

            if not os.path.exists(directory):
                print(f"'{directory}' does not exist. Attempting to create it.")
                try:
                    os.makedirs(directory, exist_ok=True)
                    print(f"Successfully created the directory '{directory}'.")
                except Exception as e:
                    print(f"Failed to create the directory '{directory}': {e}")
                    return

            if os.access(directory, os.W_OK):
                with open(save_path, 'wb') as f:
                    f.write(response.content)
            else:
                print(f"Error: The directory '{directory}' is not writable.")
        else:
            print(f"Failed to download the image. Status Code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading image from {url}: {e}")
    except Exception as e:
        print(f"An error occurred while saving the image to {save_path}: {e}")

def comma_separated_urls(form, field):
    """Validate comma-separated YouTube embed URLs."""
    urls = field.data.split(',')
    url_pattern = re.compile(
        r'^(https?:\/\/)?(www\.)?youtube\.com\/embed\/[\w-]+$'
    )
    for url in urls:
        if not url_pattern.match(url.strip()):
            raise ValidationError('One or more URLs are invalid. Please provide valid YouTube embed URLs.')


def website_category_to_string(category_id):
    # Mapping based on IGDB API documentation for website categories
    category_mapping = {
        1: "official",
        2: "wikia",
        3: "wikipedia",
        4: "facebook",
        5: "twitter",
        6: "twitch",
        8: "instagram",
        9: "youtube",
        10: "iphone",
        11: "ipad",
        12: "android",
        13: "steam",
        14: "reddit",
        15: "itch",
        16: "epicgames",
        17: "gog",
        18: "discord"
    }
    return category_mapping.get(category_id, "unknown")

PLATFORM_IDS = {
    "PCWIN": 6,
    "PCDOS": 13,
    "N64": 4,
    "GB": 33,
    "GBA": 24,
    "NDS": 20,
    "NES": 18,
    "SNES": 19,
    "NGC" : 21,
    "XBOX": 11,
    "X360": 12,
    "XONE": 49,
    "XSX": 169,
    "PSX": 7,
    "PS2": 8,
    "PS3": 9,
    "PS4": 48,
    "PS5": 167,
    "PSP": 38,
    "VB": 87,
    "SEGA_MD": 29,
    "SEGA_MS": 86,
    "SEGA_CD": 78,
    "LYNX": 61,
    "SEGA_32X": 30,
    "JAGUAR": 62,
    "SEGA_GG": 35,
    "SEGA_SATURN": 32,
    "ATARI_7800": 60,
    "ATARI_2600": 59,
    "PCE": 128,
    "PCFX": 274,
    "NGP": 119,
    "WS": 57,
    "COLECO": 68,
    "VICE_X64SC": 15,
    "VICE_X128": 15,
    "VICE_XVIC": 71,
    "VICE_XPLUS4": 94,
    "VICE_XPET": 90,
    "OTHER": None,  # Assuming "Other/Mixed" has no specific ID
}


def load_release_group_patterns():
    try:
        # Fetching insensitive patterns (not case-sensitive)
        insensitive_patterns = [
            "-" + rg.rlsgroup for rg in db.session.execute(select(ReleaseGroup).filter(ReleaseGroup.rlsgroup != None)).scalars().all()
        ] + [
            "." + rg.rlsgroup for rg in db.session.execute(select(ReleaseGroup).filter(ReleaseGroup.rlsgroup != None)).scalars().all()
        ]
        
        # Initializing list for sensitive patterns (case-sensitive)
        sensitive_patterns = []
        for rg in db.session.execute(select(ReleaseGroup).filter(ReleaseGroup.rlsgroupcs != None)).scalars().all():
            pattern = rg.rlsgroupcs
            is_case_sensitive = False
            if pattern.lower() == 'yes':
                is_case_sensitive = True
                pattern = "-" + rg.rlsgroup
                sensitive_patterns.append((pattern, is_case_sensitive))
                pattern = "." + rg.rlsgroup
                sensitive_patterns.append((pattern, is_case_sensitive))
            elif pattern.lower() == 'no':
                pattern = "-" + rg.rlsgroup
                sensitive_patterns.append((pattern, is_case_sensitive))
                pattern = "." + rg.rlsgroup
                sensitive_patterns.append((pattern, is_case_sensitive))

        return insensitive_patterns, sensitive_patterns
    except SQLAlchemyError as e:
        print(f"An error occurred while fetching release group patterns: {e}")
        return [], []


def get_library_count():
    # Direct query to the Library model
    libraries_query = db.session.execute(select(Library)).scalars().all()
    libraries = [
        {
            'uuid': lib.uuid,
            'name': lib.name,
            'image_url': lib.image_url if lib.image_url else url_for('static', filename='newstyle/default_library.jpg')
        } for lib in libraries_query
    ]

    # Logging the count of libraries returned
    print(f"Returning {len(libraries)} libraries.")
    return len(libraries)

def get_games_count():
    # Direct query to the Games model
    games_query = db.session.execute(select(Game)).scalars().all()
    games = [
        {
            'uuid': game.uuid,
            'name': game.name,
        } for game in games_query
    ]

    # Logging the count of games returned
    print(f"Returning {len(games)} games.")
    return len(games)

def delete_associations_for_game(game_to_delete):
    associations = [game_to_delete.genres, game_to_delete.platforms, game_to_delete.game_modes,
                    game_to_delete.themes, game_to_delete.player_perspectives, game_to_delete.multiplayer_modes]
    
    for association in associations:
        association.clear()

# Discord Input Validation Functions

def sanitize_string_input(input_str, max_length, allow_html=False):
    """Sanitize string input to prevent XSS and ensure length limits."""
    if not input_str:
        return ''
    
    # Convert to string and strip whitespace
    sanitized = str(input_str).strip()
    
    # HTML escape if not allowing HTML
    if not allow_html:
        sanitized = html.escape(sanitized)
    
    # Enforce length limit
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized

def validate_discord_webhook_url(url, max_length=512):
    """Validate Discord webhook URL format and length."""
    if not url:
        return False, "Webhook URL is required"
    
    # Sanitize input
    sanitized_url = sanitize_string_input(url, max_length)
    
    # Check length
    if len(sanitized_url) > max_length:
        return False, f"Webhook URL must be {max_length} characters or less"
    
    # Check if it's a valid URL structure
    try:
        parsed = urlparse(sanitized_url)
        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL format"
    except Exception:
        return False, "Invalid URL format"
    
    # Check HTTPS requirement
    if not sanitized_url.startswith('https://'):
        return False, "Webhook URL must use HTTPS"
    
    # Check Discord webhook URL format
    if not ('discord.com/api/webhooks/' in sanitized_url or 'discordapp.com/api/webhooks/' in sanitized_url):
        return False, "URL must be a valid Discord webhook URL"
    
    return True, sanitized_url

def validate_discord_bot_name(name, max_length=100):
    """Validate Discord bot name."""
    if not name:
        return False, "Bot name is required"
    
    # Sanitize input
    sanitized_name = sanitize_string_input(name, max_length)
    
    # Check length
    if len(sanitized_name) > max_length:
        return False, f"Bot name must be {max_length} characters or less"
    
    # Check for valid characters (alphanumeric, spaces, basic punctuation)
    allowed_pattern = re.compile(r'^[a-zA-Z0-9\s\-_\.]+$')
    if not allowed_pattern.match(sanitized_name):
        return False, "Bot name can only contain letters, numbers, spaces, hyphens, underscores, and periods"
    
    return True, sanitized_name

def validate_discord_avatar_url(url, max_length=512):
    """Validate Discord bot avatar URL (optional field)."""
    if not url:
        return True, ''  # Optional field, empty is valid
    
    # Sanitize input
    sanitized_url = sanitize_string_input(url, max_length)
    
    # Check length
    if len(sanitized_url) > max_length:
        return False, f"Avatar URL must be {max_length} characters or less"
    
    # Check if it's a valid URL structure
    try:
        parsed = urlparse(sanitized_url)
        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL format"
    except Exception:
        return False, "Invalid URL format"
    
    # Check HTTPS requirement
    if not sanitized_url.startswith('https://'):
        return False, "Avatar URL must use HTTPS"
    
    return True, sanitized_url


def get_url_icon(url_type, url):
    """
    Get the appropriate Font Awesome icon for a URL based on type and URL pattern matching.
    
    Args:
        url_type (str): The stored URL type from database
        url (str): The actual URL for pattern matching fallback
    
    Returns:
        str: Font Awesome icon class
    """
    # Primary icon mapping based on stored type
    type_icons = {
        "official": "fa-solid fa-globe",
        "wikia": "fa-brands fa-wikimedia", 
        "wikipedia": "fa-brands fa-wikipedia-w",
        "facebook": "fa-brands fa-facebook",
        "twitter": "fa-brands fa-twitter", 
        "twitch": "fa-brands fa-twitch",
        "instagram": "fa-brands fa-instagram",
        "youtube": "fa-brands fa-youtube",
        "steam": "fa-brands fa-steam",
        "reddit": "fa-brands fa-reddit",
        "itch": "fa-brands fa-itch-io",
        "epicgames": "fa-brands fa-epic-games",
        "gog": "fa-brands fa-gog",
        "discord": "fa-brands fa-discord",
        "android": "fa-brands fa-android",
        "iphone": "fa-brands fa-apple",
        "ipad": "fa-brands fa-apple"
    }
    
    # If we have a known type, use it
    if url_type in type_icons:
        return type_icons[url_type]
    
    # Fallback: Pattern matching for "unknown" or unmapped types
    if not url:
        return "fa-solid fa-link"
        
    url_lower = url.lower()
    
    # URL pattern mapping for fallback detection
    url_patterns = {
        "steam": ["steampowered.com", "store.steampowered.com"],
        "gog": ["gog.com", "www.gog.com"],
        "epicgames": ["epicgames.com", "store.epicgames.com"],
        "itch": ["itch.io"],
        "youtube": ["youtube.com", "youtu.be"],
        "twitch": ["twitch.tv"],
        "discord": ["discord.gg", "discord.com"],
        "reddit": ["reddit.com"],
        "facebook": ["facebook.com", "fb.com"],
        "twitter": ["twitter.com", "x.com"],
        "instagram": ["instagram.com"],
        "wikipedia": ["wikipedia.org"],
        "wikia": ["fandom.com", "wikia.com"],
        "official": []  # Will be handled by default case
    }
    
    # Check URL patterns
    for pattern_type, domains in url_patterns.items():
        for domain in domains:
            if domain in url_lower:
                return type_icons.get(pattern_type, "fa-solid fa-link")
    
    # Default fallback
    return "fa-solid fa-link"
