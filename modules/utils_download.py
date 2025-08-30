import os
import zipfile
from datetime import datetime
from typing import Tuple
from modules.utils_filename import sanitize_filename
from modules.models import DownloadRequest, GlobalSettings, db

def zip_game(download_request_id, app, zip_file_path):
    settings = GlobalSettings.query.first()
    with app.app_context():
        download_request = DownloadRequest.query.get(download_request_id)
        game = download_request.game

        if not game:
            print(f"No game found for DownloadRequest ID: {download_request_id}")
            return

        print(f"Processing game: {game.name}")
        
        zip_save_path = app.config['ZIP_SAVE_PATH']
        source_path = game.full_disk_path
        safe_name = sanitize_filename(os.path.basename(zip_file_path))
        zip_file_path = os.path.join(os.path.dirname(zip_file_path), safe_name)

        # Check if source path exists
        if not os.path.exists(source_path):
            print(f"Source path does not exist: {source_path}")
            update_download_request(download_request, 'failed', "Error: File Not Found")
            return

        # Check if source path is a file or directory
        if os.path.isfile(zip_file_path):
            print(f"Source is a file, providing direct link: {zip_file_path}")
            update_download_request(download_request, 'available', zip_file_path)
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
                    # Exclude the updates and extras folders
                    if settings.update_folder_name in dirs:
                        dirs.remove(settings.update_folder_name)
                    if settings.update_folder_name.lower() in dirs:
                        dirs.remove(settings.update_folder_name.lower())
                    if settings.update_folder_name.capitalize() in dirs:
                        dirs.remove(settings.update_folder_name.capitalize())
                    if settings.extras_folder_name in dirs:
                        dirs.remove(settings.extras_folder_name)
                    if settings.extras_folder_name.lower() in dirs:
                        dirs.remove(settings.extras_folder_name.lower())
                    if settings.extras_folder_name.capitalize() in dirs:
                        dirs.remove(settings.extras_folder_name.capitalize())
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
    download_request.completion_time = datetime.now(datetime.UTC)
    print(f"Download request updated: {download_request}")
    db.session.commit()    
     
def zip_folder(download_request_id, app, file_location, file_name):
    with app.app_context():
        download_request = DownloadRequest.query.get(download_request_id)
        game = download_request.game

        if not game:
            print(f"No game found for DownloadRequest ID: {download_request_id}")
            return

        print(f"Processing file for game: {game.name}")
        
        zip_save_path = app.config['ZIP_SAVE_PATH']
        source_path = file_location

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


        # Proceed to zip the folder
        try:           
            if not os.path.exists(zip_save_path):
                os.makedirs(zip_save_path)
                print(f"Created missing directory: {zip_save_path}")
                    
            safe_name = sanitize_filename(f"{file_name}.zip")
            zip_file_path = os.path.join(zip_save_path, safe_name)
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
