import os
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
        
        # If we reach here, neither direct download nor streaming is suitable
        # This should not happen with current logic, log an error
        print(f"Error: Unable to handle source path {source_path} - not a file and zipstream not suitable")
        update_download_request(download_request, 'failed', "Error: Unsupported source type")

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

        # If we reach here, neither direct download nor streaming is suitable
        # This should not happen with current logic, log an error
        print(f"Error: Unable to handle source path {source_path} - not a file and zipstream not suitable")
        update_download_request(download_request, 'failed', "Error: Unsupported source type")


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


