import os
from datetime import datetime, timezone
from flask import current_app, flash, has_request_context
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select

from modules import db
from modules.models import (
    Game, 
    Image, 
    Library, 
    GameUpdate, 
    GameExtra, 
    UnmatchedFolder,
    GlobalSettings,
    ScanJob
)
from modules.utils_functions import read_first_nfo_content
from modules.utils_igdb_api import make_igdb_api_request
from modules.utils_logging import log_system_event


def try_add_game(game_name, full_disk_path, scan_job_id, library_uuid, check_exists=True):
    from modules.utils_game_core import (
        retrieve_and_save_game
    )
    print(f"try_add_game: {game_name} at {full_disk_path} with scan job ID: {scan_job_id}, check_exists: {check_exists}, and library UUID: {library_uuid}")
    
    # Fetch the library details using the library_uuid, if necessary
    library = db.session.execute(select(Library).filter_by(uuid=library_uuid)).scalar_one_or_none()
    if not library:
        print(f"Library with UUID {library_uuid} not found.")
        return False

    if check_exists:
        existing_game = db.session.execute(select(Game).filter_by(full_disk_path=full_disk_path)).scalar_one_or_none()
        if existing_game:
            print(f"Game already exists in database: {game_name} at {full_disk_path}")
            return False

    game = retrieve_and_save_game(game_name, full_disk_path, scan_job_id, library_uuid)
    return game is not None


def process_game_with_fallback(game_name, full_disk_path, scan_job_id, library_uuid):
    # Fetch library details based on library_uuid
    library = db.session.execute(select(Library).filter_by(uuid=library_uuid)).scalar_one_or_none()
    scan_job = db.session.get(ScanJob, scan_job_id)
    if not library:
        print(f"Library with UUID {library_uuid} not found.")
        return False

    # Log skipping of processing for already matched or unmatched folders
    existing_unmatched_folder = db.session.execute(select(UnmatchedFolder).filter_by(folder_path=full_disk_path)).scalar_one_or_none()
    if existing_unmatched_folder:
        print(f"Skipping processing for already logged unmatched folder: {full_disk_path}")
        # Update total count to maintain consistency even when skipping
        scan_job.folders_failed += 1
        return False

    # Check if the game already exists in the database
    existing_game = db.session.execute(select(Game).filter_by(full_disk_path=full_disk_path, library_uuid=library_uuid)).scalar_one_or_none()
    if existing_game:
        print(f"Game already exists in database: {game_name} at {full_disk_path}")
        # Don't increment success counter for existing games to avoid inflated counts during rescans
        return True 

    print(f'Game does not exist in database: {game_name} at {full_disk_path}')
    # Try to add the game, now using library_uuid
    if not try_add_game(game_name, full_disk_path, scan_job_id, library_uuid=library_uuid, check_exists=False):
        # Attempt fallback game name processing
        parts = game_name.split()
        for i in range(len(parts) - 1, 0, -1):
            fallback_name = ' '.join(parts[:i])
            if try_add_game(fallback_name, full_disk_path, scan_job_id, library_uuid=library_uuid, check_exists=False):
                return True
    else:
        print(f'Skipping duplicate game: {game_name} at {full_disk_path}')
        return True

    # If the game does not match, log it as unmatched
    matched_status = 'Unmatched'
    log_unmatched_folder(scan_job_id, full_disk_path, matched_status, library_uuid)
    return False



def log_unmatched_folder(scan_job_id, folder_path, matched_status, library_uuid=None):
    existing_unmatched_folder = db.session.execute(select(UnmatchedFolder).filter_by(folder_path=folder_path)).scalar_one_or_none()

    if existing_unmatched_folder is None:
        unmatched_folder = UnmatchedFolder(
            folder_path=folder_path,
            failed_time=datetime.now(timezone.utc),
            content_type='Games',
            library_uuid=library_uuid,
            status=matched_status
        )
        try:
            db.session.add(unmatched_folder)
            db.session.commit()
            print(f"Logged unmatched folder: {folder_path}")
        except IntegrityError:
            log_system_event(f"Failed to log unmatched folder: {folder_path}", event_type='scan', event_level='warning')
            db.session.rollback()
            print(f"Failed to log unmatched folder due to a database error: {folder_path}")
    else:
        print(f"Unmatched folder already logged for: {folder_path}. Skipping.")
        


def process_game_updates(game_name, full_disk_path, updates_folder, library_uuid, update_folder_name=None):
    # Use passed parameter or fallback to database query
    if update_folder_name is None:
        settings = db.session.execute(select(GlobalSettings)).scalar_one_or_none()
        if not settings or not settings.update_folder_name:
            print("No update folder configuration found in database")
            return
        update_folder_name = settings.update_folder_name

    print(f"Processing updates for game: {game_name}")
    print(f"Full disk path: {full_disk_path}")
    print(f"Updates folder: {updates_folder}")
    print(f"Library UUID: {library_uuid}")

    game = db.session.execute(select(Game).filter_by(full_disk_path=full_disk_path, library_uuid=library_uuid)).scalar_one_or_none()
    if not game:
        print(f"Game not found in database: {game_name}")
        return

    print(f"Game found in database: {game.name} (UUID: {game.uuid})")

    update_folders = [f for f in os.listdir(updates_folder) if os.path.isdir(os.path.join(updates_folder, f))]
    print(f"Update folders found: {update_folders}")

    for update_folder in update_folders:
        update_path = os.path.join(updates_folder, update_folder)
        print(f"Processing update: {update_folder}")
        
        significant_files = [f for f in os.listdir(update_path) if not f.lower().endswith(('.sfv', '.nfo'))]
        print(f"Significant files in update folder: {significant_files}")

        if len(significant_files) == 1:
            file_path = os.path.join(update_path, significant_files[0])
            print(f"Single significant file update: {file_path}")
        else:
            file_path = update_path
            print(f"Multiple files update, using folder path: {file_path}")

        # Create or update GameUpdate record
        game_update = db.session.execute(select(GameUpdate).filter_by(game_uuid=game.uuid, file_path=file_path)).scalar_one_or_none()
        if not game_update:
            print(f"Creating new GameUpdate record for {file_path}")
            game_update = GameUpdate(
                game_uuid=game.uuid,
                file_path=file_path,
                nfo_content=read_first_nfo_content(update_path)
            )
            db.session.add(game_update)
        else:
            print(f"Updating existing GameUpdate record for {file_path}")
            game_update.file_path = file_path
            game_update.nfo_content = read_first_nfo_content(update_path)

    try:
        db.session.commit()
        print(f"Successfully committed GameUpdate records to database")
    except SQLAlchemyError as e:
        print(f"Error committing GameUpdate records to database: {str(e)}")
        db.session.rollback()

    print(f"Finished processing updates for game: {game_name}")
    


def process_game_extras(game_name, full_disk_path, extras_folder, library_uuid, extras_folder_name=None):
    # Use passed parameter or fallback to database query
    if extras_folder_name is None:
        settings = db.session.execute(select(GlobalSettings)).scalar_one_or_none()
        if not settings or not settings.extras_folder_name:
            print("No extras folder configuration found in database")
            return
        extras_folder_name = settings.extras_folder_name

    print(f"Processing extras for game: {game_name}")
    print(f"Full disk path: {full_disk_path}")
    print(f"Extras folder: {extras_folder}")
    print(f"Library UUID: {library_uuid}")

    game = db.session.execute(select(Game).filter_by(full_disk_path=full_disk_path, library_uuid=library_uuid)).scalar_one_or_none()
    if not game:
        print(f"Game not found in database: {game_name}")
        return

    print(f"Game found in database: {game.name} (UUID: {game.uuid})")
    extra_items = [f for f in os.listdir(extras_folder) if os.path.isfile(os.path.join(extras_folder, f)) or 
                  os.path.isdir(os.path.join(extras_folder, f))]
    print(f"Extra items found: {extra_items}")

    for extra_item in extra_items:
        extra_path = os.path.join(extras_folder, extra_item)
        print(f"Processing extra: {extra_item}")
        
        # Skip .nfo and .sfv files
        if extra_item.lower().endswith(('.nfo', '.sfv')):
            continue

        # Create or update GameExtra record
        game_extra = db.session.execute(select(GameExtra).filter_by(game_uuid=game.uuid, file_path=extra_path)).scalar_one_or_none()
        if not game_extra:
            print(f"Creating new GameExtra record for {extra_path}")
            game_extra = GameExtra(
                game_uuid=game.uuid,
                file_path=extra_path,
                nfo_content=read_first_nfo_content(os.path.dirname(extra_path))
            )
            db.session.add(game_extra)
        else:
            print(f"Updating existing GameExtra record for {extra_path}")
            game_extra.file_path = extra_path
            game_extra.nfo_content = read_first_nfo_content(os.path.dirname(extra_path))

    try:
        db.session.commit()
        print(f"Successfully processed extras for game: {game_name}")
    except SQLAlchemyError as e:
        print(f"Error processing extras for game: {str(e)}")
        db.session.rollback()

    print(f"Finished processing extras for game: {game_name}")


def refresh_images_in_background(game_uuid):
    with current_app.app_context():
        from modules.utils_game_core import (
            process_and_save_image
        )
        game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalar_one_or_none()
        if not game:
            print("Game not found.")
            return
        try:
            response_json = make_igdb_api_request(current_app.config['IGDB_API_ENDPOINT'],
                f"""fields id, cover.url, screenshots.url;
                    where id = {game.igdb_id}; limit 1;""")

            if 'error' not in response_json and response_json:
                delete_game_images(game_uuid)
                cover_data = response_json[0].get('cover')
                if cover_data:
                    process_and_save_image(game.uuid, cover_data['id'], image_type='cover')

                screenshots_data = response_json[0].get('screenshots', [])
                for screenshot in screenshots_data:
                    process_and_save_image(game.uuid, screenshot['id'], image_type='screenshot')

                db.session.commit()
                if has_request_context():
                    flash("Game images refreshed successfully.", "success")
                else:
                    print("Game images refreshed successfully.")
            else:
                if has_request_context():
                    flash("Failed to retrieve game images from IGDB API.", "error")
                else:
                    print("Failed to retrieve game images from IGDB API.")

        except Exception as e:
            db.session.rollback()
            if has_request_context():
                flash(f"Failed to refresh game images: {str(e)}", "error")
            else:
                print(f"Failed to refresh game images: {str(e)}")
            
def delete_game_images(game_uuid):
    with current_app.app_context():
        game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalar_one_or_none()
        if not game:
            print("Game not found for image deletion.")
            return

        images_to_delete = db.session.execute(select(Image).filter_by(game_uuid=game_uuid)).scalars().all()

        for image in images_to_delete:
            try:
                relative_image_path = image.url.replace('/static/library/images/', '').strip("/")
                image_file_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], relative_image_path)
                image_file_path = os.path.normpath(image_file_path)

                if os.path.exists(image_file_path):
                    os.remove(image_file_path)
                    if not os.path.exists(image_file_path):
                        print(f"Deleted image file: {image_file_path}")
                    else:
                        print(f"Failed to delete image file: {image_file_path}")
                else:
                    print(f"Image file not found: {image_file_path}")

                db.session.delete(image)
            except Exception as e:
                print(f"Error deleting image or database operation failed: {e}")
                db.session.rollback()
                continue  # next image

        try:
            db.session.commit()
            print("All associated images have been deleted.")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing image deletion changes to the database: {e}")
            
def is_scan_job_running():
    """
    Check if there is any scan job with the status 'Running'.
    
    Returns:
        bool: True if there is a running scan job, False otherwise.
    """
    running_scan_job = db.session.execute(select(ScanJob).filter_by(status='Running')).first()
    return running_scan_job is not None
