import os
from flask import flash
import re


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
    print(f"Files found in folder: {file_contents}")
    game_names_with_paths = []
    for file_name in file_contents:
        print(f"Checking file: {file_name}")
        extension = file_name.split('.')[-1].lower()
        if extension in extensions:
            print(f"Found supported file: {file_name}")
            # Extract the game name without the extension
            game_name_without_extension = '.'.join(file_name.split('.')[:-1])
            # Clean the game name
            cleaned_game_name = clean_game_name(game_name_without_extension, insensitive_patterns, sensitive_patterns)
            print(f"Extracted and cleaned game name: {cleaned_game_name}")
            full_path = os.path.join(folder_path, file_name)
            
            game_names_with_paths.append({'name': cleaned_game_name, 'full_path': full_path, 'file_type': extension})
            print(f"Added cleaned game name with path: {cleaned_game_name} at {full_path}")

    print(f"Game names with paths extracted from files: {game_names_with_paths}")
    return game_names_with_paths


    
    
    
def clean_game_name(filename, insensitive_patterns, sensitive_patterns):
    print(f"Original filename: {filename}")
    
    # Check and remove 'setup' at the start, case-insensitive
    if filename.lower().startswith('setup'):
        filename = filename[len('setup'):].lstrip("_").lstrip("-").lstrip()
        print(f"After removing 'setup': {filename}")

    # First handle version numbers and known patterns that should be removed
    filename = re.sub(r'v\d+(\.\d+)*', '', filename)  # Remove version numbers like v1.0.3
    filename = re.sub(r'\b\d+(\.\d+)+\b', '', filename)  # Remove standalone version numbers like 1.0.3
    
    # Handle dots between single letters (like A.Tale -> A Tale)
    filename = re.sub(r'(?<=\b[A-Z])\.(?=[A-Z]\b|\s|$)', ' ', filename)
    
    # Replace remaining dots and underscores with spaces, but preserve dots in known patterns
    filename = re.sub(r'(?<!^)(?<![\d])\.|_', ' ', filename)

    # Define a regex pattern for version numbers
    version_pattern = r'\bv?\d+(\.\d+){1,3}'

    # Remove version numbers
    filename = re.sub(version_pattern, '', filename)

    # Remove known release group patterns
    for pattern in insensitive_patterns:
        escaped_pattern = re.escape(pattern)
        filename = re.sub(f"\\b{escaped_pattern}\\b", '', filename, flags=re.IGNORECASE)

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

    # Normalize whitespace and re-title
    filename = re.sub(r'\s+', ' ', filename).strip()
    cleaned_name = ' '.join(filename.split()).title()
    print(f"Final cleaned name: {cleaned_name}")

    return cleaned_name