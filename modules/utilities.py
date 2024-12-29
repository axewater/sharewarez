#/modules/utilities.py
import os
from datetime import datetime
from threading import Thread
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from flask import current_app, flash, redirect, url_for, session, copy_current_request_context
from modules.utils_functions import (
    load_release_group_patterns,
)
from modules.models import (
    Game, Library, AllowedFileType, ScanJob, GlobalSettings
)
from modules import db
from modules.utils_game_core import remove_from_lib
from modules.utils_gamenames import get_game_names_from_folder, get_game_names_from_files
from modules.utils_scanning import process_game_with_fallback, process_game_updates, process_game_extras



def scan_and_add_games(folder_path, scan_mode='folders', library_uuid=None, remove_missing=False):
    settings = GlobalSettings.query.first()
    update_folder_name = settings.update_folder_name if settings else 'updates'
    extras_folder_name = settings.extras_folder_name if settings else 'extras'
    
    # First, find the library and its platform
    library = Library.query.filter_by(uuid=library_uuid).first()
    if not library:
        print(f"Library with UUID {library_uuid} not found.")
        return

    # Get allowed file types from database
    allowed_extensions = [ext.value.lower() for ext in AllowedFileType.query.all()]
    if not allowed_extensions:
        print("No allowed file types found in database. Please configure them in the admin panel.")
        return

    print(f"Starting auto scan for games in folder: {folder_path} with scan mode: {scan_mode} and library UUID: {library_uuid} for platform: {library.platform.name}")
    
    # If remove_missing is enabled, check for games that no longer exist
    if remove_missing:
        print("Checking for missing games...")
        games_in_library = Game.query.filter_by(library_uuid=library_uuid).all()
        for game in games_in_library:
            if not os.path.exists(game.full_disk_path):
                print(f"Game no longer found at path: {game.full_disk_path}")
                try:
                    remove_from_lib(game.uuid)
                    print(f"Removed game {game.name} as it no longer exists at {game.full_disk_path}")
                except Exception as e:
                    print(f"Error removing game {game.name}: {e}")

    # Create initial scan job
    scan_job_entry = ScanJob(
        folders={folder_path: True},
        content_type='Games',
        status='Running',
        is_enabled=True,
        last_run=datetime.now(),
        library_uuid=library_uuid,
        error_message='',
        total_folders=0,
        folders_success=0,
        folders_failed=0
    )
    
    db.session.add(scan_job_entry)
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        print(f"Database error when adding ScanJob: {str(e)}")
        return  # cannot proceed without ScanJob

    # Check access perm
    if not os.path.exists(folder_path) or not os.access(folder_path, os.R_OK):
        error_message = f"Cannot access folder at path {folder_path}. Check permissions."
        print(error_message)
        scan_job_entry.status = 'Failed'
        scan_job_entry.error_message = error_message
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            print(f"Database error when updating ScanJob with error: {str(e)}")
        return

    # Load patterns before they are used
    insensitive_patterns, sensitive_patterns = load_release_group_patterns()

    try:
        # Use database-stored allowed extensions
        if scan_mode == 'folders':
            game_names_with_paths = get_game_names_from_folder(folder_path, insensitive_patterns, sensitive_patterns)
        elif scan_mode == 'files':
            game_names_with_paths = get_game_names_from_files(folder_path, allowed_extensions, insensitive_patterns, sensitive_patterns)

        scan_job_entry.total_folders = len(game_names_with_paths)
        db.session.commit()
        if not game_names_with_paths:
            print(f"No games found in folder: {folder_path}")
            scan_job_entry.status = 'Completed'
            scan_job_entry.error_message = "No games found."
            db.session.commit()
            return
    except Exception as e:
        scan_job_entry.status = 'Failed'
        scan_job_entry.error_message = str(e)
        db.session.commit()
        print(f"Error during pattern loading or game name extraction: {str(e)}")
        return

    for game_info in game_names_with_paths:
        db.session.refresh(scan_job_entry)  # Check if the job is still enabled
        if not scan_job_entry.is_enabled:
            scan_job_entry.status = 'Failed'
            scan_job_entry.error_message = 'Scan cancelled by the captain'
            db.session.commit()
            return  # Stop processing if cancelled
        
        game_name = game_info['name']
        full_disk_path = game_info['full_path']
        
        try:
            success = process_game_with_fallback(game_name, full_disk_path, scan_job_entry.id, library_uuid)
            if success:
                scan_job_entry.folders_success += 1
                # Get settings from database
                settings = GlobalSettings.query.first()
                update_folder_name = settings.update_folder_name if settings else 'updates'  # Default fallback
                extras_folder_name = settings.extras_folder_name if settings else 'extras'  # Default fallback
                
                # Check for updates folder using the database setting
                updates_folder = os.path.join(full_disk_path, update_folder_name)
                print(f"Checking for updates folder: {updates_folder}")
                if os.path.exists(updates_folder) and os.path.isdir(updates_folder):
                    print(f"Updates folder found for game: {game_name}")
                    process_game_updates(game_name, full_disk_path, updates_folder, library_uuid)
                else:
                    print(f"No updates folder found for game: {game_name}")
                    
                # Check for extras folder
                extras_folder = os.path.join(full_disk_path, extras_folder_name)
                print(f"Checking for extras folder: {extras_folder}")
                if os.path.exists(extras_folder) and os.path.isdir(extras_folder):
                    print(f"Extras folder found for game: {game_name}")
                    process_game_extras(game_name, full_disk_path, extras_folder, library_uuid)
                else:
                    print(f"No extras folder found for game: {game_name}")
            else:
                scan_job_entry.folders_failed += 1
                print(f"Failed to process game {game_name} after fallback attempts.")   
            db.session.commit()

        except Exception as e:
            print(f"Failed to process game {game_name}: {e}")
            scan_job_entry.folders_failed += 1
            scan_job_entry.status = 'Failed'
            scan_job_entry.error_message += f" Failed to process {game_name}: {str(e)}; "
            db.session.commit()

    if scan_job_entry.status != 'Failed':
        scan_job_entry.status = 'Completed'
    
    try:
        # Truncate error message if it's too long
        if scan_job_entry.error_message and len(scan_job_entry.error_message) > 500:
            scan_job_entry.error_message = scan_job_entry.error_message[:497] + "..."
        
        db.session.commit()
        print(f"Scan completed for folder: {folder_path} with ScanJob ID: {scan_job_entry.id}")
    except SQLAlchemyError as e:
        print(f"Database error when finalizing ScanJob: {str(e)}")
        
        


def handle_auto_scan(auto_form):
    print("handle_auto_scan: function running.")
    if auto_form.validate_on_submit():
        library_uuid = auto_form.library_uuid.data
        remove_missing = auto_form.remove_missing.data
        
        running_job = ScanJob.query.filter_by(status='Running').first()
        if running_job:
            flash('A scan is already in progress. Please wait until the current scan completes.', 'error')
            session['active_tab'] = 'auto'
            return redirect(url_for('main.scan_management', library_uuid=library_uuid, active_tab='auto'))

    
        library = Library.query.filter_by(uuid=library_uuid).first()
        if not library:
            flash('Selected library does not exist. Please select a valid library.', 'error')
            return redirect(url_for('main.scan_management', active_tab='auto'))

        
        folder_path = auto_form.folder_path.data
        
        scan_mode = auto_form.scan_mode.data

        
        print(f"Auto-scan form submitted. Library: {library.name}, Folder: {folder_path}, Scan mode: {scan_mode}")
        # Prepend the base path
        base_dir = current_app.config.get('BASE_FOLDER_WINDOWS') if os.name == 'nt' else current_app.config.get('BASE_FOLDER_POSIX')
        full_path = os.path.join(base_dir, folder_path)
        if not os.path.exists(full_path) or not os.access(full_path, os.R_OK):
            flash(f"Cannot access folder: {full_path}. Please check the path and permissions.", 'error')
            print(f"Cannot access folder: {full_path}. Please check the path and permissions.", 'error')
            session['active_tab'] = 'auto'
            return redirect(url_for('library.library'))

        @copy_current_request_context
        def start_scan():
            scan_and_add_games(full_path, scan_mode, library_uuid, remove_missing)

        thread = Thread(target=start_scan)
        thread.start()
        
        flash(f"Auto-scan started for folder: {full_path} and library name: {library.name}", 'info')
        session['active_tab'] = 'auto'
    else:
        flash(f"Auto-scan form validation failed: {auto_form.errors}")
        print(f"Auto-scan form validation failed: {auto_form.errors}")
    return redirect(url_for('main.scan_management', library_uuid=library_uuid, active_tab='auto'))