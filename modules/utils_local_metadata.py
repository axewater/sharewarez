"""
Local filesystem metadata persistence utilities.
Implements Jellyfin-style metadata files for IGDB ID persistence.
"""
import os
import json
import logging
from datetime import datetime, timezone
from flask import current_app
from modules.utils_security import is_safe_path, get_allowed_base_directories
from modules.utils_functions import sanitize_string_input

logger = logging.getLogger(__name__)


def read_local_metadata(full_disk_path, filename='sharewarez.json'):
    """
    Read local metadata file from game folder.

    Args:
        full_disk_path: Full path to game folder
        filename: Metadata filename (default: sharewarez.json)

    Returns:
        dict or None: Metadata dict with keys like 'igdb_id', or None if not found/error

    Example return:
    {
        "igdb_id": 7331,
        "title": "DOOM",
        "identified_at": "2025-11-04T10:30:00Z",
        "manually_verified": true,
        "version": "1.0"
    }
    """
    try:
        # Security check
        if current_app:
            allowed_bases = get_allowed_base_directories(current_app)
            if not allowed_bases:
                logger.warning(f"No allowed base directories configured for {full_disk_path}")
                return None

            is_safe, error_message = is_safe_path(full_disk_path, allowed_bases)
            if not is_safe:
                logger.warning(f"Security: Unsafe path {full_disk_path}: {error_message}")
                return None

        # Check if path exists and is directory
        if not os.path.exists(full_disk_path):
            return None
        if not os.path.isdir(full_disk_path):
            logger.debug(f"Path is not a directory: {full_disk_path}")
            return None

        # Build metadata file path
        metadata_path = os.path.join(full_disk_path, filename)

        if not os.path.exists(metadata_path):
            return None

        # Read and parse JSON
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        # Validate required fields
        if not isinstance(metadata, dict):
            logger.warning(f"Invalid metadata format in {metadata_path}: not a dict")
            return None

        if 'igdb_id' not in metadata:
            logger.warning(f"Invalid metadata in {metadata_path}: missing igdb_id")
            return None

        logger.info(f"✅ Found local metadata: IGDB ID {metadata['igdb_id']} in {metadata_path}")
        return metadata

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON in {metadata_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading local metadata from {full_disk_path}: {e}")
        return None


def write_local_metadata(full_disk_path, igdb_id, game_title=None, manually_verified=False,
                         filename='sharewarez.json'):
    """
    Write local metadata file to game folder.

    Args:
        full_disk_path: Full path to game folder
        igdb_id: IGDB ID number
        game_title: Game title (optional, for human readability)
        manually_verified: Whether this was manually identified by admin
        filename: Metadata filename (default: sharewarez.json)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"💾 [LOCAL METADATA] Starting write process for IGDB ID {igdb_id}")
        logger.info(f"💾 [LOCAL METADATA] Target path: {full_disk_path}")
        logger.info(f"💾 [LOCAL METADATA] Filename: {filename}")

        # Security check
        if current_app:
            allowed_bases = get_allowed_base_directories(current_app)
            if not allowed_bases:
                logger.error(f"🚫 [LOCAL METADATA] No allowed base directories configured for {full_disk_path}")
                return False

            is_safe, error_message = is_safe_path(full_disk_path, allowed_bases)
            if not is_safe:
                logger.error(f"🚫 [LOCAL METADATA] Security: Cannot write to unsafe path {full_disk_path}: {error_message}")
                return False
            logger.info(f"✅ [LOCAL METADATA] Security check passed")

        # Check if path exists and is directory
        if not os.path.exists(full_disk_path):
            logger.error(f"🚫 [LOCAL METADATA] Path does not exist: {full_disk_path}")
            return False
        if not os.path.isdir(full_disk_path):
            logger.error(f"🚫 [LOCAL METADATA] Path is not a directory: {full_disk_path}")
            return False
        logger.info(f"✅ [LOCAL METADATA] Path exists and is a directory")

        # Build metadata object
        metadata = {
            "igdb_id": int(igdb_id),
            "identified_at": datetime.now(timezone.utc).isoformat(),
            "manually_verified": bool(manually_verified),
            "version": "1.0"
        }

        # Add optional fields
        if game_title:
            metadata["title"] = sanitize_string_input(game_title, 255)
            logger.info(f"💾 [LOCAL METADATA] Game title: {game_title}")

        # Write to file
        metadata_path = os.path.join(full_disk_path, filename)
        logger.info(f"💾 [LOCAL METADATA] Full metadata path: {metadata_path}")

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Verify the file was created
        if os.path.exists(metadata_path):
            file_size = os.path.getsize(metadata_path)
            logger.info(f"✅✅✅ [LOCAL METADATA] SUCCESS! File written to: {metadata_path}")
            logger.info(f"✅ [LOCAL METADATA] File size: {file_size} bytes")
            logger.info(f"✅ [LOCAL METADATA] IGDB ID {igdb_id} saved for game: {game_title or 'Unknown'}")
        else:
            logger.error(f"🚫 [LOCAL METADATA] File was not created at: {metadata_path}")
            return False

        return True

    except PermissionError as e:
        logger.error(f"🚫 [LOCAL METADATA] Permission denied writing to {full_disk_path}: {e}")
        return False
    except Exception as e:
        logger.error(f"🚫 [LOCAL METADATA] Error writing local metadata to {full_disk_path}: {e}")
        return False


def has_local_metadata(full_disk_path, filename='sharewarez.json'):
    """
    Quick check if local metadata file exists.

    Args:
        full_disk_path: Full path to game folder
        filename: Metadata filename

    Returns:
        bool: True if metadata file exists
    """
    try:
        if not os.path.isdir(full_disk_path):
            return False
        metadata_path = os.path.join(full_disk_path, filename)
        return os.path.exists(metadata_path)
    except:
        return False


def delete_local_metadata(full_disk_path, filename='sharewarez.json'):
    """
    Delete local metadata file from game folder.

    Args:
        full_disk_path: Full path to game folder
        filename: Metadata filename

    Returns:
        bool: True if deleted or didn't exist, False on error
    """
    try:
        metadata_path = os.path.join(full_disk_path, filename)
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
            logger.info(f"Deleted local metadata: {metadata_path}")
        return True
    except Exception as e:
        logger.error(f"Error deleting local metadata from {full_disk_path}: {e}")
        return False


def get_local_cover_path(full_disk_path):
    """
    Get path to local cover image if it exists.

    Checks for (in priority order):
    1. cover.jpg
    2. cover.png
    3. folder.jpg
    4. folder.png

    Args:
        full_disk_path: Full path to game folder

    Returns:
        str or None: Absolute path to cover image, or None if not found
    """
    try:
        if not os.path.isdir(full_disk_path):
            return None

        # Check each filename in priority order
        cover_filenames = ['cover.jpg', 'cover.png', 'folder.jpg', 'folder.png']

        for filename in cover_filenames:
            cover_path = os.path.join(full_disk_path, filename)
            if os.path.exists(cover_path) and os.path.isfile(cover_path):
                logger.info(f"📷 Found local cover: {cover_path}")
                return cover_path

        return None

    except Exception as e:
        logger.error(f"Error checking for local cover in {full_disk_path}: {e}")
        return None


def get_local_screenshots(full_disk_path):
    """
    Get paths to local screenshot images.

    Looks for files matching pattern:
    - screenshot-1.jpg, screenshot-2.jpg, etc.
    - screenshot-1.png, screenshot-2.png, etc.

    Args:
        full_disk_path: Full path to game folder

    Returns:
        list: List of absolute paths to screenshot images (sorted by number)
    """
    try:
        if not os.path.isdir(full_disk_path):
            return []

        screenshots = []

        # Check for numbered screenshots (screenshot-1.jpg through screenshot-99.jpg)
        for i in range(1, 100):
            for ext in ['.jpg', '.png']:
                filename = f'screenshot-{i}{ext}'
                screenshot_path = os.path.join(full_disk_path, filename)
                if os.path.exists(screenshot_path) and os.path.isfile(screenshot_path):
                    screenshots.append(screenshot_path)
                    break  # Found jpg or png, don't check other extension

        if screenshots:
            logger.info(f"📷 Found {len(screenshots)} local screenshots in {full_disk_path}")

        return screenshots

    except Exception as e:
        logger.error(f"Error checking for local screenshots in {full_disk_path}: {e}")
        return []


def has_local_images(full_disk_path):
    """
    Quick check if folder has any local images (cover or screenshots).

    Args:
        full_disk_path: Full path to game folder

    Returns:
        bool: True if local cover or screenshots exist
    """
    return (get_local_cover_path(full_disk_path) is not None or
            len(get_local_screenshots(full_disk_path)) > 0)


def check_write_permissions(directory_path, test_filename='_sharewarez_write_test.tmp'):
    """
    Check if we have write permissions to a directory by attempting to create a test file.

    Args:
        directory_path: Path to directory to check
        test_filename: Name of temporary test file

    Returns:
        tuple: (bool, str) - (success, error_message)
            - (True, "") if write permissions are OK
            - (False, "error message") if write fails
    """
    try:
        # Check if directory exists
        if not os.path.exists(directory_path):
            return False, f"Directory does not exist: {directory_path}"

        if not os.path.isdir(directory_path):
            return False, f"Path is not a directory: {directory_path}"

        # Attempt to create a test file
        test_file_path = os.path.join(directory_path, test_filename)

        try:
            with open(test_file_path, 'w') as f:
                f.write('test')

            # Clean up test file
            if os.path.exists(test_file_path):
                os.remove(test_file_path)

            logger.info(f"✅ [PERMISSIONS] Write permission check passed for: {directory_path}")
            return True, ""

        except PermissionError as e:
            error_msg = f"Permission denied: Cannot write to {directory_path}"
            logger.error(f"🚫 [PERMISSIONS] {error_msg}: {e}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Write test failed for {directory_path}: {str(e)}"
            logger.error(f"🚫 [PERMISSIONS] {error_msg}")
            return False, error_msg

    except Exception as e:
        error_msg = f"Permission check failed: {str(e)}"
        logger.error(f"🚫 [PERMISSIONS] {error_msg}")
        return False, error_msg


def check_library_write_permissions(library_path):
    """
    Check write permissions for a library by testing the root directory
    and optionally some subdirectories.

    Args:
        library_path: Root path of the library to scan

    Returns:
        tuple: (bool, list) - (all_ok, failed_paths)
            - all_ok: True if all checks passed
            - failed_paths: List of paths that failed with error messages
    """
    failed_paths = []

    # Check root directory
    success, error = check_write_permissions(library_path)
    if not success:
        failed_paths.append({
            'path': library_path,
            'error': error
        })

    # Try to check a few subdirectories (first level only)
    try:
        if os.path.isdir(library_path):
            subdirs = [d for d in os.listdir(library_path)
                      if os.path.isdir(os.path.join(library_path, d))]

            # Test up to 3 subdirectories as a sample
            for subdir in subdirs[:3]:
                subdir_path = os.path.join(library_path, subdir)
                success, error = check_write_permissions(subdir_path)
                if not success:
                    failed_paths.append({
                        'path': subdir_path,
                        'error': error
                    })
    except Exception as e:
        logger.warning(f"⚠️ [PERMISSIONS] Could not check subdirectories: {e}")

    return len(failed_paths) == 0, failed_paths
