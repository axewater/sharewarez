import os
from flask import redirect, url_for, flash, current_app, copy_current_request_context, abort
from flask_login import login_required, current_user
from threading import Thread
from uuid import uuid4
import re
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from modules.models import Game, DownloadRequest, GameUpdate, GameExtra, GlobalSettings
from modules.utils_download import zip_game, zip_folder, update_download_request
from modules.utils_game_core import get_game_by_uuid
from modules.utils_functions import get_folder_size_in_bytes
from modules.utils_security import is_safe_path, get_allowed_base_directories
from modules.utils_filename import sanitize_filename
from modules import db
from modules.utils_logging import log_system_event
from . import download_bp

@download_bp.route('/download_game/<game_uuid>', methods=['GET'])
@login_required
def download_game(game_uuid):
    # Validate UUID format
    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', game_uuid, re.IGNORECASE):
        log_system_event(f"Invalid game UUID format attempted: {game_uuid[:50]}", event_type='security', event_level='warning')
        abort(400)
    
    game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalars().first() or abort(404)
    log_system_event(f"User initiated download for game: {game.name}", event_type='game', event_level='information')

    # Validate game path is within allowed directories
    allowed_bases = get_allowed_base_directories(current_app)
    if not allowed_bases:
        log_system_event("No allowed base directories configured", event_type='system', event_level='error')
        flash("System configuration error. Please contact administrator.", "error")
        return redirect(url_for('download.downloads'))
        
    is_safe, error_message = is_safe_path(game.full_disk_path, allowed_bases)
    if not is_safe:
        log_system_event(f"Path validation failed for game {game_uuid}: {error_message}", event_type='security', event_level='warning')
        flash("Access denied.", "error")
        return redirect(url_for('download.downloads'))

    # Check for any existing download request for the same game by the current user
    existing_request = db.session.execute(select(DownloadRequest).filter_by(user_id=current_user.id, file_location=game.full_disk_path)).scalars().first()
    
    if existing_request:
        flash("You already have a download request for this game in your basket. Please check your downloads page.", "info")
        return redirect(url_for('download.downloads'))
    
    try:
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
                sanitized_name = sanitize_filename(f"{game.name}.zip")
                zip_file_path = os.path.join(zip_save_path, sanitized_name)
            else:
                zip_file_path = os.path.join(game.full_disk_path, significant_files[0])
        else:
            zip_file_path = game.full_disk_path
            
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
        
        # Start the download process in a thread - zip_game() handles all security validation
        @copy_current_request_context
        def thread_function():
            log_system_event(f"Starting zip process for download request {new_request.id}", event_type='game', event_level='information')
            zip_game(new_request.id, current_app._get_current_object(), zip_file_path)

        thread = Thread(target=thread_function, daemon=True)
        thread.start()

        return redirect(url_for('download.downloads'))
        
    except Exception as e:
        db.session.rollback()
        log_system_event(f"Error creating download request for game {game_uuid}: {str(e)}", event_type='game', event_level='error')
        flash("An error occurred processing your request.", "error")
        return redirect(url_for('download.downloads'))

@download_bp.route('/download_other/<file_type>/<game_uuid>/<file_id>', methods=['GET'])
@login_required
def download_other(file_type, game_uuid, file_id):
    """Handle downloads for update and extra files"""
    
    # Validate inputs
    if file_type not in ['update', 'extra']:
        log_system_event(f"Invalid file type attempted: {file_type}", event_type='security', event_level='warning')
        flash("Invalid file type", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))
    
    # Validate UUID format
    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', game_uuid, re.IGNORECASE):
        log_system_event(f"Invalid game UUID format attempted: {game_uuid[:50]}", event_type='security', event_level='warning')
        abort(400)
    
    # Validate file_id is numeric
    try:
        file_id = int(file_id)
    except ValueError:
        log_system_event(f"Invalid file ID attempted: {file_id}", event_type='security', event_level='warning')
        abort(400)

    FileModel = GameUpdate if file_type == 'update' else GameExtra
    file_record = db.session.execute(select(FileModel).filter_by(id=file_id, game_uuid=game_uuid)).scalars().first()
    
    if not file_record:
        log_system_event(f"Failed to download {file_type} - file not found: {game_uuid}/{file_id}", event_type='game', event_level='error')
        flash(f"{file_type.capitalize()} file not found", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))

    # Validate file path is within allowed directories
    allowed_bases = get_allowed_base_directories(current_app)
    if not allowed_bases:
        log_system_event("No allowed base directories configured", event_type='system', event_level='error')
        flash("System configuration error. Please contact administrator.", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))
        
    is_safe, error_message = is_safe_path(file_record.file_path, allowed_bases)
    if not is_safe:
        log_system_event(f"Path validation failed for {file_type} {file_id}: {error_message}", event_type='security', event_level='warning')
        flash("Access denied.", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))

    # Check if the file or folder exists
    if not os.path.exists(file_record.file_path):
        log_system_event(f"{file_type.capitalize()} file not found on disk: {file_record.file_path}", event_type='system', event_level='error')
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
        # Create sanitized filename for ZIP
        base_name = os.path.basename(file_record.file_path)
        sanitized_name = sanitize_filename(f"{uuid4()}_{base_name}.zip")
        zip_file_path = os.path.join(current_app.config['ZIP_SAVE_PATH'], sanitized_name)
        
        # Determine status based on file type
        if os.path.isfile(file_record.file_path) and file_record.file_path.lower().endswith('.zip'):
            zip_file_path = file_record.file_path
            status = 'available'
        else:
            status = 'processing'
            
        # Create download request
        new_request = DownloadRequest(
            user_id=current_user.id,
            game_uuid=game_uuid,
            status=status,
            download_size=0,  # Will be set by zip_folder()
            file_location=file_record.file_path,
            zip_file_path=zip_file_path
        )
        
        db.session.add(new_request)
        file_record.times_downloaded += 1
        db.session.commit()

        log_system_event(f"Download request created for {file_type}: {base_name}", event_type='game', event_level='information')
        
        # Use the secure zip_folder function instead of inline zipping
        if status == 'processing':
            @copy_current_request_context
            def thread_function():
                log_system_event(f"Starting zip process for {file_type} download request {new_request.id}", event_type='game', event_level='information')
                zip_folder(new_request.id, current_app._get_current_object(), file_record.file_path, base_name)

            thread = Thread(target=thread_function, daemon=True)
            thread.start()

        return redirect(url_for('download.downloads'))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        log_system_event(f"Database error creating {file_type} download request: {str(e)}", event_type='system', event_level='error')
        flash("Database error occurred", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))
    except Exception as e:
        db.session.rollback()
        log_system_event(f"Error creating {file_type} download request: {str(e)}", event_type='system', event_level='error')
        flash("An error occurred processing your request.", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))


