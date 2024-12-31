from datetime import datetime
from flask import flash, current_app, abort
from flask_login import current_user
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.utils import secure_filename
import os, uuid

from modules import db
from modules.models import (
    Game, Image, Library, GlobalSettings,
    Developer, Publisher, Genre, Theme, GameMode, Platform, 
    PlayerPerspective, GameURL, ScanJob, 
    category_mapping, status_mapping, player_perspective_mapping
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

def create_game_instance(game_data, full_disk_path, folder_size_bytes, library_uuid):
    global settings
    settings = GlobalSettings.query.first()
    
    try:
        if not isinstance(game_data, dict):
            raise ValueError("create_game_instance game_data is not a dictionary")

        # Fetch library details using library_uuid
        library = Library.query.filter_by(uuid=library_uuid).first()
        if not library:
            print(f"Library with UUID {library_uuid} not found.")
            return None

        category_id = game_data.get('category')
        category_enum = category_mapping.get(category_id, None)
        status_id = game_data.get('status')
        status_enum = status_mapping.get(status_id, None)
        player_perspective_id = game_data.get('player_perspective')
        player_perspective_enum = player_perspective_mapping.get(player_perspective_id, None)
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
            first_release_date=datetime.utcfromtimestamp(game_data.get('first_release_date', 0)) if game_data.get('first_release_date') else None,
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
            date_created=datetime.utcnow(),
            date_identified=datetime.utcnow(),
            steam_url='',
            times_downloaded=0
        )
        
        db.session.add(new_game)
        db.session.flush()        
        fetch_and_store_game_urls(new_game.uuid, game_data['id'])
        print(f"create_game_instance Finished processing game '{new_game.name}'. URLs (if any) have been fetched and stored.")
        
        # Send Discord notification if enabled
        if settings and settings.discord_webhook_url and settings.discord_notify_new_games:
            print(f"Sending Discord notification for new game '{new_game.name}'.")
            discord_webhook(new_game.uuid)
        
    except Exception as e:
        print(f"create_game_instance Error during the game instance creation or URL fetching for game '{game_data.get('name')}'. Error: {e}")
    
    return new_game



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
    print(f"retrieve_and_save_game Retrieving and saving game: {game_name} on {full_disk_path} to library with UUID {library_uuid}.")
    library = Library.query.filter_by(uuid=library_uuid).first()
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
        existing_game_with_same_igdb_id = Game.query.filter(Game.igdb_id == igdb_id, Game.full_disk_path != full_disk_path).first()
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
            
                    
            if 'genres' in response_json[0]:
                for genre_data in response_json[0]['genres']:
                    genre_name = genre_data['name']
                    genre = Genre.query.filter_by(name=genre_name).first()
                    if not genre:
                        genre = Genre(name=genre_name)
                        db.session.add(genre)
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
                    
                    theme = Theme.query.filter_by(name=theme_name).first()
                    if not theme:
                        
                        theme = Theme(name=theme_name)
                        db.session.add(theme)
                    
                    new_game.themes.append(theme)

            if 'game_modes' in response_json[0]:
                for game_mode_data in response_json[0]['game_modes']:
                    game_mode_name = game_mode_data['name']
                    
                    game_mode = GameMode.query.filter_by(name=game_mode_name).first()
                    if not game_mode:
                        
                        game_mode = GameMode(name=game_mode_name)
                        db.session.add(game_mode)
                        db.session.flush()

                    new_game.game_modes.append(game_mode)

            if 'platforms' in response_json[0]:
                for platform_data in response_json[0]['platforms']:
                    platform_name = platform_data['name']
                    platform = Platform.query.filter_by(name=platform_name).first()
                    if not platform:
                        platform = Platform(name=platform_name)
                        db.session.add(platform)
                    new_game.platforms.append(platform)
                    
            if 'player_perspectives' in response_json[0]:
                for perspective_data in response_json[0]['player_perspectives']:
                    perspective_name = perspective_data['name']
                    perspective = PlayerPerspective.query.filter_by(name=perspective_name).first()
                    if not perspective:
                        perspective = PlayerPerspective(name=perspective_name)
                        db.session.add(perspective)
                    new_game.player_perspectives.append(perspective)
                    
            if 'videos' in response_json[0]:
                video_urls = [f"https://www.youtube.com/embed/{video['video_id']}" for video in response_json[0]['videos']]
                videos_comma_separated = ','.join(video_urls)
                new_game.video_urls = videos_comma_separated
            
            db.session.commit()
            print(f"Processing images for game: {new_game.name}.")
            if 'cover' in response_json[0]:
                process_and_save_image(new_game.uuid, response_json[0]['cover'], 'cover')
            db.session.commit()
            for screenshot_id in response_json[0].get('screenshots', []):
                process_and_save_image(new_game.uuid, screenshot_id, 'screenshot')
            db.session.commit()
            try:
                new_game.nfo_content = nfo_content
                for column in new_game.__table__.columns:
                    attr = getattr(new_game, column.name)
                db.session.commit()
                print(f"Game and its images saved successfully : {new_game.name}.")
            except IntegrityError as e:
                db.session.rollback()
                print(f"Failed to save game due to a database error: {e}")
                flash("Failed to save game due to a duplicate entry.")
            return new_game
    else:
        if 'error' in response_json:
            # Check specifically for authentication error
            if response_json.get('error') == 'Failed to retrieve access token':
                error_msg = 'IGDB API Authentication Failed'
                if scan_job_id:
                    scan_job = ScanJob.query.get(scan_job_id)
                    if scan_job:
                        scan_job.error_message = error_msg
                        scan_job.status = 'Failed'
                        db.session.commit()
                
                log_system_event(f"IGDB API Authentication Failed: {response_json.get('error')}", 
                                 event_type='scan', event_level='error')
                return None
            
        print(f"No match found: {game_name} in library {library.name} on platform {library.platform.name}.")
        flash("No game data found for the given name.")
        return None
    
def check_existing_game_by_path(full_disk_path):
    """
    Checks if a game already exists in the library by its disk path.

    Parameters:
    - full_disk_path: The full disk path of the game to check.

    Returns:
    - The existing Game object if found, None otherwise.
    """
    existing_game_by_path = Game.query.filter_by(full_disk_path=full_disk_path).first()
    if existing_game_by_path:
        print(f"Skipping {existing_game_by_path.name} on {full_disk_path} (path already in library).")
        return existing_game_by_path 
    return None

def check_existing_game_by_igdb_id(igdb_id):
    return Game.query.filter_by(igdb_id=igdb_id).first()


def enumerate_companies(game_instance, igdb_game_id, involved_company_ids):
    print(f"Enumerating companies for game {game_instance.name} with IGDB ID {igdb_game_id}.")
    if not involved_company_ids:
        print("No company IDs provided for enumeration.")
        return

    company_ids_str = ','.join(map(str, involved_company_ids))
    print(f"Company IDs: {company_ids_str}")

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
                print(f"Company {company_name} is a developer.")
                developer = Developer.query.filter_by(name=company_name).first()
                if not developer:
                    print(f"Creating new developer: {company_name}")
                    developer = Developer(name=company_name)
                    db.session.add(developer)

                print(f"Assigning developer {developer.name} to game {game_instance.name}.")
                game_instance.developer = developer

            if is_publisher:
                print(f"Company {company_name} is a publisher.")
                publisher = Publisher.query.filter_by(name=company_name).first()
                if not publisher:
                    publisher = Publisher(name=company_name)
                    db.session.add(publisher)
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
    print(f"Searching for game UUID: {game_uuid}")
    game = Game.query.filter_by(uuid=game_uuid).first()
    if game:
        print(f"Game ID {game.id} with name {game.name} and UUID {game.uuid} relating to IGDB ID {game.igdb_id} found")
        return game
    else:
        print("Game not found")
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
        game = Game.query.filter_by(uuid=game_uuid).first()
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
            game_to_delete = Game.query.filter_by(uuid=game_uuid_str).first_or_404()
        except ValueError:
            print(f"Invalid UUID format: {game_identifier}")
            abort(404)
        except Exception as e:
            print(f"Error fetching game with UUID {game_uuid_str}: {e}")
            abort(404)

    try:
        print(f"Found game to delete: {game_to_delete}")
        GameURL.query.filter_by(game_uuid=game_uuid_str).delete()
        delete_associations_for_game(game_to_delete)        
        delete_game_images(game_uuid_str)
        db.session.delete(game_to_delete)
        db.session.commit()
        flash('Game and its images have been deleted successfully.', 'success')
        print(f'Deleted game with UUID: {game_uuid_str}')
    except Exception as e:
        db.session.rollback()
        print(f'Error deleting game with UUID {game_uuid_str}: {e}')
        flash(f'Error deleting game: {e}', 'error')
