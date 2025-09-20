import os
from flask import flash
import re
from modules import db
from modules.models import Game
from sqlalchemy import select

def get_game_names_from_folder(folder_path, insensitive_patterns, sensitive_patterns):
    if not os.path.exists(folder_path) or not os.access(folder_path, os.R_OK):
        print(f"Error: The folder '{folder_path}' does not exist or is not readable.")
        flash(f"Error: The folder '{folder_path}' does not exist or is not readable.")
        return []
    folder_contents = os.listdir(folder_path)
    game_names_with_paths = []
    for item in folder_contents:
        full_path = os.path.join(folder_path, item)
        if os.path.isdir(full_path):
            game_name = clean_game_name(item, insensitive_patterns, sensitive_patterns)
            game_names_with_paths.append({'name': game_name, 'full_path': full_path})
    return game_names_with_paths

def get_game_names_from_files(folder_path, extensions, insensitive_patterns, sensitive_patterns):
    if not os.path.exists(folder_path) or not os.access(folder_path, os.R_OK):
        print(f"Error: The path '{folder_path}' does not exist or is not readable.")
        return []
    file_contents = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    # print(f"Files found in folder: {file_contents}")
    game_names_with_paths = []
    for file_name in file_contents:
        print(f"Checking file: {file_name}")
        extension = file_name.split('.')[-1].lower()
        if extension in extensions:
            # print(f"Found supported file: {file_name}")
            # Extract the game name without the extension
            game_name_without_extension = '.'.join(file_name.split('.')[:-1])
            # Clean the game name
            cleaned_game_name = clean_game_name(game_name_without_extension, insensitive_patterns, sensitive_patterns)
            # print(f"Extracted and cleaned game name: {cleaned_game_name}")
            full_path = os.path.join(folder_path, file_name)
            
            game_names_with_paths.append({'name': cleaned_game_name, 'full_path': full_path, 'file_type': extension})
            # print(f"Added cleaned game name with path: {cleaned_game_name} at {full_path}")

    # print(f"Game names with paths extracted from files: {game_names_with_paths}")
    return game_names_with_paths


def get_game_name_by_uuid(uuid):
    print(f"Searching for game UUID: {uuid}")
    game = db.session.execute(select(Game).filter_by(uuid=uuid)).scalars().first()
    if game:
        print(f"Game with name {game.name} and UUID {game.uuid} found")
        return game.name
    else:
        print("Game not found")
        return None
    
    
def detect_goty_pattern(filename):
    """
    Detect if filename contains GOTY or G.O.T.Y. patterns.
    Returns tuple: (has_goty, standardized_name)
    """
    # Check for various GOTY patterns (case-insensitive)
    goty_patterns = [
        r'\bg\.o\.t\.y\.?(?=\s|$|\.|-)',    # g.o.t.y or g.o.t.y. (followed by space, end, dot, or hyphen)
        r'(?:^|[^a-zA-Z])goty(?=\s|$|-|\.|_)',  # goty (not preceded by letter, followed by space, end, hyphen, dot, or underscore)
    ]

    for i, pattern in enumerate(goty_patterns):
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            start, end = match.span()
            if i == 1:  # Special handling for the second pattern that includes preceding character
                # Check if match starts with a non-letter character
                if match.start() > 0 and not filename[match.start()].isalpha():
                    # Keep the preceding character
                    cleaned = filename[:start+1] + 'GOTY' + filename[end:]
                else:
                    cleaned = filename[:start] + 'GOTY' + filename[end:]
            else:
                # Standard replacement for first pattern
                cleaned = filename[:start] + 'GOTY' + filename[end:]
            return True, cleaned

    return False, filename


def generate_goty_variants(base_name):
    """
    Generate GOTY search variants for a game name containing GOTY.
    Returns list of variants to try.
    """
    if 'GOTY' not in base_name:
        return [base_name]

    # Generate variants
    variants = []

    # Try with GOTY
    variants.append(base_name)

    # Try with G.O.T.Y.
    goty_variant = base_name.replace('GOTY', 'G.O.T.Y.')
    variants.append(goty_variant)

    # Try without GOTY as fallback
    no_goty_variant = base_name.replace('GOTY', '').strip()
    # Clean up any double spaces
    no_goty_variant = re.sub(r'\s+', ' ', no_goty_variant).strip()
    if no_goty_variant:  # Only add if not empty
        variants.append(no_goty_variant)

    return variants


def clean_game_name(filename, insensitive_patterns, sensitive_patterns):
    # print(f"Original filename: {filename}")

    # Check and remove 'setup' at the start, case-insensitive
    if filename.lower().startswith('setup'):
        filename = filename[len('setup'):].lstrip("_").lstrip("-").lstrip()
        # print(f"After removing 'setup': {filename}")

    # Detect and preserve GOTY patterns early, before dot processing
    has_goty, filename = detect_goty_pattern(filename)

    # First handle version numbers and known patterns that should be removed
    filename = re.sub(r'v\d+(\.\d+)*', '', filename)  # Remove version numbers like v1.0.3
    filename = re.sub(r'(?:^|_|\s)\d+(\.\d+){2,}(?=_|\s|$)', '', filename)  # Remove complex version numbers like 1.9.23494.3
    filename = re.sub(r'\b\d+(\.\d+)+\b', '', filename)  # Remove standalone version numbers like 1.0.3
    filename = re.sub(r'_\(\d+\)_', '_', filename)  # Replace build numbers in parentheses like _(51906)_ with single underscore
    filename = re.sub(r'_?\(\d+\)_?', '', filename)  # Remove any remaining build numbers in parentheses

    # Handle dots between single letters (like A.Tale -> A Tale), but preserve GOTY if present
    if not has_goty or 'GOTY' not in filename:
        filename = re.sub(r'(?<=\b[A-Z])\.(?=[A-Z]\b|\s|$)', ' ', filename)
    else:
        # More careful dot handling when GOTY is present
        filename = re.sub(r'(?<=\b[A-Z])\.(?=[A-Z]\b|\s|$)(?!.*GOTY)', ' ', filename)

    # Replace remaining dots and underscores with spaces, but preserve GOTY
    if has_goty and 'GOTY' in filename:
        # Temporarily replace GOTY to protect it from dot processing
        filename = filename.replace('GOTY', 'GOTYPLACEHOLDER')
        filename = re.sub(r'(?<!^)(?<![\d])\.|_', ' ', filename)
        filename = filename.replace('GOTYPLACEHOLDER', 'GOTY')
    else:
        filename = re.sub(r'(?<!^)(?<![\d])\.|_', ' ', filename)

    # Define a regex pattern for version numbers
    version_pattern = r'\bv?\d+(\.\d+){1,3}'

    # Remove version numbers
    filename = re.sub(version_pattern, '', filename)

    # Remove known release group patterns
    for pattern in insensitive_patterns:
        escaped_pattern = re.escape(pattern)
        # Use word boundary only if pattern starts/ends with word characters
        if pattern[0].isalnum() and pattern[-1].isalnum():
            filename = re.sub(f"\\b{escaped_pattern}\\b", '', filename, flags=re.IGNORECASE)
        else:
            filename = re.sub(escaped_pattern, '', filename, flags=re.IGNORECASE)

    for pattern, is_case_sensitive in sensitive_patterns:
        escaped_pattern = re.escape(pattern)
        if is_case_sensitive:
            filename = re.sub(f"\\b{escaped_pattern}\\b", '', filename)
        else:
            filename = re.sub(f"\\b{escaped_pattern}\\b", '', filename, flags=re.IGNORECASE)

    # Handle cases with numerals and versions
    filename = re.sub(r'\b([IVXLCDM]+|[0-9]+)(?:[^\w]|$)', r' \1 ', filename)

    # Cleanup for versions, DLCs, etc.
    filename = re.sub(r'Build\.\d+', '', filename)
    filename = re.sub(r'(\+|\-)\d+DLCs?', '', filename, flags=re.IGNORECASE)
    filename = re.sub(r'Repack|Edition|Remastered|Remake|Proper|Dodi', '', filename, flags=re.IGNORECASE)

    # Remove trailing numbers enclosed in brackets
    filename = re.sub(r'\(\d+\)$', '', filename).strip()

    # Smart cleanup of trailing numbers - keep only one meaningful number at the end
    # Split by spaces and work backwards from the end
    words = filename.split()
    if len(words) > 1:
        # Find trailing numeric/garbage words
        trailing_numbers = []
        clean_words = []

        for word in reversed(words):
            # Check if word is purely numeric or obvious garbage
            if (word.isdigit() and len(word) <= 2) or word.lower() in ['win', 'gog', 'steam']:
                trailing_numbers.append(word)
            else:
                # Keep this word and stop looking
                clean_words = words[:len(words) - len(trailing_numbers)]
                break

        # If we found trailing garbage words, clean them up
        if trailing_numbers:
            # Look for a valid game sequel number (typically 1-20)
            valid_sequel = None
            for num_word in reversed(trailing_numbers):
                if num_word.isdigit() and 1 <= int(num_word) <= 20:
                    valid_sequel = num_word
                    break

            # Rebuild filename with cleaned words plus optional valid sequel number
            if valid_sequel:
                filename = ' '.join(clean_words + [valid_sequel])
            else:
                filename = ' '.join(clean_words)

    # Normalize whitespace and re-title
    filename = re.sub(r'\s+', ' ', filename).strip()
    cleaned_name = ' '.join(filename.split()).title()

    # Preserve GOTY in uppercase after title case conversion
    if has_goty:
        cleaned_name = re.sub(r'\bGoty\b', 'GOTY', cleaned_name)

    # print(f"Final cleaned name: {cleaned_name}")

    return cleaned_name