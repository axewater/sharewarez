import os
import zipfile
from datetime import datetime, timezone
from typing import Tuple
from modules.utils_filename import sanitize_filename
from modules.models import DownloadRequest, GlobalSettings, db
from modules.utils_security import is_safe_path, get_allowed_base_directories
from modules.utils_zipstream import should_use_zipstream, get_zipstream_info
from modules.async_streaming import get_zipstream_download_info
from sqlalchemy import select

def zip_game(download_request_id, app, zip_file_path):
    settings = db.session.execute(select(GlobalSettings)).scalars().first()
    with app.app_context():
        download_request = db.session.get(DownloadRequest, download_request_id)
        game = download_request.game

        if not game:
            print(f"No game found for DownloadRequest ID: {download_request_id}")
            return

        print(f"Processing game: {game.name}")
        
        # Validate game path is within allowed directories
        allowed_bases = get_allowed_base_directories(app)
        if not allowed_bases:
            print("Error: No allowed base directories configured")
            update_download_request(download_request, 'failed', "Error: Service configuration error")
            return
            
        source_path = game.full_disk_path
        is_safe, error_message = is_safe_path(source_path, allowed_bases)
        if not is_safe:
            print(f"Security error: Game path validation failed for {source_path}: {error_message}")
            update_download_request(download_request, 'failed', f"Error: {error_message}")
            return
        
        # Check if source path exists
        if not os.path.exists(source_path):
            print(f"Source path does not exist: {source_path}")
            update_download_request(download_request, 'failed', "Error: File Not Found")
            return

        # FIRST: Check if zip_file_path is pointing to an existing single file (before any path manipulation)
        if os.path.isfile(zip_file_path):
            print(f"Source is a single file, providing direct link: {zip_file_path}")
            update_download_request(download_request, 'available', zip_file_path)
            return
        
        # Check if we should use zipstream for multi-file games
        if should_use_zipstream(source_path):
            print(f"Using zipstream for multi-file game: {game.name}")
            safe_name = sanitize_filename(os.path.basename(zip_file_path))
            prepare_streaming_download(download_request, source_path, safe_name)
            return
        
        # Only proceed with traditional ZIP creation logic if it's not suitable for streaming
        zip_save_path = app.config['ZIP_SAVE_PATH']
        safe_name = sanitize_filename(os.path.basename(zip_file_path))
        zip_file_path = os.path.join(os.path.dirname(zip_file_path), safe_name)
        
        # Validate destination ZIP path is within the expected ZIP save directory (only when creating ZIP)
        abs_zip_path = os.path.abspath(os.path.realpath(zip_file_path))
        abs_zip_save_path = os.path.abspath(os.path.realpath(zip_save_path))
        if not abs_zip_path.startswith(abs_zip_save_path):
            print(f"Security error: ZIP destination path outside allowed directory: {zip_file_path}")
            update_download_request(download_request, 'failed', "Error: Invalid destination path")
            return
       
        # Proceed to zip the game
        try:
            if not os.path.exists(zip_save_path):
                os.makedirs(zip_save_path)
                print(f"Created missing directory: {zip_save_path}")
                
            update_download_request(download_request, 'processing', zip_file_path)
            print(f"Zipping game folder: {source_path} to {zip_file_path} with storage method.")
            
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_STORED) as zipf:
                for root, dirs, files in os.walk(source_path):
                    # Exclude the updates and extras folders (case-insensitive)
                    dirs_to_remove = []
                    for dir_name in dirs:
                        if dir_name.lower() == settings.update_folder_name.lower():
                            dirs_to_remove.append(dir_name)
                        elif dir_name.lower() == settings.extras_folder_name.lower():
                            dirs_to_remove.append(dir_name)
                    
                    # Remove the directories (done separately to avoid modifying list while iterating)
                    for dir_name in dirs_to_remove:
                        dirs.remove(dir_name)
                    
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Ensure .NFO, .SFV, and file_id.diz files are still included in the zip
                        zipf.write(file_path, os.path.relpath(file_path, source_path))
            print(f"Archive created at {zip_file_path}")
            update_download_request(download_request, 'available', zip_file_path)
            
        except Exception as e:
            error_message = str(e)
            print(f"An error occurred: {error_message}")
            update_download_request(download_request, 'failed', "Error: " + error_message)

def update_download_request(download_request, status, file_path, file_size=None):
    download_request.status = status
    download_request.zip_file_path = file_path
    if file_size:
        download_request.download_size = file_size
    download_request.completion_time = datetime.now(timezone.utc)
    print(f"Download request updated: {download_request}")
    db.session.commit()    
     
def zip_folder(download_request_id, app, file_location, file_name):
    with app.app_context():
        download_request = db.session.get(DownloadRequest, download_request_id)
        game = download_request.game

        if not game:
            print(f"No game found for DownloadRequest ID: {download_request_id}")
            return

        print(f"Processing file for game: {game.name}")
        
        # Validate file location is within allowed directories
        allowed_bases = get_allowed_base_directories(app)
        if not allowed_bases:
            print("Error: No allowed base directories configured")
            update_download_request(download_request, 'failed', "Error: Service configuration error")
            return
            
        source_path = file_location
        is_safe, error_message = is_safe_path(source_path, allowed_bases)
        if not is_safe:
            print(f"Security error: File location validation failed for {source_path}: {error_message}")
            update_download_request(download_request, 'failed', f"Error: {error_message}")
            return
        
        zip_save_path = app.config['ZIP_SAVE_PATH']

        # Check if source path exists
        if not os.path.exists(source_path):
            print(f"Source path does not exist: {source_path}")
            update_download_request(download_request, 'failed', "Error: File Not Found")
            return

        # Check if source path is a file or directory
        if os.path.isfile(source_path):
            print(f"Source is a file, providing direct link: {source_path}")
            update_download_request(download_request, 'available', source_path)
            return
        
        # Check if we should use zipstream for multi-file folders
        if should_use_zipstream(source_path):
            print(f"Using zipstream for folder: {file_name}")
            safe_name = sanitize_filename(f"{file_name}.zip")
            prepare_streaming_download(download_request, source_path, safe_name)
            return

        # Proceed to zip the folder with traditional method
        try:           
            if not os.path.exists(zip_save_path):
                os.makedirs(zip_save_path)
                print(f"Created missing directory: {zip_save_path}")
                    
            safe_name = sanitize_filename(f"{file_name}.zip")
            zip_file_path = os.path.join(zip_save_path, safe_name)
            
            # Validate destination ZIP path is within the expected ZIP save directory
            abs_zip_path = os.path.abspath(os.path.realpath(zip_file_path))
            abs_zip_save_path = os.path.abspath(os.path.realpath(zip_save_path))
            if not abs_zip_path.startswith(abs_zip_save_path):
                print(f"Security error: ZIP destination path outside allowed directory: {zip_file_path}")
                update_download_request(download_request, 'failed', "Error: Invalid destination path")
                return
                
            print(f"Zipping game folder: {source_path} to {zip_file_path} with storage method.")
            
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_STORED) as zipf:
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Ensure .NFO, .SFV, and file_id.diz files are still included in the zip
                        zipf.write(file_path, os.path.relpath(file_path, source_path))
                print(f"Archive created at {zip_file_path}")
                zip_file_size = os.path.getsize(zip_file_path)
                update_download_request(download_request, 'available', zip_file_path, zip_file_size)
            
        except Exception as e:
            error_message = str(e)
            print(f"An error occurred: {error_message}")
            update_download_request(download_request, 'failed', "Error: " + error_message)

def get_zip_storage_stats() -> Tuple[int, int, int]:
    """Calculate storage statistics for zip files.
    
    Returns:
        Tuple containing (total_zip_count, total_size_bytes, zip_folder_size_bytes)
    """
    from flask import current_app
    
    zip_save_path = current_app.config['ZIP_SAVE_PATH']
    if not os.path.exists(zip_save_path):
        return 0, 0, 0
        
    total_zip_count = 0
    zip_folder_size_bytes = 0
    for file in os.listdir(zip_save_path):
        if file.lower().endswith('.zip'):
            total_zip_count += 1
            zip_folder_size_bytes += os.path.getsize(os.path.join(zip_save_path, file))
            
    return total_zip_count, zip_folder_size_bytes, zip_folder_size_bytes


def delete_zip_file_safely(zip_file_path: str, zip_save_path: str) -> Tuple[bool, str]:
    """
    Safely delete a ZIP file if it exists and is within the expected directory.
    
    Args:
        zip_file_path: Path to the ZIP file to delete
        zip_save_path: Expected base directory for ZIP files
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not zip_file_path or not os.path.exists(zip_file_path):
        return True, "No ZIP file to delete"
        
    # Resolve paths to handle symbolic links and relative paths
    abs_zip_path = os.path.abspath(os.path.realpath(zip_file_path))
    abs_zip_save_path = os.path.abspath(os.path.realpath(zip_save_path))
    
    # Security check: ensure file is within expected directory
    if not abs_zip_path.startswith(abs_zip_save_path):
        return False, "ZIP file is not in the expected directory"
        
    try:
        os.remove(abs_zip_path)
        return True, f"ZIP file deleted successfully: {zip_file_path}"
    except OSError as e:
        return False, f"Error deleting ZIP file: {str(e)}"


def prepare_streaming_download(download_request, source_path, filename):
    """
    Set up streaming metadata for zipstream downloads.
    
    Args:
        download_request: DownloadRequest object to update
        source_path: Path to the source files to stream
        filename: Filename for the download
    """
    try:
        # Generate streaming metadata
        stream_info = get_zipstream_info(source_path, filename)
        
        # Update download request with streaming status
        download_request.status = 'available'
        download_request.zip_file_path = source_path  # Store source path for streaming
        download_request.completion_time = datetime.now(timezone.utc)
        
        print(f"Download request prepared for streaming: {download_request}")
        db.session.commit()
        
    except Exception as e:
        error_message = str(e)
        print(f"Error preparing streaming download: {error_message}")
        update_download_request(download_request, 'failed', f"Error: {error_message}")


