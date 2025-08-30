import os
from flask import redirect, url_for, flash, current_app, copy_current_request_context, abort
from flask_login import login_required, current_user
from threading import Thread
from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from modules.models import Game, DownloadRequest, GameUpdate, GameExtra, GlobalSettings
from modules.utils_download import zip_game, zip_folder, update_download_request
from modules.utils_game_core import get_game_by_uuid
from modules.utils_functions import get_folder_size_in_bytes
from modules import db
from modules.utils_logging import log_system_event
from . import download_bp

@download_bp.route('/download_game/<game_uuid>', methods=['GET'])
@login_required
def download_game(game_uuid):
    print(f"Downloading game with UUID: {game_uuid}")
    game = db.session.get(Game, game_uuid) or abort(404)
    print(f"Game found: {game}")

    log_system_event(f"User initiated download for game: {game.name}", event_type='game', event_level='information')
    # Check for any existing download request for the same game by the current user, regardless of status
    existing_request = db.session.execute(select(DownloadRequest).filter_by(user_id=current_user.id, file_location=game.full_disk_path)).scalars().first()
    
    if existing_request:
        flash("You already have a download request for this game in your basket. Please check your downloads page.", "info")
        return redirect(url_for('download.downloads'))
    
    if os.path.isdir(game.full_disk_path):
        settings = db.session.execute(select(GlobalSettings)).scalars().first()
        files_in_directory = []
        for f in os.listdir(game.full_disk_path):
            full_path = os.path.join(game.full_disk_path, f)
            # Skip updates and extras folders
            if os.path.isdir(full_path) and (
                f.lower() == settings.update_folder_name.lower() or 
                f.lower() == settings.extras_folder_name.lower()):
                continue
            if os.path.isfile(full_path):
                files_in_directory.append(f)
        # Filter out .nfo, .sfv files after excluding special folders
        significant_files = [f for f in files_in_directory if not f.lower().endswith(('.nfo', '.sfv')) and not f.lower() == 'file_id.diz']

        # If more than one significant file remains, create a zip file
        if len(significant_files) > 1:
            zip_save_path = current_app.config['ZIP_SAVE_PATH']
            zip_file_path = os.path.join(zip_save_path, f"{game.name}.zip")
        else:
            zip_file_path = os.path.join(game.full_disk_path, significant_files[0])
    else:
        zip_file_path = game.full_disk_path
        
    print(f"Creating a new download request for user {current_user.id} for game {game_uuid}")
    new_request = DownloadRequest(
        user_id=current_user.id,
        game_uuid=game.uuid,
        status='processing',  
        download_size=game.size,
        file_location=game.full_disk_path,
        zip_file_path=zip_file_path
    )
    db.session.add(new_request)
    game.times_downloaded += 1
    db.session.commit()

    log_system_event(f"Download request created for game: {game.name}", event_type='game', event_level='information')
    # Start the download process (potentially in a new thread as before)
    @copy_current_request_context
    def thread_function():
        print(f"Thread function started for download request {new_request.id}")
        zip_game(new_request.id, current_app._get_current_object(), zip_file_path)

    thread = Thread(target=thread_function)
    thread.start()

    flash("Your download request is being processed. You will be notified when the download is ready.", "info")
    return redirect(url_for('download.downloads'))

@download_bp.route('/download_other/<file_type>/<game_uuid>/<file_id>', methods=['GET'])
@login_required
def download_other(file_type, game_uuid, file_id):
    """Handle downloads for update and extra files"""
    
    # Validate file_type
    if file_type not in ['update', 'extra']:
        flash("Invalid file type", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))

    FileModel = GameUpdate if file_type == 'update' else GameExtra
    # Fetch the file record
    file_record = db.session.execute(select(FileModel).filter_by(id=file_id, game_uuid=game_uuid)).scalars().first()
    
    if not file_record:
        flash(f"{file_type.capitalize()} file not found", "error")
        log_system_event(f"Failed to download {file_type} - file not found: {game_uuid}", event_type='game', event_level='error')
        return redirect(url_for('games.game_details', game_uuid=game_uuid))

    # Check if the file or folder exists
    if not os.path.exists(file_record.file_path):
        flash("File not found on disk", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))

    # Check for an existing download request
    existing_request = db.session.execute(select(DownloadRequest).filter_by(
        user_id=current_user.id,
        file_location=file_record.file_path
    )).scalars().first()
    if existing_request:
        flash("You already have a download request for this file", "info")
        return redirect(url_for('download.downloads'))
    try:
        # Determine if the path is a file or a directory
        if os.path.isfile(file_record.file_path):
            # If it's already a zip file, set it as available
            if file_record.file_path.lower().endswith('.zip'):
                zip_file_path = file_record.file_path
                status = 'available'
            else:
                # For single files that aren't zips, create a zip
                zip_file_path = os.path.join(current_app.config['ZIP_SAVE_PATH'], f"{uuid4()}_{os.path.basename(file_record.file_path)}.zip")
                status = 'processing'
        else:
            # It's a directory; create a zip
            zip_file_path = os.path.join(current_app.config['ZIP_SAVE_PATH'], f"{uuid4()}_{os.path.basename(file_record.file_path)}.zip")
            status = 'processing'
        # Create a new download request
        new_request = DownloadRequest(
            user_id=current_user.id,
            game_uuid=game_uuid,
            status=status,
            download_size=0,  # Will be set after zipping
            file_location=file_record.file_path,
            zip_file_path=zip_file_path
        )
        
        db.session.add(new_request)
        file_record.times_downloaded += 1
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        flash("Database error occurred", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))

    # Start the download process in a background thread
    @copy_current_request_context
    def process_download():
        try:
            import zipfile
            if os.path.isfile(file_record.file_path):
                if file_record.file_path.lower().endswith('.zip'):
                    # Directly mark as available
                    update_download_request(new_request, 'available', file_record.file_path)
                else:
                    # Zip the single file
                    with zipfile.ZipFile(zip_file_path, 'w') as zipf:
                        zipf.write(file_record.file_path, arcname=os.path.basename(file_record.file_path))
                    new_request.download_size = os.path.getsize(zip_file_path)
                    update_download_request(new_request, 'available', zip_file_path)
            else:
                # Zip the entire directory
                with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(file_record.file_path):
                        for file in files:
                            abs_file_path = os.path.join(root, file)
                            relative_path = os.path.relpath(abs_file_path, os.path.dirname(file_record.file_path))
                            zipf.write(abs_file_path, arcname=relative_path)
                new_request.download_size = os.path.getsize(zip_file_path)
                update_download_request(new_request, 'available', zip_file_path)
        except Exception as e:
            with current_app.app_context():
                update_download_request(new_request, 'failed', str(e))
            print(f"Error during download processing: {e}")

    thread = Thread(target=process_download)
    thread.start()

    flash("Your download request is being processed. You will be notified when it's ready.", "info")
    return redirect(url_for('download.downloads'))


@download_bp.route('/download_file/<file_location>/<file_size>/<game_uuid>/<file_name>', methods=['GET'])
@login_required
def download_file(file_location, file_size, game_uuid, file_name):
    settings = db.session.execute(select(GlobalSettings)).scalars().first()
    game = get_game_by_uuid(game_uuid)
    
    if file_location == "updates":
        # Query the update record directly
        update = db.session.execute(select(GameUpdate).filter_by(game_uuid=game_uuid, file_path=file_name)).scalars().first()
        if update:
            file_location = update.file_path
        else:
            print(f"Update file not found for game {game_uuid}")
            flash("Update file not found", "error")
            return redirect(url_for('games.game_details', game_uuid=game_uuid))
    elif file_location == "extras":
        # Query the extra record directly
        extra = db.session.execute(select(GameExtra).filter_by(game_uuid=game_uuid, file_path=file_name)).scalars().first()
        if extra:
            file_location = extra.file_path
        else:
            print(f"Extra file not found for game {game_uuid}")
            flash("Extra file not found", "error")
            return redirect(url_for('games.game_details', game_uuid=game_uuid))
    else:
        print(f"Error - No location: {file_location}")
        return
    
    print(f"Downloading file with location: {file_location}")
    if os.path.isfile(file_location):
        file_size_stripped = ''.join(filter(str.isdigit, file_size))
        file_size_bytes = int(file_size_stripped)*10000
        zip_file_path = file_location
    else:
        file_size_bytes = get_folder_size_in_bytes(file_location)
        zip_save_path = current_app.config['ZIP_SAVE_PATH']
        zip_file_path = os.path.join(zip_save_path, f"{file_name}.zip")
        
    # Check for any existing download request for the same file by the current user, regardless of status
    existing_request = db.session.execute(select(DownloadRequest).filter_by(user_id=current_user.id, file_location=file_location)).scalars().first()
    
    if existing_request:
        flash("You already have a download request for this file in your basket. Please check your downloads page.", "info")
        return redirect(url_for('download.downloads'))

    print(f"Creating a new download request for user {current_user.id} for file {file_location}")
    new_request = DownloadRequest(
        user_id=current_user.id,
        zip_file_path=zip_file_path,
        status='processing',  
        download_size=file_size_bytes,
        game_uuid=game_uuid,
        file_location=file_location
    )
    db.session.add(new_request)
    db.session.commit()

    # Start the download process (potentially in a new thread as before)
    @copy_current_request_context
    def thread_function():
        print(f"Thread function started for download request {new_request.id}")
        zip_folder(new_request.id, current_app._get_current_object(), file_location, file_name)

    thread = Thread(target=thread_function)
    thread.start()
    
    flash("Your download request is being processed. You will be notified when the download is ready.", "info")
    return redirect(url_for('download.downloads'))
