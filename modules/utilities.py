#/modules/utilities.py
import os
from datetime import datetime
from threading import Thread
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select, func
from flask import current_app, flash, redirect, url_for, session, copy_current_request_context
from modules.utils_functions import (
    load_release_group_patterns,
)
from modules.models import (
    Game, Library, AllowedFileType, ScanJob, GlobalSettings, UnmatchedFolder
)
from modules import db
from modules.utils_game_core import remove_from_lib
from modules.utils_gamenames import get_game_names_from_folder, get_game_names_from_files
from modules.utils_scanning import process_game_with_fallback, process_game_updates, process_game_extras, is_scan_job_running
from modules.utils_igdb_api import IGDBRateLimiter
from modules.utils_security import is_safe_path, get_allowed_base_directories


def scan_and_add_games(folder_path, scan_mode='folders', library_uuid=None, remove_missing=False, existing_job=None, download_missing_images=False):
    # Only check for running jobs if we're not restarting an existing job
    if not existing_job and is_scan_job_running():
        print("A scan is already in progress. Please wait for it to complete.")
        return
        
    # Cache settings once at the start of scan
    settings = db.session.execute(select(GlobalSettings)).scalars().first()
    update_folder_name = settings.update_folder_name if settings else 'updates'
    extras_folder_name = settings.extras_folder_name if settings else 'extras'
    enable_game_updates = settings.enable_game_updates if settings else False
    enable_game_extras = settings.enable_game_extras if settings else False
    scan_thread_count = settings.scan_thread_count if settings else 1
    
    # Initialize IGDB rate limiter for scanning operations
    igdb_rate_limiter = IGDBRateLimiter()
    
    # Bulk prefetch existing games and unmatched folders for performance
    print("Prefetching existing games and unmatched folders...")
    existing_game_paths = set(
        db.session.execute(
            select(Game.full_disk_path).filter_by(library_uuid=library_uuid)
        ).scalars().all()
    )
    existing_unmatched_paths = set(
        db.session.execute(
            select(UnmatchedFolder.folder_path).filter_by(library_uuid=library_uuid)
        ).scalars().all()
    )
    print(f"Prefetched {len(existing_game_paths)} existing games and {len(existing_unmatched_paths)} unmatched folders")
    
    # First, find the library and its platform
    library = db.session.execute(select(Library).filter_by(uuid=library_uuid)).scalars().first()
    if not library:
        print(f"Library with UUID {library_uuid} not found.")
        return

    # Get allowed file types from database
    allowed_extensions = [ext.value.lower() for ext in db.session.execute(select(AllowedFileType)).scalars().all()]
    if not allowed_extensions:
        print("No allowed file types found in database. Please configure them in the admin panel.")
        return

    print(f"Starting auto scan for games in folder: {folder_path} with scan mode: {scan_mode} and library UUID: {library_uuid} for platform: {library.platform.name}")
    
    # Use existing job or create new one
    if existing_job:
        # Re-query the job to ensure it's bound to the current session
        scan_job_entry = db.session.get(ScanJob, existing_job.id)
        print(f"Using existing scan job: {scan_job_entry.id}")
    else:
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
            folders_failed=0,
            removed_count=0,
            scan_folder=folder_path,
            setting_remove=remove_missing,
            setting_filefolder=(scan_mode == 'files'),
            setting_download_missing_images=download_missing_images
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

    def process_single_game(game_info, scan_job_id, library_uuid, update_folder_name, extras_folder_name, enable_game_updates, enable_game_extras, existing_game_paths, existing_unmatched_paths, igdb_rate_limiter, app):
        """Process a single game with rate limiting and thread-safe database operations."""
        game_name = game_info['name']
        full_disk_path = game_info['full_path']
        result = {'game_name': game_name, 'success': False, 'error': None}
        
        # Fast path - check cached sets BEFORE rate limiting
        if existing_game_paths and full_disk_path in existing_game_paths:
            print(f"Game already exists (cached): {game_name} at {full_disk_path}")
            return {'game_name': game_name, 'success': True, 'already_exists': True}
        
        if existing_unmatched_paths and full_disk_path in existing_unmatched_paths:
            print(f"Folder already logged as unmatched (cached): {full_disk_path}")
            return {'game_name': game_name, 'success': False, 'already_unmatched': True}
        
        # Ensure we have a Flask app context for database operations
        with app.app_context():
            try:
                # Use rate limiter for IGDB API calls
                igdb_rate_limiter.acquire()
                try:
                    success = process_game_with_fallback(game_name, full_disk_path, scan_job_id, library_uuid)
                    result['success'] = success
                    
                    if success:
                        # Check for updates folder using the cached setting
                        if enable_game_updates:
                            updates_folder = os.path.join(full_disk_path, update_folder_name)
                            if os.path.exists(updates_folder) and os.path.isdir(updates_folder):
                                print(f"Updates folder found for game: {game_name}")
                                process_game_updates(game_name, full_disk_path, updates_folder, library_uuid, update_folder_name)
                            else:
                                print(f"No updates folder found for game: {game_name}")
                        else:
                            print(f"Updates scanning disabled, skipping for game: {game_name}")
                            
                        # Check for extras folder
                        if enable_game_extras:
                            extras_folder = os.path.join(full_disk_path, extras_folder_name)
                            if os.path.exists(extras_folder) and os.path.isdir(extras_folder):
                                print(f"Extras folder found for game: {game_name}")
                                process_game_extras(game_name, full_disk_path, extras_folder, library_uuid, extras_folder_name)
                            else:
                                print(f"No extras folder found for game: {game_name}")
                        else:
                            print(f"Extras scanning disabled, skipping for game: {game_name}")
                    else:
                        result['unmatched'] = True
                        print(f"[PROCESS INFO] Game '{game_name}' could not be matched to IGDB database or was already unmatched.")
                        print(f"[PROCESS INFO] Game path: {full_disk_path}")
                        print(f"[PROCESS INFO] This is informational, not an error")
                        
                finally:
                    igdb_rate_limiter.release()
                    
            except Exception as e:
                result['error'] = str(e)
                print(f"[PROCESS EXCEPTION] Exception in process_single_game for '{game_name}': {str(e)}")
                print(f"[PROCESS EXCEPTION] Game path: {full_disk_path}")
                print(f"[PROCESS EXCEPTION] Full exception: {repr(e)}")
                import traceback
                print(f"[PROCESS EXCEPTION] Traceback: {traceback.format_exc()}")
                
        return result
    
    # Process games either sequentially or in parallel based on thread count
    if scan_thread_count > 1:
        # Multithreaded processing
        print(f"Using multithreaded scanning with {scan_thread_count} threads")
        with ThreadPoolExecutor(max_workers=scan_thread_count) as executor:
            # Submit all game processing tasks
            future_to_game = {
                executor.submit(process_single_game, game_info, scan_job_entry.id, library_uuid, 
                              update_folder_name, extras_folder_name, enable_game_updates, enable_game_extras,
                              existing_game_paths, existing_unmatched_paths, igdb_rate_limiter, current_app._get_current_object()): game_info 
                for game_info in game_names_with_paths
            }
            
            # Process completed futures
            for future in as_completed(future_to_game):
                # Check if the job is still enabled
                db.session.refresh(scan_job_entry)
                if not scan_job_entry.is_enabled:
                    # Cancel remaining tasks
                    for f in future_to_game:
                        f.cancel()
                    scan_job_entry.status = 'Failed'
                    scan_job_entry.error_message = 'Scan cancelled by the captain'
                    db.session.commit()
                    return
                
                game_info = future_to_game[future]
                try:
                    result = future.result()
                    if result['success']:
                        scan_job_entry.folders_success += 1
                    elif result.get('unmatched'):
                        # Unmatched games are not errors, just increment failed count for tracking
                        scan_job_entry.folders_failed += 1
                        print(f"[SCAN INFO] Game '{result['game_name']}' was unmatched (not an error)")
                    else:
                        scan_job_entry.folders_failed += 1
                        
                    # Only add actual errors to error_message, not unmatched games
                    if result.get('error') and not result.get('unmatched'):
                        error_line = f"Failed to process '{result['game_name']}': {result['error']}"
                        scan_job_entry.error_message = (scan_job_entry.error_message or "") + f"{error_line}\n"
                        print(f"[SCAN ERROR] {error_line}")
                        print(f"[SCAN ERROR] Game path: {future_to_game[future]['full_path']}")
                        print(f"[SCAN ERROR] Full result: {result}")
                        
                except Exception as e:
                    scan_job_entry.folders_failed += 1
                    error_line = f"Exception processing '{game_info['name']}': {str(e)}"
                    scan_job_entry.error_message = (scan_job_entry.error_message or "") + f"{error_line}\n"
                    print(f"[SCAN EXCEPTION] {error_line}")
                    print(f"[SCAN EXCEPTION] Game path: {game_info.get('full_path', 'unknown')}")
                    print(f"[SCAN EXCEPTION] Full exception: {repr(e)}")
                    import traceback
                    print(f"[SCAN EXCEPTION] Traceback: {traceback.format_exc()}")
                    
                db.session.commit()
    else:
        # Sequential processing (original behavior)
        print("Using single-threaded sequential scanning")
        
        # Progress tracking variables
        processed_count = 0
        already_exist_count = 0
        new_games_count = 0
        already_unmatched_count = 0
        scan_start_time = datetime.now()
        
        for game_info in game_names_with_paths:
            db.session.refresh(scan_job_entry)  # Check if the job is still enabled
            if not scan_job_entry.is_enabled:
                scan_job_entry.status = 'Failed'
                scan_job_entry.error_message = 'Scan cancelled by the captain'
                db.session.commit()
                return  # Stop processing if cancelled
            
            game_name = game_info['name']
            full_disk_path = game_info['full_path']
            processed_count += 1
            
            # Fast path - check cached sets BEFORE database queries
            if existing_game_paths and full_disk_path in existing_game_paths:
                print(f"Game already exists (cached): {game_name} at {full_disk_path}")
                already_exist_count += 1
                scan_job_entry.folders_success += 1
            elif existing_unmatched_paths and full_disk_path in existing_unmatched_paths:
                print(f"Folder already logged as unmatched (cached): {full_disk_path}")
                already_unmatched_count += 1
                scan_job_entry.folders_failed += 1
            else:
                try:
                    success = process_game_with_fallback(game_name, full_disk_path, scan_job_entry.id, library_uuid, existing_game_paths, existing_unmatched_paths)
                    if success:
                        new_games_count += 1
                        scan_job_entry.folders_success += 1
                        # Use cached settings instead of querying database again
                        # Check for updates folder using the cached setting
                        if enable_game_updates:
                            updates_folder = os.path.join(full_disk_path, update_folder_name)
                            if os.path.exists(updates_folder) and os.path.isdir(updates_folder):
                                print(f"Updates folder found for game: {game_name}")
                                process_game_updates(game_name, full_disk_path, updates_folder, library_uuid, update_folder_name)
                            else:
                                print(f"No updates folder found for game: {game_name}")
                        else:
                            print(f"Updates scanning disabled, skipping for game: {game_name}")
                            
                        # Check for extras folder
                        if enable_game_extras:
                            extras_folder = os.path.join(full_disk_path, extras_folder_name)
                            if os.path.exists(extras_folder) and os.path.isdir(extras_folder):
                                print(f"Extras folder found for game: {game_name}")
                                process_game_extras(game_name, full_disk_path, extras_folder, library_uuid, extras_folder_name)
                            else:
                                print(f"No extras folder found for game: {game_name}")
                        else:
                            print(f"Extras scanning disabled, skipping for game: {game_name}")
                    else:
                        scan_job_entry.folders_failed += 1
                        print(f"[SCAN INFO] Game '{game_name}' could not be matched to IGDB database or was already unmatched.")
                        print(f"[SCAN INFO] Game path: {full_disk_path}")
                        print(f"[SCAN INFO] This is informational, not an error")

                except Exception as e:
                    print(f"[SCAN EXCEPTION] Exception processing game '{game_name}': {str(e)}")
                    print(f"[SCAN EXCEPTION] Game path: {full_disk_path}")
                    print(f"[SCAN EXCEPTION] Full exception: {repr(e)}")
                    import traceback
                    print(f"[SCAN EXCEPTION] Traceback: {traceback.format_exc()}")
                    scan_job_entry.folders_failed += 1
                    scan_job_entry.status = 'Failed'
                    error_line = f"Exception processing '{game_name}': {str(e)}"
                    scan_job_entry.error_message = (scan_job_entry.error_message or "") + f"{error_line}\n"
            
            # Commit after each game and update progress
            scan_job_entry.current_processing = f"Processing: {game_name} ({processed_count}/{len(game_names_with_paths)})"
            scan_job_entry.last_progress_update = datetime.now()
            
            db.session.commit()
            
            # Log detailed progress every 10 games
            if processed_count % 10 == 0 or processed_count == len(game_names_with_paths):
                print(f"Committed: {processed_count}/{len(game_names_with_paths)} games processed")
                
                elapsed_time = (datetime.now() - scan_start_time).total_seconds()
                games_per_second = processed_count / elapsed_time if elapsed_time > 0 else 0
                estimated_remaining = (len(game_names_with_paths) - processed_count) / games_per_second if games_per_second > 0 else 0
                
                print(f"Progress: {processed_count}/{len(game_names_with_paths)} games processed")
                print(f"Speed: {games_per_second:.1f} games/sec")
                if estimated_remaining > 0:
                    print(f"Estimated time remaining: {estimated_remaining:.0f} seconds")
                print(f"Skipped (already exist): {already_exist_count}")
                print(f"New games found: {new_games_count}")
                print(f"Already unmatched: {already_unmatched_count}")

    if scan_job_entry.status != 'Failed':
        scan_job_entry.status = 'Completed'
    
    # If remove_missing is enabled, check for games that no longer exist
    if remove_missing:
        print("Checking for missing games...")
        games_in_library = db.session.execute(select(Game).filter_by(library_uuid=library_uuid)).scalars().all()
        for game in games_in_library:
            if not os.path.exists(game.full_disk_path):
                print(f"Game no longer found at path: {game.full_disk_path}")
                try:
                    remove_from_lib(game.uuid)
                    scan_job_entry.removed_count += 1
                    print(f"Removed game {game.name} as it no longer exists at {game.full_disk_path}")
                except Exception as e:
                    print(f"Error removing game {game.name}: {e}")

    # If download_missing_images is enabled, check for and queue missing images
    if download_missing_images:
        print("🔍 Download missing images option enabled - checking for missing images...")
        try:
            from modules.utils_game_core import process_missing_images_for_scan
            result = process_missing_images_for_scan(library_uuid, current_app._get_current_object())
            
            if result.get('success'):
                message = f"Missing images scan: {result['message']}"
                print(message)
                
                # Add to scan job status for user feedback
                if scan_job_entry.error_message:
                    scan_job_entry.error_message += f" | {message}"
                else:
                    scan_job_entry.error_message = message
                    
            else:
                error_message = f"Missing images scan failed: {result.get('error', 'Unknown error')}"
                print(error_message)
                scan_job_entry.error_message += f" | {error_message}"
                
        except Exception as e:
            error_message = f"Error during missing images processing: {str(e)}"
            print(error_message)
            scan_job_entry.error_message += f" | {error_message}"

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
    print(f"Auto-scan form data: {auto_form.data}")
    library_uuid = auto_form.library_uuid.data
    if auto_form.validate_on_submit():
        remove_missing = auto_form.remove_missing.data
        download_missing_images = auto_form.download_missing_images.data
        
        running_job = db.session.execute(select(ScanJob).filter_by(status='Running')).scalars().first()
        if running_job:
            print("A scan is already in progress. Please wait until the current scan completes.")
            flash('A scan is already in progress. Please wait until the current scan completes.', 'error')
            session['active_tab'] = 'auto'
            return redirect(url_for('main.scan_management', library_uuid=library_uuid, active_tab='auto'))

    
        library = db.session.execute(select(Library).filter_by(uuid=library_uuid)).scalars().first()
        if not library:
            print(f"Selected library does not exist. Please select a valid library.")
            flash('Selected library does not exist. Please select a valid library.', 'error')
            return redirect(url_for('main.scan_management', active_tab='auto'))

        folder_path = auto_form.folder_path.data
        scan_mode = auto_form.scan_mode.data        
        print(f"Auto-scan form submitted. Library: {library.name}, Folder: {folder_path}, Scan mode: {scan_mode}, Download missing images: {download_missing_images}")
        
        # Validate folder path security
        allowed_bases = get_allowed_base_directories(current_app)
        if not allowed_bases:
            flash('Service configuration error: No allowed base directories configured.', 'error')
            return redirect(url_for('main.scan_management', active_tab='auto'))
        
        # Prepend the base path
        base_dir = current_app.config.get('BASE_FOLDER_WINDOWS') if os.name == 'nt' else current_app.config.get('BASE_FOLDER_POSIX')
        full_path = os.path.join(base_dir, folder_path)
        
        # Security validation: ensure the constructed path is within allowed directories
        is_safe, error_message = is_safe_path(full_path, allowed_bases)
        if not is_safe:
            print(f"Security error: Auto-scan path validation failed for {full_path}: {error_message}")
            flash(f"Access denied: {error_message}", 'error')
            return redirect(url_for('main.scan_management', active_tab='auto'))
        
        if not os.path.exists(full_path) or not os.access(full_path, os.R_OK):
            flash(f"Cannot access folder: {full_path}. Please check the path and permissions.", 'error')
            print(f"Cannot access folder: {full_path}. Please check the path and permissions.", 'error')
            session['active_tab'] = 'auto'
            return redirect(url_for('library.library'))

        @copy_current_request_context
        def start_scan():
            scan_and_add_games(full_path, scan_mode, library_uuid, remove_missing, download_missing_images=download_missing_images)

        thread = Thread(target=start_scan)
        thread.start()
        
        flash(f"Auto-scan started for folder: {full_path} and library name: {library.name}", 'info')
        session['active_tab'] = 'auto'
    else:
        flash(f"Auto-scan form validation failed: {auto_form.errors}")
        print(f"Auto-scan form validation failed: {auto_form.errors}")
    return redirect(url_for('main.scan_management', library_uuid=library_uuid, active_tab='auto'))



def handle_manual_scan(manual_form):
    session['active_tab'] = 'manual'
    library_uuid = manual_form.library_uuid.data
    if manual_form.validate_on_submit():
        # check job status
        running_job = db.session.execute(select(ScanJob).filter_by(status='Running')).scalars().first()
        if running_job:
            flash('A scan is already in progress. Please wait until the current scan completes.', 'error')
            session['active_tab'] = 'manual'
            return redirect(url_for('main.scan_management', active_tab='manual'))
        
        folder_path = manual_form.folder_path.data
        scan_mode = manual_form.scan_mode.data
        
        if not library_uuid:
            flash('Please select a library.', 'error')
            return redirect(url_for('main.scan_management', active_tab='manual'))
        
        # Store library_uuid in session for use in identify page
        session['selected_library_uuid'] = library_uuid
        print(f"Manual scan: Selected library UUID: {library_uuid}")

        # Validate folder path security
        allowed_bases = get_allowed_base_directories(current_app)
        if not allowed_bases:
            flash('Service configuration error: No allowed base directories configured.', 'error')
            return redirect(url_for('main.scan_management', active_tab='manual'))

        base_dir = current_app.config.get('BASE_FOLDER_WINDOWS') if os.name == 'nt' else current_app.config.get('BASE_FOLDER_POSIX')
        full_path = os.path.join(base_dir, folder_path)
        print(f"Manual scan form submitted. Full path: {full_path}, Library UUID: {library_uuid}")
        
        # Security validation: ensure the constructed path is within allowed directories
        is_safe, error_message = is_safe_path(full_path, allowed_bases)
        if not is_safe:
            print(f"Security error: Manual scan path validation failed for {full_path}: {error_message}")
            flash(f"Access denied: {error_message}", 'error')
            return redirect(url_for('main.scan_management', active_tab='manual'))

        if os.path.exists(full_path) and os.access(full_path, os.R_OK):
            print("Folder exists and can be accessed.")
            insensitive_patterns, sensitive_patterns = load_release_group_patterns()
            if scan_mode == 'folders':
                games_with_paths = get_game_names_from_folder(full_path, insensitive_patterns, sensitive_patterns)
            else:  # files mode
                # Load allowed file types from database
                allowed_file_types = db.session.execute(select(AllowedFileType)).scalars().all()
                supported_extensions = [file_type.value for file_type in allowed_file_types]
                if not supported_extensions:
                    flash("No allowed file types defined in the database.", "error")
                    return redirect(url_for('main.scan_management', active_tab='manual'))
                
                games_with_paths = get_game_names_from_files(full_path, supported_extensions, insensitive_patterns, sensitive_patterns)
            session['game_paths'] = {game['name']: game['full_path'] for game in games_with_paths}
            print(f"Found {len(session['game_paths'])} games in the folder.")
            flash('Manual scan processed for folder: ' + full_path, 'info')
            
        else:
            flash("Folder does not exist or cannot be accessed.", "error")
    else:
        flash('Manual scan form validation failed.', 'error')
        
    print("Game paths: ", session.get('game_paths', {}))
    return redirect(url_for('main.scan_management', library_uuid=library_uuid, active_tab='manual'))
