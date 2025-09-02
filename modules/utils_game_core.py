from datetime import datetime, UTC
from flask import flash, current_app, abort, has_request_context
from flask_login import current_user
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select, update, delete
from werkzeug.utils import secure_filename
import os, uuid

from modules import db
from modules.models import (
    Game, Image, Library, GlobalSettings,
    Developer, Publisher, Genre, Theme, GameMode, Platform, 
    PlayerPerspective, GameURL, ScanJob, Category, Status
)
from modules.utils_functions import (
    read_first_nfo_content, delete_associations_for_game,
    website_category_to_string,
    PLATFORM_IDS, format_size, download_image,
    get_folder_size_in_bytes_updates
)
from modules.utils_igdb_api import make_igdb_api_request
from modules.utils_discord import discord_webhook
from modules.utils_scanning import log_unmatched_folder, delete_game_images
from modules.utils_logging import log_system_event
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# IGDB API mapping dictionaries for category, status, and player perspective
category_mapping = {
    0: Category.MAIN_GAME,
    1: Category.DLC_ADDON,
    2: Category.EXPANSION,
    3: Category.BUNDLE,
    4: Category.STANDALONE_EXPANSION,
    5: Category.MOD,
    6: Category.EPISODE,
    7: Category.SEASON,
    8: Category.REMAKE,
    9: Category.REMASTER,
    10: Category.EXPANDED_GAME,
    11: Category.PORT,
    12: Category.PACK,
    13: Category.UPDATE
}

status_mapping = {
    1: Status.RELEASED,
    2: Status.ALPHA,
    3: Status.BETA,
    4: Status.EARLY_ACCESS,
    6: Status.OFFLINE,
    7: Status.CANCELLED
}

def get_or_create_entity(model_class, name_field="name", **kwargs):
    """
    Thread-safe helper to get an existing entity or create a new one.
    Handles race conditions that occur during multithreaded scanning.
    
    Args:
        model_class: The SQLAlchemy model class (Genre, Theme, etc.)
        name_field: The field name to query by (default: "name")
        **kwargs: The attributes to query and create with
        
    Returns:
        The existing or newly created entity instance
    """
    filter_value = kwargs.get(name_field)
    
    # First attempt: try to get existing entity
    entity = db.session.execute(
        select(model_class).filter_by(**{name_field: filter_value})
    ).scalar_one_or_none()
    
    if entity:
        return entity
    
    # Entity doesn't exist, try to create it
    try:
        entity = model_class(**kwargs)
        db.session.add(entity)
        db.session.flush()  # Flush to check for constraint violations immediately
        return entity
    except IntegrityError:
        # Handle race condition: another thread created the entity
        db.session.rollback()
        # Query again to get the entity created by the other thread
        entity = db.session.execute(
            select(model_class).filter_by(**{name_field: filter_value})
        ).scalar_one_or_none()
        if entity:
            return entity
        else:
            # This should not happen, but raise an error if it does
            raise RuntimeError(f"Failed to create or retrieve {model_class.__name__} with {name_field}='{filter_value}'")

def create_game_instance(game_data, full_disk_path, folder_size_bytes, library_uuid):
    global settings
    settings = db.session.execute(select(GlobalSettings)).scalar_one_or_none()
    new_game = None  # Initialize new_game to None
    
    try:
        if not isinstance(game_data, dict):
            raise ValueError("create_game_instance game_data is not a dictionary")

        # Fetch library details using library_uuid
        library = db.session.execute(select(Library).filter_by(uuid=library_uuid)).scalar_one_or_none()
        if not library:
            print(f"Library with UUID {library_uuid} not found.")
            return None

        category_id = game_data.get('category')
        category_enum = category_mapping.get(category_id, None)
        status_id = game_data.get('status')
        status_enum = status_mapping.get(status_id, None)
        if 'videos' in game_data:
            video_urls = [f"https://www.youtube.com/watch?v={video['video_id']}" for video in game_data['videos']]
            videos_comma_separated = ','.join(video_urls)
        else:
            videos_comma_separated = ""
            
        print(f"create_game_instance Creating game instance for '{game_data.get('name')}' with UUID: {game_data.get('id')} in library '{library.name}' on platform '{library.platform.name}'.")
        new_game = Game(
            library_uuid=library_uuid,
            igdb_id=game_data['id'],
            name=game_data['name'],
            summary=game_data.get('summary'),
            storyline=game_data.get('storyline'),
            url=game_data.get('url'),
            first_release_date=datetime.fromtimestamp(game_data.get('first_release_date', 0), UTC) if game_data.get('first_release_date') else None,
            aggregated_rating=game_data.get('aggregated_rating'),
            aggregated_rating_count=game_data.get('aggregated_rating_count'),
            rating=game_data.get('rating'),
            rating_count=game_data.get('rating_count'),
            slug=game_data.get('slug'),
            status=status_enum,
            category=category_enum,
            total_rating=game_data.get('total_rating'),
            total_rating_count=game_data.get('total_rating_count'),
            video_urls=videos_comma_separated,
            full_disk_path=full_disk_path,
            size=folder_size_bytes,
            date_created=datetime.now(UTC),
            date_identified=datetime.now(UTC),
            steam_url='',
            times_downloaded=0
        )
        
        db.session.add(new_game)
        db.session.flush()        
        fetch_and_store_game_urls(new_game.uuid, game_data['id'])
        print(f"create_game_instance Finished processing game '{new_game.name}'. URLs (if any) have been fetched and stored.")
        
    except Exception as e:
        game_name = game_data.get('name') if isinstance(game_data, dict) else str(game_data)
        print(f"create_game_instance Error during the game instance creation or URL fetching for game '{game_name}'. Error: {e}")
    
    return new_game



def store_image_url_for_download(game_uuid, image_data, image_type='cover'):
    """Store image URL in database for later async download."""
    try:
        # Get the image URL from IGDB API
        if image_type == 'cover':
            cover_query = f'fields url; where id={image_data};'
            cover_response = make_igdb_api_request('https://api.igdb.com/v4/covers', cover_query)
            if cover_response and 'error' not in cover_response:
                download_url = cover_response[0].get('url')
                if download_url and not download_url.startswith(('http://', 'https://')):
                    download_url = 'https:' + download_url
                download_url = download_url.replace('/t_thumb/', '/t_original/')
            else:
                print(f"Failed to retrieve URL for cover ID {image_data}.")
                return
        
        elif image_type == 'screenshot':
            screenshot_query = f'fields url; where id={image_data};'
            response = make_igdb_api_request('https://api.igdb.com/v4/screenshots', screenshot_query)
            if response and 'error' not in response:
                download_url = response[0].get('url')
                if download_url and not download_url.startswith(('http://', 'https://')):
                    download_url = 'https:' + download_url
                download_url = download_url.replace('/t_thumb/', '/t_original/')
            else:
                print(f"Failed to retrieve URL for screenshot ID {image_data}.")
                return
        
        # Generate filename for when it gets downloaded
        file_name = secure_filename(f"{game_uuid}_{image_type}_{image_data}.jpg")
        
        # Store image metadata with URL for later download
        image = Image(
            game_uuid=game_uuid,
            image_type=image_type,
            url=file_name,  # Local filename when downloaded
            igdb_image_id=str(image_data),
            download_url=download_url,
            is_downloaded=False
        )
        db.session.add(image)
        print(f"Stored {image_type} URL for game {game_uuid}: {download_url}")
        
    except Exception as e:
        print(f"Error storing image URL for {image_type} {image_data}: {e}")


def smart_process_images_for_game(game_uuid, cover_data=None, screenshots_data=None, app=None):
    """Smart image processing that uses settings to determine single-thread vs turbo mode."""
    if app is None:
        app = current_app._get_current_object()
    
    try:
        with app.app_context():
            # Get settings to determine processing mode
            from modules.models import GlobalSettings
            settings = db.session.execute(select(GlobalSettings)).scalar_one_or_none()
            
            # Store image URLs first (always)
            if cover_data:
                store_image_url_for_download(game_uuid, cover_data, 'cover')
            if screenshots_data:
                for screenshot_id in screenshots_data:
                    store_image_url_for_download(game_uuid, screenshot_id, 'screenshot')
            db.session.commit()
            
            # Decide processing mode based on settings
            if settings and settings.use_turbo_image_downloads:
                # TURBO MODE - Download immediately with parallel processing
                threads = settings.turbo_download_threads or 8
                print(f"🚀 TURBO MODE: Processing images for game {game_uuid} with {threads} threads")
                return download_images_for_game_turbo(game_uuid, app, max_workers=threads)
            else:
                # SINGLE THREAD MODE - Download one by one
                print(f"🐌 SINGLE THREAD: Processing images for game {game_uuid}")
                return download_images_for_game(game_uuid, app)
                
    except Exception as e:
        print(f"Error in smart image processing for game {game_uuid}: {e}")
        return 0


def download_images_for_game_turbo(game_uuid, app=None, max_workers=5):
    """Download all pending images for a specific game using turbo mode."""
    if app is None:
        app = current_app._get_current_object()
        
    try:
        with app.app_context():
            pending_images = db.session.execute(select(Image).filter_by(game_uuid=game_uuid, is_downloaded=False)).scalars().all()
            
            if not pending_images:
                print(f"No pending images for game {game_uuid}.")
                return 0
            
            print(f"🚀 TURBO downloading {len(pending_images)} images for game {game_uuid} with {max_workers} threads")
            
            downloaded_count = 0
            successful_images = []
            
            # Use ThreadPoolExecutor for parallel downloads
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_image = {
                    executor.submit(download_single_image_worker, image, app): image 
                    for image in pending_images
                }
                
                for future in as_completed(future_to_image):
                    image = future_to_image[future]
                    try:
                        result = future.result()
                        if result['success']:
                            successful_images.append(image.id)
                            downloaded_count += 1
                            print(f"✅ Downloaded {result['image_type']}: {result['url']}")
                    except Exception as e:
                        print(f"❌ Failed downloading image {image.id}: {e}")
            
            # Update database
            if successful_images:
                db.session.execute(
                    update(Image).filter(Image.id.in_(successful_images)).values(is_downloaded=True)
                )
                db.session.commit()
            
            print(f"🔥 TURBO download complete for game {game_uuid}: {downloaded_count} images")
            return downloaded_count
            
    except Exception as e:
        print(f"Error in turbo download for game {game_uuid}: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return 0


def process_and_save_image(game_uuid, image_data, image_type='cover'):
    url = None
    save_path = None
    file_name = None

    if image_type == 'cover':
        cover_query = f'fields url; where id={image_data};'
        cover_response = make_igdb_api_request('https://api.igdb.com/v4/covers', cover_query)
        if cover_response and 'error' not in cover_response:
            url = cover_response[0].get('url')
            if url:
                file_name = secure_filename(f"{game_uuid}_cover_{image_data}.jpg")
            else:
                print(f"Cover URL not found for ID {image_data}.")
                return
        else:
            print(f"Failed to retrieve URL for cover ID {image_data}.")
            return

        file_name = secure_filename(f"{game_uuid}_cover_{image_data}.jpg") 
        save_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], file_name)
        download_image(url, save_path)

    elif image_type == 'screenshot':
        screenshot_query = f'fields url; where id={image_data};'
        response = make_igdb_api_request('https://api.igdb.com/v4/screenshots', screenshot_query)
        if response and 'error' not in response:
            url = response[0].get('url')
            if url:
                file_name = secure_filename(f"{game_uuid}_{image_data}.jpg")
            else:
                print(f"Screenshot URL not found for ID {image_data}.")
                return
            file_name = secure_filename(f"{game_uuid}_{image_data}.jpg") 
    
    # Check if file_name is set before proceeding
    if not file_name:
        print("File name could not be set. Exiting.")
        return
    save_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], file_name)
    download_image(url, save_path)

    if file_name and save_path:
        image = Image(
            game_uuid=game_uuid,
            image_type=image_type,
            url=file_name,
        )
        db.session.add(image)
    
    
def fetch_and_store_game_urls(game_uuid, igdb_id):
    try:
        website_query = f'fields url, category; where game={igdb_id};'        
        websites_response = make_igdb_api_request('https://api.igdb.com/v4/websites', website_query)
        
        if websites_response and 'error' not in websites_response:
            for website in websites_response:
                
                new_url = GameURL(
                    game_uuid=game_uuid,
                    url_type=website_category_to_string(website.get('category')),
                    url=website.get('url')
                )
                db.session.add(new_url)
        else:
            print(f"No URLs found or failed to retrieve URLs for game IGDB ID {igdb_id}.")
    except Exception as e:
        print(f"Exception while fetching/storing URLs for game UUID {game_uuid}, IGDB ID {igdb_id}: {e}")
        

    
def retrieve_and_save_game(game_name, full_disk_path, scan_job_id=None, library_uuid=None):
    # print(f"retrieve_and_save_game Retrieving and saving game: {game_name} on {full_disk_path} to library with UUID {library_uuid}.")
    library = db.session.execute(select(Library).filter_by(uuid=library_uuid)).scalar_one_or_none()
    if not library:
        print(f"retrieve_and_save_game Library with UUID {library_uuid} not found.")
        return None
    
    print(f"retrieve_and_save_game Finding a way to add {game_name} on {full_disk_path} to the library with UUID {library_uuid}.")

    existing_game_by_path = check_existing_game_by_path(full_disk_path)
    if existing_game_by_path:
        return existing_game_by_path 

    print(f"retrieve_and_save_game No existing game found for {game_name} on {full_disk_path}. Proceeding to retrieve game data from IGDB API.")
    platform_id = PLATFORM_IDS.get(library.platform.name)
    print(f"retrieve_and_save_game Platform ID for {library.platform.name}: {platform_id}")
    if platform_id is None:
        print(f"No platform ID found for platform {library.platform.name}. Proceeding without a platform-specific search.")
    else:
        print(f"Performing a platform-specific search for {game_name} on platform ID: {platform_id}.")
    query_fields = """fields id, name, cover, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name,
                      screenshots, videos.video_id, first_release_date, aggregated_rating, involved_companies, player_perspectives.name,
                      aggregated_rating_count, rating, rating_count, slug, status, category, total_rating, 
                      total_rating_count;"""
    query_filter = f'search "{game_name}"; limit 1;'
    if platform_id is not None:
        query_filter += f' where platforms = ({platform_id});'

    response_json = make_igdb_api_request(current_app.config['IGDB_API_ENDPOINT'], query_fields + query_filter)
    print(f"retrieve_and_save Response JSON: {response_json}")
    if 'error' not in response_json and response_json:
        igdb_id = response_json[0].get('id')
        print(f"Found game {game_name} with IGDB ID {igdb_id}")

        # Check for existing game with the same IGDB ID but different folder path
        existing_game_with_same_igdb_id = db.session.execute(select(Game).filter(Game.igdb_id == igdb_id, Game.full_disk_path != full_disk_path)).scalar_one_or_none()
        if existing_game_with_same_igdb_id:
            print(f"Duplicate game found with same IGDB ID {igdb_id} but different folder path. Logging as duplicate.")
            matched_status = 'Duplicate'
            log_unmatched_folder(scan_job_id, full_disk_path, matched_status, library_uuid=library_uuid)
            return None
        else:
            print(f"attempting to read NFO content for game {game_name} on {full_disk_path}.")
            nfo_content = read_first_nfo_content(full_disk_path)            
            print(f"Calculating folder size for {full_disk_path}.")
            folder_size_bytes = get_folder_size_in_bytes_updates(full_disk_path)
            print(f"Folder size for {full_disk_path}: {format_size(folder_size_bytes)}")
            new_game = create_game_instance(game_data=response_json[0], full_disk_path=full_disk_path, folder_size_bytes=folder_size_bytes, library_uuid=library.uuid)
            
            if new_game is None:
                print(f"Failed to create game instance for {game_name}. Skipping further processing.")
                return None
                    
            if 'genres' in response_json[0]:
                for genre_data in response_json[0]['genres']:
                    genre_name = genre_data['name']
                    genre = get_or_create_entity(Genre, name=genre_name)
                    new_game.genres.append(genre)

            if 'involved_companies' in response_json[0]:
                involved_company_ids = response_json[0]['involved_companies']
                if involved_company_ids:
                    enumerate_companies(new_game, new_game.igdb_id, involved_company_ids)
                else:
                    print(f"No involved companies found for {game_name}.")

            if 'themes' in response_json[0]:
                for theme_data in response_json[0]['themes']:
                    theme_name = theme_data['name']
                    theme = get_or_create_entity(Theme, name=theme_name)
                    new_game.themes.append(theme)

            if 'game_modes' in response_json[0]:
                for game_mode_data in response_json[0]['game_modes']:
                    game_mode_name = game_mode_data['name']
                    game_mode = get_or_create_entity(GameMode, name=game_mode_name)
                    new_game.game_modes.append(game_mode)

            if 'platforms' in response_json[0]:
                for platform_data in response_json[0]['platforms']:
                    platform_name = platform_data['name']
                    platform = get_or_create_entity(Platform, name=platform_name)
                    new_game.platforms.append(platform)
                    
            if 'player_perspectives' in response_json[0]:
                for perspective_data in response_json[0]['player_perspectives']:
                    perspective_name = perspective_data['name']
                    perspective = get_or_create_entity(PlayerPerspective, name=perspective_name)
                    new_game.player_perspectives.append(perspective)
                    
            if 'videos' in response_json[0]:
                video_urls = [f"https://www.youtube.com/embed/{video['video_id']}" for video in response_json[0]['videos']]
                videos_comma_separated = ','.join(video_urls)
                new_game.video_urls = videos_comma_separated
            
            db.session.commit()
            print(f"Processing images for game: {new_game.name}")
            # Use smart image processing that respects turbo/single-thread settings
            cover_data = response_json[0].get('cover') 
            screenshots_data = response_json[0].get('screenshots', [])
            smart_process_images_for_game(new_game.uuid, cover_data, screenshots_data)
            try:
                new_game.nfo_content = nfo_content
                for column in new_game.__table__.columns:
                    attr = getattr(new_game, column.name)
                db.session.commit()
                print(f"Game and its images saved successfully : {new_game.name}.")
                
                # Move Discord notification here, after everything is saved successfully
                settings = db.session.execute(select(GlobalSettings)).scalar_one_or_none()
                if settings and settings.discord_webhook_url and settings.discord_notify_new_games:
                    print(f"Sending Discord notification for new game '{new_game.name}'.")
                    discord_webhook(new_game.uuid)
                    
            except IntegrityError as e: 
                db.session.rollback()
                print(f"Failed to save game due to a database error: {e}")
                if has_request_context():
                    flash("Failed to save game due to a duplicate entry.")
                else:
                    print("Failed to save game due to a duplicate entry.")
            return new_game
    else:
        if 'error' in response_json:
            # Check specifically for authentication error
            if response_json.get('error') == 'Failed to retrieve access token':
                error_msg = 'IGDB API Authentication Failed'
                if scan_job_id:
                    scan_job = db.session.get(ScanJob, scan_job_id)
                    if scan_job:
                        scan_job.error_message = error_msg
                        scan_job.status = 'Failed'
                        db.session.commit()
                
                log_system_event(f"IGDB API Authentication Failed: {response_json.get('error')}", 
                                 event_type='scan', event_level='error')
                return None
            
        print(f"No match found: {game_name} in library {library.name} on platform {library.platform.name}.")
        if has_request_context():
            flash("No game data found for the given name.")
        else:
            print("No game data found for the given name.")
        return None
    
def check_existing_game_by_path(full_disk_path):
    """
    Checks if a game already exists in the library by its disk path.

    Parameters:
    - full_disk_path: The full disk path of the game to check.

    Returns:
    - The existing Game object if found, None otherwise.
    """
    existing_game_by_path = db.session.execute(select(Game).filter_by(full_disk_path=full_disk_path)).scalar_one_or_none()
    if existing_game_by_path:
        print(f"Skipping {existing_game_by_path.name} on {full_disk_path} (path already in library).")
        return existing_game_by_path 
    return None

def check_existing_game_by_igdb_id(igdb_id):
    return db.session.execute(select(Game).filter_by(igdb_id=igdb_id)).scalar_one_or_none()


def enumerate_companies(game_instance, igdb_game_id, involved_company_ids):
    print(f"Enumerating companies for game {game_instance.name} with IGDB ID {igdb_game_id}.")
    if not involved_company_ids:
        print("No company IDs provided for enumeration.")
        return

    company_ids_str = ','.join(map(str, involved_company_ids))
    # print(f"Company IDs: {company_ids_str}")

    try:
        response_json = make_igdb_api_request(
            "https://api.igdb.com/v4/involved_companies",
            f"""fields company.name, developer, publisher, game;
                where game={igdb_game_id} & id=({company_ids_str});"""
        )

        if not isinstance(response_json, list):
            print(f"Unexpected response structure: {response_json}")
            return

        print(f"Involved companies response: {response_json}")
        for company_data in response_json:
            company_info = company_data.get('company')
            if not isinstance(company_info, dict) or 'name' not in company_info:
                print(f"Unexpected company data structure or missing name: {company_data}")
                continue  # Skip to the next

            company_name = company_info['name'][:50] 
            is_developer = company_data.get('developer', False)
            is_publisher = company_data.get('publisher', False)

            if is_developer:
                # print(f"Company {company_name} is a developer.")
                print(f"Creating or finding developer: {company_name}")
                developer = get_or_create_entity(Developer, name=company_name)

                print(f"Assigning developer {developer.name} to game {game_instance.name}.")
                game_instance.developer = developer

            if is_publisher:
                # print(f"Company {company_name} is a publisher.")
                publisher = get_or_create_entity(Publisher, name=company_name)
                game_instance.publisher = publisher
    except Exception as e:
        print(f"Failed to enumerate companies due to an error: {e}")
        return

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Failed to enumerate companies due to a database error: {e}")
        
def get_game_by_uuid(game_uuid):
    log_system_event(
        f"Searching for game UUID: {game_uuid[:8]}...",
        event_type='game',
        event_level='debug'
    )
    game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalar_one_or_none()
    if game:
        log_system_event(
            f"Game '{game.name}' (ID: {game.id}, IGDB: {game.igdb_id}) found for UUID search",
            event_type='game',
            event_level='debug'
        )
        return game
    else:
        log_system_event(
            f"Game not found for UUID: {game_uuid[:8]}...",
            event_type='game',
            event_level='debug'
        )
        return None
    
def remove_from_lib(game_uuid):
    """
    Remove a game from the library and clean up associated files.
    
    Args:
        game_uuid (str): UUID of the game to remove
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the game
        game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalar_one_or_none()
        if not game:
            print(f"Game with UUID {game_uuid} not found")
            return False
            
        # Delete associated images from disk
        delete_game_images(game_uuid)
        
        # Delete the game (cascade will handle related records)
        db.session.delete(game)
        db.session.commit()
        
        log_system_event(f"Game deleted: {game.name} (UUID: {game_uuid})", event_type='game', event_level='information')
        print(f"Successfully removed game {game.name} (UUID: {game_uuid}) from library")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error removing game from library: {str(e)}")
        return False
    

def delete_game(game_identifier):
    """Delete a game by UUID or Game object.""" 
    game_to_delete = None
    if isinstance(game_identifier, Game):
        game_to_delete = game_identifier
        game_uuid_str = game_to_delete.uuid
    else:
        try:
            valid_uuid = uuid.UUID(game_identifier, version=4)
            game_uuid_str = str(valid_uuid)
            game_to_delete = db.session.execute(select(Game).filter_by(uuid=game_uuid_str)).scalar_one_or_none() or abort(404)
        except ValueError:
            print(f"Invalid UUID format: {game_identifier}")
            abort(404)
        except Exception as e:
            print(f"Error fetching game with UUID {game_uuid_str}: {e}")
            abort(404)

    try:
        print(f"Found game to delete: {game_to_delete}")
        db.session.execute(delete(GameURL).filter_by(game_uuid=game_uuid_str))
        delete_associations_for_game(game_to_delete)        
        delete_game_images(game_uuid_str)
        db.session.delete(game_to_delete)
        db.session.commit()
        # flash('Game and its images have been deleted successfully.', 'success')
        print(f'Deleted game with UUID: {game_uuid_str}')
    except Exception as e:
        db.session.rollback()
        print(f'Error deleting game with UUID {game_uuid_str}: {e}')
        if has_request_context():
            flash(f'Error deleting game: {e}', 'error')
        else:
            print(f'Error deleting game: {e}')


def download_pending_images(batch_size=10, delay_between_downloads=1, app=None):
    """Download images that are queued but not yet downloaded."""
    if app is None:
        app = current_app._get_current_object()
        
    try:
        with app.app_context():
            # Get pending images
            pending_images = db.session.execute(select(Image).filter_by(is_downloaded=False).limit(batch_size)).scalars().all()
            
            if not pending_images:
                print("No pending images to download.")
                return 0
            
            downloaded_count = 0
            for image in pending_images:
                try:
                    if not image.download_url:
                        print(f"No download URL for image {image.id}, skipping.")
                        continue
                    
                    # Download the image
                    save_path = os.path.join(app.config['IMAGE_SAVE_PATH'], image.url)
                    
                    from modules.utils_functions import download_image
                    download_image(image.download_url, save_path)
                    
                    # Mark as downloaded
                    image.is_downloaded = True
                    downloaded_count += 1
                    
                    print(f"Downloaded {image.image_type} for game {image.game_uuid}: {image.url}")
                    
                    # Small delay to avoid overwhelming the server
                    if delay_between_downloads > 0:
                        time.sleep(delay_between_downloads)
                        
                except Exception as e:
                    print(f"Error downloading image {image.id}: {e}")
                    continue
            
            # Commit all changes
            db.session.commit()
            print(f"Downloaded {downloaded_count} images.")
            return downloaded_count
            
    except Exception as e:
        print(f"Error in batch image download: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return 0


def start_background_image_downloader(interval_seconds=60):
    """Start a background thread that periodically downloads pending images."""
    # Capture the current app instance
    app = current_app._get_current_object()
    
    def background_worker():
        while True:
            try:
                download_pending_images(batch_size=20, delay_between_downloads=0.5, app=app)
                time.sleep(interval_seconds)
            except Exception as e:
                print(f"Background image downloader error: {e}")
                time.sleep(interval_seconds)
    
    thread = threading.Thread(target=background_worker, daemon=True)
    thread.start()
    print(f"Background image downloader started (interval: {interval_seconds}s)")
    return thread


def download_images_for_game(game_uuid, app=None):
    """Download all pending images for a specific game immediately."""
    if app is None:
        app = current_app._get_current_object()
        
    try:
        with app.app_context():
            pending_images = db.session.execute(select(Image).filter_by(game_uuid=game_uuid, is_downloaded=False)).scalars().all()
            
            if not pending_images:
                print(f"No pending images for game {game_uuid}.")
                return 0
            
            downloaded_count = 0
            for image in pending_images:
                try:
                    if not image.download_url:
                        continue
                    
                    save_path = os.path.join(app.config['IMAGE_SAVE_PATH'], image.url)
                    
                    from modules.utils_functions import download_image
                    download_image(image.download_url, save_path)
                    
                    image.is_downloaded = True
                    downloaded_count += 1
                    
                except Exception as e:
                    print(f"Error downloading image {image.id}: {e}")
                    continue
            
            db.session.commit()
            print(f"Downloaded {downloaded_count} images for game {game_uuid}.")
            return downloaded_count
            
    except Exception as e:
        print(f"Error downloading images for game {game_uuid}: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return 0


def download_single_image_worker(image, app):
    """Worker function to download a single image - designed for parallel execution."""
    try:
        if not image.download_url:
            return {'success': False, 'image_id': image.id, 'error': 'No download URL'}
        
        save_path = os.path.join(app.config['IMAGE_SAVE_PATH'], image.url)
        
        from modules.utils_functions import download_image
        download_image(image.download_url, save_path)
        
        return {
            'success': True, 
            'image_id': image.id, 
            'game_uuid': image.game_uuid,
            'image_type': image.image_type,
            'url': image.url
        }
        
    except Exception as e:
        return {'success': False, 'image_id': image.id, 'error': str(e)}


def turbo_download_images(batch_size=100, max_workers=5, app=None):
    """MAXIMUM SPEED parallel image downloading with multiple threads."""
    if app is None:
        app = current_app._get_current_object()
    
    print(f"🚀 TURBO DOWNLOAD MODE ACTIVATED - {max_workers} threads, {batch_size} images, NO MERCY!")
    
    try:
        with app.app_context():
            # Get pending images
            pending_images = db.session.execute(select(Image).filter_by(is_downloaded=False).limit(batch_size)).scalars().all()
            
            if not pending_images:
                print("No pending images to download.")
                return {'downloaded': 0, 'failed': 0, 'message': 'No pending images'}
            
            print(f"Found {len(pending_images)} pending images. UNLEASHING THE THREADS!")
            
            downloaded_count = 0
            failed_count = 0
            successful_images = []
            
            # Create thread pool and submit all download tasks
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all download jobs
                future_to_image = {
                    executor.submit(download_single_image_worker, image, app): image 
                    for image in pending_images
                }
                
                # Process completed downloads as they finish
                for future in as_completed(future_to_image):
                    image = future_to_image[future]
                    try:
                        result = future.result()
                        
                        if result['success']:
                            successful_images.append(image.id)
                            downloaded_count += 1
                            print(f"✅ Downloaded {result['image_type']} for game {result['game_uuid']}: {result['url']}")
                        else:
                            failed_count += 1
                            print(f"❌ Failed to download image {result['image_id']}: {result['error']}")
                            
                    except Exception as e:
                        failed_count += 1
                        print(f"❌ Exception downloading image {image.id}: {e}")
            
            # Update database - mark successful downloads as completed
            if successful_images:
                print(f"Updating database for {len(successful_images)} successful downloads...")
                db.session.execute(
                    update(Image).filter(Image.id.in_(successful_images)).values(is_downloaded=True)
                )
                db.session.commit()
            
            result_message = f"TURBO DOWNLOAD COMPLETE! ✅ {downloaded_count} downloaded, ❌ {failed_count} failed"
            print(result_message)
            
            return {
                'downloaded': downloaded_count,
                'failed': failed_count,
                'message': result_message
            }
            
    except Exception as e:
        print(f"Error in turbo download: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return {'downloaded': 0, 'failed': 0, 'message': f'Error: {str(e)}'}


def start_turbo_background_downloader(interval_seconds=30, max_workers=4, batch_size=50):
    """Start a HIGH SPEED background downloader with parallel processing."""
    app = current_app._get_current_object()
    
    def turbo_background_worker():
        print(f"🔥 TURBO BACKGROUND DOWNLOADER STARTED - {max_workers} workers, {batch_size} batch, {interval_seconds}s interval")
        while True:
            try:
                result = turbo_download_images(batch_size=batch_size, max_workers=max_workers, app=app)
                if result['downloaded'] > 0:
                    print(f"🚀 Background turbo download: {result['message']}")
                time.sleep(interval_seconds)
            except Exception as e:
                print(f"Turbo background downloader error: {e}")
                time.sleep(interval_seconds)
    
    thread = threading.Thread(target=turbo_background_worker, daemon=True)
    thread.start()
    print(f"🔥 TURBO BACKGROUND DOWNLOADER LAUNCHED!")
    return thread


def find_missing_images_for_library(library_uuid=None, app=None):
    """
    Find all images that have URLs in the database but are missing from disk.
    
    Parameters:
    - library_uuid: UUID of library to check (optional, checks all games if None)
    - app: Flask app context (optional)
    
    Returns:
    - Dictionary with statistics and list of missing images
    """
    if app is None:
        app = current_app._get_current_object()
    
    try:
        with app.app_context():
            # Build query based on library filter
            if library_uuid:
                images_query = select(Image).join(Game).filter(Game.library_uuid == library_uuid)
                print(f"🔍 Checking for missing images in library {library_uuid}")
            else:
                images_query = select(Image)
                print(f"🔍 Checking for missing images across all libraries")
            
            # Get all images with download URLs
            all_images = db.session.execute(images_query.filter(Image.download_url.isnot(None))).scalars().all()
            
            if not all_images:
                print("No images with download URLs found in database.")
                return {
                    'total_checked': 0,
                    'missing_count': 0,
                    'missing_images': [],
                    'already_queued': 0
                }
            
            print(f"📊 Found {len(all_images)} images to check")
            
            missing_images = []
            already_queued_count = 0
            
            for image in all_images:
                try:
                    # Check if image is already marked as not downloaded (already in queue)
                    if not image.is_downloaded:
                        already_queued_count += 1
                        continue
                    
                    # Build expected file path
                    image_save_path = os.path.join(app.config['IMAGE_SAVE_PATH'], image.url)
                    
                    # Check if file exists on disk
                    if not os.path.exists(image_save_path):
                        missing_images.append({
                            'id': image.id,
                            'game_uuid': image.game_uuid,
                            'image_type': image.image_type,
                            'url': image.url,
                            'download_url': image.download_url,
                            'file_path': image_save_path
                        })
                        print(f"❌ Missing: {image.image_type} for game {image.game_uuid}: {image.url}")
                    
                except Exception as e:
                    print(f"Error checking image {image.id}: {e}")
                    continue
            
            result = {
                'total_checked': len(all_images),
                'missing_count': len(missing_images),
                'missing_images': missing_images,
                'already_queued': already_queued_count
            }
            
            print(f"📈 Missing images summary: {len(missing_images)} missing, {already_queued_count} already queued, {len(all_images)} total checked")
            return result
            
    except Exception as e:
        print(f"Error in find_missing_images_for_library: {e}")
        return {
            'total_checked': 0,
            'missing_count': 0,
            'missing_images': [],
            'already_queued': 0,
            'error': str(e)
        }


def queue_missing_images_for_download(missing_images_list, app=None):
    """
    Mark missing images as not downloaded so they get picked up by the download queue.
    
    Parameters:
    - missing_images_list: List of missing image dictionaries from find_missing_images_for_library
    - app: Flask app context (optional)
    
    Returns:
    - Number of images successfully queued
    """
    if app is None:
        app = current_app._get_current_object()
    
    if not missing_images_list:
        print("No missing images to queue.")
        return 0
    
    try:
        with app.app_context():
            queued_count = 0
            image_ids = [img['id'] for img in missing_images_list]
            
            # Update images to mark them as not downloaded (queued for download)
            db.session.execute(
                update(Image).filter(Image.id.in_(image_ids)).values(is_downloaded=False)
            )
            updated_count = len(image_ids)
            
            db.session.commit()
            queued_count = updated_count
            
            print(f"📥 Successfully queued {queued_count} missing images for download")
            
            # Trigger immediate download if turbo mode is enabled
            settings = db.session.execute(select(GlobalSettings)).scalar_one_or_none()
            if settings and settings.use_turbo_image_downloads:
                print(f"🚀 Turbo mode enabled - triggering immediate download")
                # Run a small batch download to start processing immediately
                download_result = turbo_download_images(
                    batch_size=min(20, queued_count), 
                    max_workers=settings.turbo_download_threads or 4, 
                    app=app
                )
                print(f"⚡ Quick download result: {download_result.get('message', 'Download initiated')}")
            
            return queued_count
            
    except Exception as e:
        print(f"Error queuing missing images: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return 0


def process_missing_images_for_scan(library_uuid=None, app=None):
    """
    Complete workflow to find and queue missing images for download during scan.
    
    Parameters:
    - library_uuid: UUID of library to process (optional, processes all if None)
    - app: Flask app context (optional)
    
    Returns:
    - Dictionary with results summary
    """
    if app is None:
        app = current_app._get_current_object()
    
    print(f"🔍 Starting missing images processing for library: {library_uuid or 'ALL'}")
    
    # Step 1: Find missing images
    missing_result = find_missing_images_for_library(library_uuid, app)
    
    if missing_result.get('error'):
        return {
            'success': False,
            'error': missing_result['error'],
            'found': 0,
            'queued': 0
        }
    
    # Step 2: Queue missing images if any found
    queued_count = 0
    if missing_result['missing_count'] > 0:
        queued_count = queue_missing_images_for_download(missing_result['missing_images'], app)
    
    result = {
        'success': True,
        'total_checked': missing_result['total_checked'],
        'found': missing_result['missing_count'],
        'queued': queued_count,
        'already_queued': missing_result['already_queued'],
        'message': f"Found {missing_result['missing_count']} missing images, queued {queued_count} for download"
    }
    
    print(f"✅ Missing images processing complete: {result['message']}")
    return result
