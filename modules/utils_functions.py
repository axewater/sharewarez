import os
from PIL import Image as PILImage
import requests
import re
from wtforms.validators import ValidationError
from modules import db
from modules.models import ReleaseGroup, Library, Game
from sqlalchemy.exc import SQLAlchemyError
from modules.models import GlobalSettings
from flask import url_for

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

def get_folder_size_in_bytes(folder_path):
    """Calculate the total size of a folder in bytes."""
    if os.path.isfile(folder_path):
        return os.path.getsize(folder_path)
    
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
    return max(total_size, 1)

def get_folder_size_in_bytes_updates(folder_path):
    settings = GlobalSettings.query.first()
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            if settings and settings.update_folder_name and settings.update_folder_name != "" and settings.extras_folder_name and settings.extras_folder_name != "":
                if settings.update_folder_name.lower() not in dirpath.lower() and settings.extras_folder_name.lower() not in dirpath.lower():
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
            elif settings and settings.update_folder_name and settings.update_folder_name != "":
                if settings.update_folder_name.lower() not in dirpath.lower():
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
            elif settings.extras_folder_name and settings.extras_folder_name != "":
                if settings.extras_folder_name.lower() not in dirpath.lower():
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
            else:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
    return total_size



def read_first_nfo_content(full_disk_path):
    """Read the content of the first NFO file found in the given path."""
    print(f"Searching for NFO file in: {full_disk_path}")
    
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
            "-" + rg.rlsgroup for rg in ReleaseGroup.query.filter(ReleaseGroup.rlsgroup != None).all()
        ] + [
            "." + rg.rlsgroup for rg in ReleaseGroup.query.filter(ReleaseGroup.rlsgroup != None).all()
        ]
        
        # Initializing list for sensitive patterns (case-sensitive)
        sensitive_patterns = []
        for rg in ReleaseGroup.query.filter(ReleaseGroup.rlsgroupcs != None).all():
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
    libraries_query = Library.query.all()
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
    games_query = Game.query.all()
    games = [
        {
            'uuid': game.uuid,
            'name': game.name,
        } for game in games_query
    ]

    # Logging the count of games returned
    print(f"Returning {len(games)} games.")
    return len(games)
