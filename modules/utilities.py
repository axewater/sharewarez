#/modules/utilities.py
import re, requests, os, zipfile, time, traceback
from functools import wraps
from flask import flash, redirect, url_for, request, current_app, flash
from flask_login import current_user, login_user
from datetime import datetime
from werkzeug.urls import url_parse
from werkzeug.utils import secure_filename
from modules.utils_functions import (
    format_size, read_first_nfo_content,
    download_image
)
from modules.models import (
    User, Game, Image, DownloadRequest, Platform, Genre, 
    Publisher, Developer, GameURL, Library, GameUpdate, AllowedFileType, 
    Theme, GameMode, PlayerPerspective, ScanJob, UnmatchedFolder, GameExtra,
    category_mapping, status_mapping, player_perspective_mapping, GlobalSettings
)
from modules import db, mail
from modules.utils_functions import website_category_to_string, PLATFORM_IDS, load_release_group_patterns, get_folder_size_in_bytes_updates
from modules.utils_discord import discord_webhook, discord_update
from modules.utils_gamenames import get_game_names_from_folder, get_game_names_from_files
from modules.utils_igdb_api import make_igdb_api_request, get_cover_url
from sqlalchemy import func, String
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from flask import current_app
from PIL import Image as PILImage
from datetime import datetime
from wtforms.validators import ValidationError


def _authenticate_and_redirect(username, password):
    user = User.query.filter(func.lower(User.name) == func.lower(username)).first()
    
    if user and user.check_password(password):
        # If the password is correct and is using bcrypt, rehash it with Argon2
        if not user.password_hash.startswith('$argon2'):
            user.rehash_password(password)
            db.session.commit()

        user.lastlogin = datetime.utcnow()
        db.session.commit()
        login_user(user, remember=True)
        
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.discover')
        return redirect(next_page)
    else:
        flash('Invalid username or password', 'error')
        return redirect(url_for('main.login'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("You must be an admin to access this page.", "danger")
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

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
            discord_webhook(new_game.uuid)
        
    except Exception as e:
        print(f"create_game_instance Error during the game instance creation or URL fetching for game '{game_data.get('name')}'. Error: {e}")
    
    return new_game



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
    

    
def retrieve_and_save_game(game_name, full_disk_path, scan_job_id=None, library_uuid=None):
    print(f"rns Retrieving and saving game: {game_name} on {full_disk_path} to library with UUID {library_uuid}.")
    # Fetch the library using the UUID
    library = Library.query.filter_by(uuid=library_uuid).first()
    if not library:
        print(f"rns Library with UUID {library_uuid} not found.")
        return None
    
    print(f"rns Finding a way to add {game_name} on {full_disk_path} to the library with UUID {library_uuid}.")

    existing_game_by_path = check_existing_game_by_path(full_disk_path)
    if existing_game_by_path:
        return existing_game_by_path 

    print(f"rns No existing game found for {game_name} on {full_disk_path}. Proceeding to retrieve game data from IGDB API.")
    platform_id = PLATFORM_IDS.get(library.platform.name)
    print(f"rns Platform ID for {library.platform.name}: {platform_id}")
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
        if scan_job_id:
            pass
        print(f"IGDB match failed: {game_name} in library {library.name} on platform {library.platform.name}.")
        error_message = "No game data found for the given name or failed to retrieve data from IGDB API."
        flash(error_message)
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

    

def process_game_updates(game_name, full_disk_path, updates_folder, library_uuid):
    settings = GlobalSettings.query.first()
    if not settings or not settings.update_folder_name:
        print("No update folder configuration found in database")
        return

    print(f"Processing updates for game: {game_name}")
    print(f"Full disk path: {full_disk_path}")
    print(f"Updates folder: {updates_folder}")
    print(f"Library UUID: {library_uuid}")

    game = Game.query.filter_by(full_disk_path=full_disk_path, library_uuid=library_uuid).first()
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
        game_update = GameUpdate.query.filter_by(game_uuid=game.uuid, file_path=file_path).first()
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


def process_game_extras(game_name, full_disk_path, extras_folder, library_uuid):
    settings = GlobalSettings.query.first()
    if not settings or not settings.extras_folder_name:
        print("No extras folder configuration found in database")
        return

    print(f"Processing extras for game: {game_name}")
    print(f"Full disk path: {full_disk_path}")
    print(f"Extras folder: {extras_folder}")
    print(f"Library UUID: {library_uuid}")

    game = Game.query.filter_by(full_disk_path=full_disk_path, library_uuid=library_uuid).first()
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
        game_extra = GameExtra.query.filter_by(game_uuid=game.uuid, file_path=extra_path).first()
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
                continue  # Skip to the next iteration

            company_name = company_info['name'][:50]  # Safely access 'name' and truncate to 50 characters

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
        zip_file_path = zip_file_path

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
    download_request.completion_time = datetime.utcnow()
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
                    
            zip_file_path = os.path.join(zip_save_path, f"{file_name}.zip")
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

        
def check_existing_game_by_igdb_id(igdb_id):
    return Game.query.filter_by(igdb_id=igdb_id).first()

def log_unmatched_folder(scan_job_id, folder_path, matched_status, library_uuid=None):
    existing_unmatched_folder = UnmatchedFolder.query.filter_by(folder_path=folder_path).first()

    if existing_unmatched_folder is None:
        unmatched_folder = UnmatchedFolder(
            folder_path=folder_path,
            failed_time=datetime.utcnow(),
            content_type='Games',
            library_uuid=library_uuid,
            status=matched_status
        )
        try:
            db.session.add(unmatched_folder)
            db.session.commit()
            print(f"Logged unmatched folder: {folder_path}")
        except IntegrityError:
            db.session.rollback()
            print(f"Failed to log unmatched folder due to a database error: {folder_path}")
    else:
        print(f"Unmatched folder already logged for: {folder_path}. Skipping.")

def refresh_images_in_background(game_uuid):
    with current_app.app_context():
        game = Game.query.filter_by(uuid=game_uuid).first()
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
                flash("Game images refreshed successfully.", "success")
            else:
                flash("Failed to retrieve game images from IGDB API.", "error")

        except Exception as e:
            db.session.rollback()
            flash(f"Failed to refresh game images: {str(e)}", "error")
            
def delete_game_images(game_uuid):
    with current_app.app_context():
        game = Game.query.filter_by(uuid=game_uuid).first()
        if not game:
            print("Game not found for image deletion.")
            return

        images_to_delete = Image.query.filter_by(game_uuid=game_uuid).all()

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
        
        print(f"Successfully removed game {game.name} (UUID: {game_uuid}) from library")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error removing game from library: {str(e)}")
        return False






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

        
def process_game_with_fallback(game_name, full_disk_path, scan_job_id, library_uuid):
    # Fetch library details based on library_uuid
    library = Library.query.filter_by(uuid=library_uuid).first()
    if not library:
        print(f"Library with UUID {library_uuid} not found.")
        return False

    # Log skipping of processing for already matched or unmatched folders
    existing_unmatched_folder = UnmatchedFolder.query.filter_by(folder_path=full_disk_path).first()
    if existing_unmatched_folder:
        print(f"Skipping processing for already logged unmatched folder: {full_disk_path}")
        return False

    # Check if the game already exists in the database
    existing_game = Game.query.filter_by(full_disk_path=full_disk_path, library_uuid=library_uuid).first()
    if existing_game:
        print(f"Game already exists in database: {game_name} at {full_disk_path}")
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



def try_add_game(game_name, full_disk_path, scan_job_id, library_uuid, check_exists=True):
    print(f"try_add_game: {game_name} at {full_disk_path} with scan job ID: {scan_job_id}, check_exists: {check_exists}, and library UUID: {library_uuid}")
    
    # Fetch the library details using the library_uuid, if necessary
    library = Library.query.filter_by(uuid=library_uuid).first()
    if not library:
        print(f"Library with UUID {library_uuid} not found.")
        return False

    if check_exists:
        existing_game = Game.query.filter_by(full_disk_path=full_disk_path).first()
        if existing_game:
            print(f"Game already exists in database: {game_name} at {full_disk_path}")
            return False

    game = retrieve_and_save_game(game_name, full_disk_path, scan_job_id, library_uuid)
    return game is not None