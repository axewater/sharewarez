#/modules/utilities.py
import re, requests, shutil, os
from functools import wraps
from flask import flash, redirect, url_for, request, current_app, flash
from flask_login import current_user, login_user
from flask_mail import Message as MailMessage
from datetime import datetime
from werkzeug.urls import url_parse
from werkzeug.utils import secure_filename
from modules.models import (
    User, User, Whitelist, ReleaseGroup, Game, Image, DownloadRequest, Platform, Genre, Publisher, Developer, 
    Theme, GameMode, MultiplayerMode, PlayerPerspective, ScanJob, UnmatchedFolder, category_mapping, status_mapping, player_perspective_mapping
)
from modules import db, mail
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from PIL import Image as PILImage
from PIL import ImageOps
from datetime import datetime
from wtforms.validators import ValidationError



def _authenticate_and_redirect(username, password):
    user = User.query.filter(func.lower(User.name) == func.lower(username)).first()
    if user is None or not user.check_password(password):
        flash('Invalid username or password')
        return redirect(url_for('main.login'))

    user.lastlogin = datetime.utcnow()
    db.session.commit()
    login_user(user, remember=True)
    next_page = request.args.get('next')
    if not next_page or url_parse(next_page).netloc != '':
        next_page = url_for('site.restricted')
    return redirect(next_page)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("You must be an admin to access this page.", "danger")
            return redirect(url_for('main.index'))  # Adjust if necessary
        return f(*args, **kwargs)
    return decorated_function



def create_game_instance(game_data, full_disk_path, folder_size_mb):
            
    category_id = game_data.get('category')
    category_enum = category_mapping.get(category_id, None)
    status_id = game_data.get('status')
    status_enum = status_mapping.get(status_id, None)
    player_perspective_id = game_data.get('player_perspective')
    player_perspective_enum = player_perspective_mapping.get(player_perspective_id, None)
    # Convert video IDs to YouTube URLs and concatenate into a comma-separated string
    if 'videos' in game_data:
        video_urls = [f"https://www.youtube.com/watch?v={video['video_id']}" for video in game_data['videos']]
        videos_comma_separated = ','.join(video_urls)
    else:
        videos_comma_separated = ""
    new_game = Game(
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
        size=folder_size_mb
    )
    
    db.session.add(new_game)
    db.session.flush()
    return new_game


def process_and_save_image(game_uuid, image_data, image_type='cover'):
    url = None
    save_path = None
    # print(f"Processing and saving {image_type} image for game {game_uuid} with UUID {image_data}.")
    if image_type == 'cover':
        # print(f"Processing cover image for game {game_uuid}.")
        cover_query = f'fields url; where id={image_data};'
        cover_response = make_igdb_api_request('https://api.igdb.com/v4/covers', cover_query)
        # print(f'Cover response: {cover_response}')
        if cover_response and 'error' not in cover_response:
            url = cover_response[0].get('url')
            if not url:
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
            if not url:
                print(f"Screenshot URL not found for ID {image_data}.")
                return
            file_name = secure_filename(f"{game_uuid}_{image_data}.jpg") 
            save_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], file_name)
            download_image(url, save_path)

    image = Image(
        game_uuid=game_uuid,
        image_type=image_type,
        url=file_name, 
    )
    db.session.add(image)
    
def retrieve_and_save_game(game_name, full_disk_path, scan_job_id=None):
    print(f"retrieve_and_save_game for {game_name} with full disk path {full_disk_path}.")
    existing_game_by_path = Game.query.filter_by(full_disk_path=full_disk_path).first()
    if existing_game_by_path:
        print(f"Game already exists in the database with full disk path: {full_disk_path}. Skipping.")
        return existing_game_by_path 

    response_json = make_igdb_api_request(current_app.config['IGDB_API_ENDPOINT'],
        f"""fields id, name, cover, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name,
                   screenshots, videos.video_id, first_release_date, aggregated_rating, involved_companies, player_perspectives.name,
                   aggregated_rating_count, rating, rating_count, slug, status, category, total_rating, 
                   total_rating_count;
            search "{game_name}"; limit 1;
        """)
    # print(f"retrieve_and_save Response JSON: {response_json}")
    if 'error' not in response_json and response_json:

        igdb_id = response_json[0].get('id')


        existing_game = check_existing_game_by_igdb_id(igdb_id)
        if existing_game:
            print(f"Game with IGDB ID {igdb_id} already exists in the database.")
            flash(f"Game '{game_name}' already exists in the database.")
            return existing_game
        else:
            print(f"Calculating folder size for {full_disk_path}.")
            folder_size_mb = get_folder_size_in_mb(full_disk_path)
            print(f"Folder size for {full_disk_path}: {folder_size_mb} MB.")
            new_game = create_game_instance(game_data=response_json[0], full_disk_path=full_disk_path, folder_size_mb=folder_size_mb)
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
                    print("No involved companies found for this game.")

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

            
            if 'cover' in response_json[0]:
                process_and_save_image(new_game.uuid, response_json[0]['cover'], 'cover')
            
            for screenshot_id in response_json[0].get('screenshots', []):
                process_and_save_image(new_game.uuid, screenshot_id, 'screenshot')
            
            try:
                for column in new_game.__table__.columns:
                    attr = getattr(new_game, column.name)

                db.session.commit()
                print(f"retrieve_and_save_game Game and its images saved successfully : {new_game.name}.")
                flash("Game and its images saved successfully.")
            except IntegrityError as e:
                db.session.rollback()
                print(f"retrieve_and_save_game Failed to save game due to a database error: {e}")
                flash("Failed to save game due to a duplicate entry.")
            return new_game
    else:
        if scan_job_id:
            print(f"PLACEHOLDER retrieve_and_save_game Scan job ID: {scan_job_id}")
        print(f"retrieve_and_save_game Failed to find game: {game_name} using IGDB API.")
        error_message = "No game data found for the given name or failed to retrieve data from IGDB API."
        # print(error_message)
        flash(error_message)
        return None

def get_folder_size_in_mb(folder_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
    return total_size / (1024 * 1024)

def enumerate_companies(game_instance, igdb_game_id, involved_company_ids):
    #print(f"Enumerating companies for game with IGDB ID {igdb_game_id}.")
    company_ids_str = ','.join(map(str, involved_company_ids))

    # print(f"Company IDs: {company_ids_str}")
    response_json = make_igdb_api_request(
        "https://api.igdb.com/v4/involved_companies",
        f"""fields company.name, developer, publisher, game;
            where game={igdb_game_id} & id=({company_ids_str});"""
    )
    # print(f"Companies Response JSON: {response_json}")
    
    for company in response_json:
        company_name = company['company']['name']
        is_developer = company.get('developer', False)
        is_publisher = company.get('publisher', False)

        if is_developer:
            # print(f"Company {company_name} is a developer.")
            developer = Developer.query.filter_by(name=company_name).first()
            if not developer:
                developer = Developer(name=company_name)
                db.session.add(developer)
            
            game_instance.developer = developer
        
        if is_publisher:
            
            publisher = Publisher.query.filter_by(name=company_name).first()
            if not publisher:
                publisher = Publisher(name=company_name)
                db.session.add(publisher)
            game_instance.publisher = publisher

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Failed to enumerate companies due to a database error: {e}")


def make_igdb_api_request(endpoint_url, query_params):
    client_id = current_app.config['IGDB_CLIENT_ID']
    client_secret = current_app.config['IGDB_CLIENT_SECRET']
    access_token = get_access_token(client_id, client_secret) 

    if not access_token:
        return {"error": "Failed to retrieve access token"}

    headers = {
        'Client-ID': client_id,
        'Authorization': f"Bearer {access_token}"
    }

    try:
        # print(f"Making API request to {endpoint_url} with query params: {query_params}")
        response = requests.post(endpoint_url, headers=headers, data=query_params)
        response.raise_for_status()
        data = response.json()
        # print(f"API request successful: {json.dumps(data, indent=4)}")
        return response.json()

    except requests.RequestException as e:
        return {"error": f"API Request failed: {e}"}

    except ValueError:
        return {"error": "Invalid JSON in response"}

    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

def download_image(url, save_path):
    if not url.startswith(('http://', 'https://')):
        url = 'https:' + url

    
    url = url.replace('/t_thumb/', '/t_original/')

    # print(f"Downloading image from {url}.")
    response = requests.get(url)
    if response.status_code == 200:
        # print(f"Image downloaded successfully to {save_path}.")
        with open(save_path, 'wb') as f:
            f.write(response.content)
    else:
        print(f"Failed to download the image. Status Code: {response.status_code}")

def zip_game(download_request_id, app):
    with app.app_context():
        download_request = DownloadRequest.query.get(download_request_id)
        game = download_request.game
        print(f"Zipping game: {game.name}")
        if not game:
            print(f"No game found for DownloadRequest ID: {download_request_id}")
            return
        
        zip_save_path = app.config['ZIP_SAVE_PATH']
        output_zip_base = os.path.join(zip_save_path, game.uuid)
        source_folder = game.full_disk_path
        
        if not os.path.exists(source_folder):
            print(f"Source folder does not exist: {source_folder}")
            return
        
        try:
            print(f"Zipping game folder: {source_folder} to {output_zip_base}.")
            output_zip = shutil.make_archive(output_zip_base, 'zip', source_folder)
            print(f"Archive created at {output_zip}")
                        
            download_request.status = 'available'
            download_request.zip_file_path = output_zip
            download_request.completion_time = datetime.utcnow()
            print(f"Download request updated: {download_request}")
            db.session.commit()
        except Exception as e:
            error_message = str(e)
            print(f"An error occurred while zipping: {error_message}")

            download_request.status = 'failed'
            download_request.zip_file_path = error_message
            db.session.commit()
            print(f"Failed to zip game for DownloadRequest ID: {download_request_id}, Error: {error_message}")
   
        
def check_existing_game_by_igdb_id(igdb_id):
    return Game.query.filter_by(igdb_id=igdb_id).first()



def log_unmatched_folder(scan_job_id, folder_path):
    # Check if there's already an unmatched folder logged for this specific folder path, regardless of the scan job ID
    existing_unmatched_folder = UnmatchedFolder.query.filter_by(folder_path=folder_path).first()

    if existing_unmatched_folder is None:
        # No existing log for this folder path, proceed to log it
        unmatched_folder = UnmatchedFolder(
            folder_path=folder_path,
            failed_time=datetime.utcnow(),
            content_type='Games',
            status='Pending'
        )
        try:
            db.session.add(unmatched_folder)
            db.session.commit()
            print(f"Logged unmatched folder: {folder_path}")
        except IntegrityError:
            # Handle any potential IntegrityError (e.g., concurrent write attempt)
            db.session.rollback()
            print(f"Failed to log unmatched folder due to a database error: {folder_path}")
    else:
        # An unmatched folder log already exists for this path, skip logging
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

def square_image(image, size):
    image.thumbnail((size, size))
    if image.size[0] != size or image.size[1] != size:
        new_image = PILImage.new('RGB', (size, size), color='black')
        offset = ((size - image.size[0]) // 2, (size - image.size[1]) // 2)
        new_image.paste(image, offset)
        image = new_image
    return image


def get_game_by_uuid(game_uuid):
    print(f"Searching for game UUID: {game_uuid}")
    game = Game.query.filter_by(uuid=game_uuid).first()
    if game:
        print(f"Game ID {game.id} with name {game.name} and UUID {game.uuid} relating to IGDB ID {game.igdb_id} found")
        return game
    else:
        print("Game not found")
        return None

def escape_special_characters(pattern):
    return re.escape(pattern)


def send_email(to, subject, template):
    msg = MailMessage(
        subject,
        sender='halliday@pleasewaitloading.com',
        recipients=[to],
        html=template
    )
    mail.send(msg)

def send_password_reset_email(user_email, token):
    reset_url = url_for('main.reset_password', token=token, _external=True)
    msg = MailMessage(
        'Password Reset Request',
        sender='halliday@sharewarez.pleasewaitloading.com',  # Replace with your actual sender email
        recipients=[user_email],
        body=f'Please click on the link to reset your password: {reset_url}'
    )
    mail.send(msg)


def get_access_token(client_id, client_secret):
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, params=params)
    if response.status_code == 200:
        return response.json()['access_token']
        # print("Access token obtained successfully")
    else:
        print("Failed to obtain access token")
        return None

def get_cover_thumbnail_url(igdb_id):
    """
    Takes an IGDB ID number and returns the URL to the cover thumbnail.

    Parameters:
    igdb_id (int): The IGDB ID of the game.

    Returns:
    str: The URL of the cover thumbnail, or None if not found.
    """
    cover_query = f'fields url; where game={igdb_id};'
    response = make_igdb_api_request('https://api.igdb.com/v4/covers', cover_query)

    if response and 'error' not in response and len(response) > 0:
        cover_url = response[0].get('url')
        if cover_url:

            return 'https:' + cover_url
        else:
            print(f"No cover URL found for IGDB ID {igdb_id}.")
    else:
        print(f"Failed to retrieve cover for IGDB ID {igdb_id}. Response: {response}")

    return None

def scan_and_add_games(folder_path):
    print(f"Starting scan for games in folder: {folder_path}")
    if not os.path.exists(folder_path) or not os.access(folder_path, os.R_OK):
        print(f"Error: Cannot access folder at path {folder_path}")
        return

    insensitive_patterns, sensitive_patterns = load_release_group_patterns()
    
    game_names_with_paths = get_game_names_from_folder(folder_path, insensitive_patterns, sensitive_patterns)
    
    scan_job_entry = ScanJob(folders={folder_path:True}, content_type='Games', status='Running', is_enabled=True, last_run=datetime.now())
    try:
        db.session.add(scan_job_entry)
        db.session.commit()
    except SQLAlchemyError as e:
        print(f"Failed to add ScanJob: {str(e)}")
        return
    
    scan_job_id = scan_job_entry.id
    for game_info in game_names_with_paths:
        game_name = game_info['name']
        full_disk_path = game_info['full_path']
        
        # Attempt to process the game with fallback logic
        success = process_game_with_fallback(game_name, full_disk_path, scan_job_id)
        if success:
            pass
        else:
            print(f"Failed to add game {game_name} after fallback attempts.")

    scan_job_entry.status = 'Completed'
    print(f"Scan completed for folder: {folder_path} with ScanJob ID: {scan_job_id}")
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        print(f"Failed to update ScanJob status: {str(e)}")
        
def process_game_with_fallback(game_name, full_disk_path, scan_job_id):
    # Check if the game exists before attempting fallback logic
    existing_game = Game.query.filter_by(full_disk_path=full_disk_path).first()
    if existing_game:
        print(f"Game already exists in database: {game_name} at {full_disk_path}")
        return True  # Returning True because the game is already in the database, hence no need to add

    # If game does not exist, proceed with adding it, including fallback logic
    if not try_add_game(game_name, full_disk_path, scan_job_id, check_exists=False):  # Note the check_exists parameter
        parts = game_name.split()
        for i in range(len(parts) - 1, 1, -1):  # Adjusted to stop when only one word is left
            fallback_name = ' '.join(parts[:i])
            if try_add_game(fallback_name, full_disk_path, scan_job_id, check_exists=False):
                return True
    else:
        return True  # Initial try was successful
    log_unmatched_folder(scan_job_id, full_disk_path)
    return False  # All fallback attempts failed

def try_add_game(game_name, full_disk_path, scan_job_id, check_exists=True):
    """
    Attempt to add a game to the database. Now includes a check_exists flag to skip redundant checks.
    """
    if check_exists:
        existing_game = Game.query.filter_by(full_disk_path=full_disk_path).first()
        if existing_game:
            print(f"Game already exists in database: {game_name} at {full_disk_path}")
            return False

    # Process of adding the game remains unchanged
    game = retrieve_and_save_game(game_name, full_disk_path, scan_job_id)
    return game is not None

def get_game_names_from_folder(folder_path, insensitive_patterns, sensitive_patterns):
    print(f"Processing folder: {folder_path}")
    if not os.path.exists(folder_path) or not os.access(folder_path, os.R_OK):
        print(f"Error: The folder '{folder_path}' does not exist or is not readable.")
        flash(f"Error: The folder '{folder_path}' does not exist or is not readable.")
        return []

    folder_contents = os.listdir(folder_path)
    # print("Folder contents before filtering:", folder_contents)

    game_names_with_paths = []
    for item in folder_contents:
        full_path = os.path.join(folder_path, item)
        if os.path.isdir(full_path):
            game_name = clean_game_name(item, insensitive_patterns, sensitive_patterns)
            game_names_with_paths.append({'name': game_name, 'full_path': full_path})

    # print("Extracted game names with paths:", game_names_with_paths)
    return game_names_with_paths



import re

def escape_special_characters(pattern):
    """Escape special characters in the pattern to prevent regex errors."""
    return re.escape(pattern)


    


def clean_game_name(filename, insensitive_patterns, sensitive_patterns):
    # Step 1: Normalize separators for release group processing
    # Replace underscores and dots with spaces for easier pattern matching
    # Note: This step assumes dots not part of essential abbreviations or numeric versions are separators
    filename = re.sub(r'(?<!\b[A-Z])\.(?![A-Z]\b)|_', ' ', filename)

    # Step 2: Remove known release group patterns
    for pattern in insensitive_patterns:
        escaped_pattern = escape_special_characters(pattern)
        filename = re.sub(f"\\b{escaped_pattern}\\b", '', filename, flags=re.IGNORECASE)

    for pattern, is_case_sensitive in sensitive_patterns:
        escaped_pattern = escape_special_characters(pattern)
        if is_case_sensitive:
            filename = re.sub(f"\\b{escaped_pattern}\\b", '', filename)
        else:
            filename = re.sub(f"\\b{escaped_pattern}\\b", '', filename, flags=re.IGNORECASE)

    # Step 3: Additional cleanup for version numbers, DLC mentions, etc.
    filename = re.sub(r'\bv\d+(\.\d+)*', '', filename)  # Version numbers
    filename = re.sub(r'Build\.\d+', '', filename)      # Build numbers
    filename = re.sub(r'(\+|\-)\d+DLCs?', '', filename, flags=re.IGNORECASE)  # DLC mentions
    filename = re.sub(r'Repack|Edition|Remastered|Remake|Proper|Dodi', '', filename, flags=re.IGNORECASE)

    # Step 4: Normalize whitespace and re-title
    filename = re.sub(r'\s+', ' ', filename).strip()
    cleaned_name = ' '.join(filename.split()).title()

    return cleaned_name


from sqlalchemy.exc import SQLAlchemyError

def load_release_group_patterns():
    try:
        # Assuming ReleaseGroup is a model that contains release group information
        # Fetching insensitive patterns (not case-sensitive)
        insensitive_patterns = [
            "-" + rg.rlsgroup for rg in ReleaseGroup.query.filter(ReleaseGroup.rlsgroup != None).all()
        ] + [
            "." + rg.rlsgroup for rg in ReleaseGroup.query.filter(ReleaseGroup.rlsgroup != None).all()
        ]
        
        # Initializing list for sensitive patterns (case-sensitive)
        sensitive_patterns = []
        for rg in ReleaseGroup.query.filter(ReleaseGroup.rlsgroupcs != None).all():
            pattern = rg.rlsgroupcs
            is_case_sensitive = False
            if pattern.lower() == 'yes':
                is_case_sensitive = True
                pattern = "-" + rg.rlsgroup  # Assume the pattern needs to be prefixed for sensitive matches
                sensitive_patterns.append((pattern, is_case_sensitive))
                pattern = "." + rg.rlsgroup  # Adding period-prefixed pattern as well
                sensitive_patterns.append((pattern, is_case_sensitive))
            elif pattern.lower() == 'no':
                pattern = "-" + rg.rlsgroup
                sensitive_patterns.append((pattern, is_case_sensitive))
                pattern = "." + rg.rlsgroup  # Adding period-prefixed pattern for insensitivity
                sensitive_patterns.append((pattern, is_case_sensitive))
        
        # print("Loaded release groups:", ", ".join(insensitive_patterns + [p[0] for p in sensitive_patterns]))

        return insensitive_patterns, sensitive_patterns
    except SQLAlchemyError as e:
        print(f"An error occurred while fetching release group patterns: {e}")
        return [], []

def format_size(size_in_mb):
    if size_in_mb >= 1024:
        size_in_gb = size_in_mb / 1024
        return f"{size_in_gb:.2f} GB"
    else:
        return f"{size_in_mb} MB"



def comma_separated_urls(form, field):
    # print(f"comma_separated_urls: {field.data}")
    urls = field.data.split(',')
    url_pattern = re.compile(
        r'^(https?:\/\/)?(www\.)?youtube\.com\/embed\/[\w-]+$'
    )
    for url in urls:
        if not url_pattern.match(url.strip()):
            raise ValidationError('One or more URLs are invalid. Please provide valid YouTube embed URLs.')




# def directory_scan_task(folder_path):
#     with app.app_context():
#         print(f"directory_scan_task Started: {folder_path} by {current_user.name} (id: {current_user.id})")
#         
#         insensitive_patterns, sensitive_patterns = load_release_group_patterns()
#         game_names_with_paths = get_game_names_from_folder(folder_path, insensitive_patterns, sensitive_patterns)
# 
#         for game_info in game_names_with_paths:
#             game_name = game_info['name']
#             full_disk_path = game_info['full_path']
#             print(f"directory_scan_task Processing: {game_name} in {full_disk_path}")
#             game_added_successfully = retrieve_and_save_game(game_name, full_disk_path)
#             if game_added_successfully:
#                 print(f"directory_scan_task Game: {game_name} added successfully.")
#             else:
#                 print(f"directory_scan_task Failed to process {game_name}, adding to failed list.")

# def run_scheduled_tasks():
#     while True:
#         try:
#             schedule.run_pending()
#         except Exception as e:
#             print(f"An error occurred: {str(e)}")
#         time.sleep(1)

# Schedule the task for periodic execution, e.g., every day at 10 am
# folder_path = 'e:\games'
# if os.path.exists(folder_path):
#     schedule.every().day.at("10:00").do(directory_scan_task, folder_path=folder_path)
# else:
#     print(f"Specified folder path: {folder_path} does not exist. The task is not scheduled.")

# Start the scheduling thread
# try:
#     thread = Thread(target=run_scheduled_tasks)
#     thread.start()
#     print("Task scheduling thread started successfully.")
# except Exception as e:
#     print(f"An error occurred while starting the task scheduling thread: {str(e)}")