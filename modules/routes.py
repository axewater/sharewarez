# modules/routes.py
import sys, uuid, json, os, shutil, os
from threading import Thread
from config import Config
from flask import (
    Flask, render_template, flash, redirect, url_for, request, Blueprint, 
    jsonify, session, abort, current_app, 
    copy_current_request_context, g, current_app
)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case
from werkzeug.utils import secure_filename
from modules import db, mail, cache
from functools import wraps
from datetime import datetime, timedelta
from PIL import Image as PILImage
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from modules.forms import (
    ScanFolderForm, CsrfProtectForm, 
    AddGameForm, AutoScanForm, UpdateUnmatchedFolderForm, CsrfForm
)
from modules.models import (
    User, Game, Image, DownloadRequest, ScanJob, UnmatchedFolder,
    Publisher, Developer, Genre, Theme, GameMode, PlayerPerspective, GameUpdate, GameExtra,
    Category, GameURL, GlobalSettings, Library, user_favorites
)
from modules.utils_functions import (
    load_release_group_patterns, delete_associations_for_game,
    get_folder_size_in_bytes_updates, format_size, read_first_nfo_content, 
    PLATFORM_IDS
)
from modules.utilities import handle_auto_scan, handle_manual_scan
from modules.utils_auth import admin_required
from modules.utils_gamenames import get_game_names_from_folder, get_game_name_by_uuid
from modules.utils_scanning import refresh_images_in_background, delete_game_images
from modules.utils_game_core import get_game_by_uuid, check_existing_game_by_igdb_id
from modules.utils_processors import get_global_settings
from modules import app_start_time, app_version

bp = Blueprint('main', __name__)
s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
has_initialized_whitelist = False
has_upgraded_admin = False
has_initialized_setup = False

@bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()


@bp.context_processor
def inject_current_theme():
    if current_user.is_authenticated and current_user.preferences:
        current_theme = current_user.preferences.theme or 'default'
    else:
        current_theme = 'default'
    return dict(current_theme=current_theme)

@bp.route('/browse_games')
@login_required
def browse_games():
    print(f"Route: /browse_games - {current_user.name}")
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    library_uuid = request.args.get('library_uuid')
    category = request.args.get('category')
    genre = request.args.get('genre')
    rating = request.args.get('rating', type=int)
    game_mode = request.args.get('game_mode')
    player_perspective = request.args.get('player_perspective')
    theme = request.args.get('theme')
    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('sort_order', 'asc')
    query = Game.query.options(joinedload(Game.genres))
    if library_uuid:
        query = query.filter(Game.library_uuid == library_uuid)
    if category:
        query = query.filter(Game.category.has(Category.name == category))
    if genre:
        query = query.filter(Game.genres.any(Genre.name == genre))
    if rating is not None:
        query = query.filter(Game.rating >= rating)
    if game_mode:
        query = query.filter(Game.game_modes.any(GameMode.name == game_mode))
    if player_perspective:
        query = query.filter(Game.player_perspectives.any(PlayerPerspective.name == player_perspective))
    if theme:
        query = query.filter(Game.themes.any(Theme.name == theme))
    if sort_by == 'name':
        query = query.order_by(Game.name.asc() if sort_order == 'asc' else Game.name.desc())
    elif sort_by == 'rating':
        query = query.order_by(Game.rating.asc() if sort_order == 'asc' else Game.rating.desc())
    elif sort_by == 'first_release_date':
        query = query.order_by(Game.first_release_date.asc() if sort_order == 'asc' else Game.first_release_date.desc())
    elif sort_by == 'size':
        query = query.order_by(Game.size.asc() if sort_order == 'asc' else Game.size.desc())
    elif sort_by == 'date_identified':
        query = query.order_by(Game.date_identified.asc() if sort_order == 'asc' else Game.date_identified.desc())

    # Pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    games = pagination.items
    
    # Get game data
    game_data = []
    for game in games:
        cover_image = Image.query.filter_by(game_uuid=game.uuid, image_type='cover').first()
        cover_url = cover_image.url if cover_image else 'newstyle/default_cover.jpg'
        genres = [genre.name for genre in game.genres]
        game_size_formatted = format_size(game.size)
        game_data.append({
            'id': game.id,
            'uuid': game.uuid,
            'name': game.name,
            'cover_url': cover_url,
            'summary': game.summary,
            'url': game.url,
            'size': game_size_formatted,
            'genres': genres,
            'library_uuid': game.library_uuid
        })

    return jsonify({
        'games': game_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })
    

@bp.route('/browse_folders_ss')
@login_required
@admin_required
def browse_folders_ss():
    # Select base by OS
    base_dir = current_app.config.get('BASE_FOLDER_WINDOWS') if os.name == 'nt' else current_app.config.get('BASE_FOLDER_POSIX')
    print(f'SS folder browser: Base directory: {base_dir}', file=sys.stderr)
    
    # Attempt to get 'path' from request arguments; default to an empty string which signifies the base directory
    req_path = request.args.get('path', '')
    print(f'SS folder browser: Requested path: {req_path}', file=sys.stderr)
    # Handle the default path case
    if not req_path:
        print(f'SS folder browser: No default path provided; using base directory: {base_dir}', file=sys.stderr)
        req_path = ''
        folder_path = base_dir
    else:
        # Safely construct the folder path to prevent directory traversal vulnerabilities
        folder_path = os.path.abspath(os.path.join(base_dir, req_path))
        print(f'SS folder browser: Folder path: {folder_path}', file=sys.stderr)
        # Prevent directory traversal outside the base directory
        if not folder_path.startswith(base_dir):
            print(f'SS folder browser: Access denied: {folder_path} outside of base directory: {base_dir}', file=sys.stderr)
            return jsonify({'error': 'Access denied'}), 403

    if os.path.isdir(folder_path):
        # List directory contents; distinguish between files and directories
        # print(f'Folder contents: {os.listdir(folder_path)}', file=sys.stderr)
        contents = [{'name': item, 'isDir': os.path.isdir(os.path.join(folder_path, item))} for item in sorted(os.listdir(folder_path))]
        return jsonify(sorted(contents, key=lambda x: (not x['isDir'], x['name'].lower())))
    else:
        return jsonify({'error': 'SS folder browser: Folder not found'}), 404


@bp.route('/toggle_favorite/<game_uuid>', methods=['POST'])
@login_required
def toggle_favorite(game_uuid):
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    
    if game in current_user.favorites:
        current_user.favorites.remove(game)
        is_favorite = False
    else:
        current_user.favorites.append(game)
        is_favorite = True
    
    db.session.commit()
    return jsonify({'success': True, 'is_favorite': is_favorite})


@bp.route('/favorites')
@login_required
def favorites():
    favorites = current_user.favorites
    game_data = []
    for game in favorites:
        cover_image = Image.query.filter_by(game_uuid=game.uuid, image_type='cover').first()
        cover_url = cover_image.url if cover_image else 'newstyle/default_cover.jpg'
        genres = [genre.name for genre in game.genres]
        game_size_formatted = format_size(game.size)
        game_data.append({'uuid': game.uuid, 'name': game.name, 'cover_url': cover_url, 'size': game_size_formatted, 'genres': genres})
    
    return render_template('games/favorites.html', favorites=game_data)


@bp.route('/check_favorite/<game_uuid>')
@login_required
def check_favorite(game_uuid):
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    is_favorite = game in current_user.favorites
    return jsonify({'is_favorite': is_favorite})


@bp.route('/downloads')
@login_required
def downloads():
    user_id = current_user.id
    print(f"Route: /downloads user_id: {user_id}")
    download_requests = DownloadRequest.query.filter_by(user_id=user_id).all()
    for download_request in download_requests:
        download_request.formatted_size = format_size(download_request.download_size)
    form = CsrfProtectForm()
    return render_template('games/manage_downloads.html', download_requests=download_requests, form=form)


@bp.route('/scan_manual_folder', methods=['GET', 'POST'])
@login_required
@admin_required
def scan_folder():
    ## to be fixed broken again after update
    form = ScanFolderForm()
    game_names_with_ids = None
    
    if form.validate_on_submit():
        if form.cancel.data:
            return redirect(url_for('main.scan_folder'))
        
        folder_path = form.folder_path.data
        print(f"Scanning folder: {folder_path}")

        if os.path.exists(folder_path) and os.access(folder_path, os.R_OK):
            print("Folder exists and is accessible.")
            insensitive_patterns, sensitive_patterns = load_release_group_patterns()
            games_with_paths = get_game_names_from_folder(folder_path, insensitive_patterns, sensitive_patterns)
            session['active_tab'] = 'manualScan'
            session['game_paths'] = {game['name']: game['full_path'] for game in games_with_paths}            
            game_names_with_ids = [{'name': game['name'], 'id': i} for i, game in enumerate(games_with_paths)]
        else:
            flash("Folder does not exist or cannot be accessed.", "error")
            print("Folder does not exist or cannot be accessed.")
            
    return render_template('admin/admin_manage_scanjobs.html', form=form, game_names_with_ids=game_names_with_ids)



@bp.route('/scan_management', methods=['GET', 'POST'])
@login_required
@admin_required
def scan_management():
    auto_form = AutoScanForm()
    manual_form = ScanFolderForm()

    libraries = Library.query.all()
    auto_form.library_uuid.choices = [(str(lib.uuid), lib.name) for lib in libraries]
    manual_form.library_uuid.choices = [(str(lib.uuid), lib.name) for lib in libraries]

    selected_library_uuid = request.args.get('library_uuid')
    if selected_library_uuid:
        auto_form.library_uuid.data = selected_library_uuid 
        manual_form.library_uuid.data = selected_library_uuid

    jobs = ScanJob.query.order_by(ScanJob.last_run.desc()).all()
    csrf_form = CsrfProtectForm()
    unmatched_folders = UnmatchedFolder.query\
                        .join(Library)\
                        .with_entities(UnmatchedFolder, Library.name, Library.platform)\
                        .order_by(UnmatchedFolder.status.desc()).all()
    unmatched_form = UpdateUnmatchedFolderForm() 
    # Packaging data with platform details
    unmatched_folders_with_platform = []
    for unmatched, lib_name, lib_platform in unmatched_folders:
        platform_id = PLATFORM_IDS.get(lib_platform.name) if lib_platform else None
        unmatched_folders_with_platform.append({
            "folder": unmatched,
            "library_name": lib_name,
            "platform_name": lib_platform.name if lib_platform else '',
            "platform_id": platform_id
        })
        
    game_count = Game.query.count()  # Fetch the game count here

    if request.method == 'POST':
        submit_action = request.form.get('submit')
        if submit_action == 'AutoScan':
            return handle_auto_scan(auto_form)
        elif submit_action == 'ManualScan':
            return handle_manual_scan(manual_form)
        elif submit_action == 'DeleteAllUnmatched':
            return handle_delete_unmatched(all=True)
        elif submit_action == 'DeleteOnlyUnmatched':
            return handle_delete_unmatched(all=False)
        else:
            flash("Unrecognized action.", "error")
            return redirect(url_for('main.scan_management'))

    game_paths_dict = session.get('game_paths', {})
    game_names_with_ids = [{'name': name, 'full_path': path} for name, path in game_paths_dict.items()]
    active_tab = session.get('active_tab', 'auto')

    return render_template('admin/admin_manage_scanjobs.html', 
                           auto_form=auto_form, 
                           manual_form=manual_form, 
                           jobs=jobs, 
                           csrf_form=csrf_form, 
                           active_tab=active_tab, 
                           unmatched_folders=unmatched_folders_with_platform,
                           unmatched_form=unmatched_form,
                           game_count=game_count,
                           libraries=libraries,
                           game_names_with_ids=game_names_with_ids)


@bp.route('/cancel_scan_job/<job_id>', methods=['POST'])
@login_required
@admin_required
def cancel_scan_job(job_id):
    job = ScanJob.query.get(job_id)
    if job and job.status == 'Running':
        job.is_enabled = False
        db.session.commit()
        flash(f"Scan job {job_id} has been canceled.")
        print(f"Scan job {job_id} has been canceled.")
    else:
        flash('Scan job not found or not in a cancellable state.', 'error')
    return redirect(url_for('main.scan_management'))


@bp.route('/add_game_manual', methods=['GET', 'POST'])
@login_required
@admin_required
def add_game_manual():
    if is_scan_job_running():
        flash('Cannot add a new game while a scan job is running. Please try again later.', 'error')
        print("Attempt to add a new game while a scan job is running.")
        
        # Determine redirection based on from_unmatched
        from_unmatched = request.args.get('from_unmatched', 'false') == 'true'
        if from_unmatched:
            return redirect(url_for('main.scan_management', active_tab='unmatched'))
        else:
            return redirect(url_for('library.library'))
    
    full_disk_path = request.args.get('full_disk_path', None)
    library_uuid = request.args.get('library_uuid') or session.get('selected_library_uuid')
    from_unmatched = request.args.get('from_unmatched', 'false') == 'true'  # Detect origin
    game_name = os.path.basename(full_disk_path) if full_disk_path else ''

    form = AddGameForm()

    # Populate the choices for the library_uuid field
    form.library_uuid.choices = [(str(library.uuid), library.name) for library in Library.query.order_by(Library.name).all()]
    print(f'agm Library choices: {form.library_uuid.choices}')
    
    # Fetch library details for displaying on the form
    library_uuid = request.args.get('library_uuid')
    library = Library.query.filter_by(uuid=library_uuid).first()
    if library:
        library_name = library.name
        platform_name = library.platform.name
        platform_id = PLATFORM_IDS.get(library.platform.name)
    else:
        library_name = platform_name = ''
        platform_id = None
    
    if request.method == 'GET':
        if full_disk_path:
            form.full_disk_path.data = full_disk_path
            form.name.data = game_name
        if library_uuid:
            form.library_uuid.data = library_uuid
    
    if form.validate_on_submit():
        if check_existing_game_by_igdb_id(form.igdb_id.data):
            flash('A game with this IGDB ID already exists.', 'error')
            print(f"IGDB ID {form.igdb_id.data} already exists.")
            return render_template('admin/admin_game_identify.html', form=form, library_uuid=library_uuid, library_name=library_name, platform_name=platform_name, platform_id=platform_id)
        
        new_game = Game(
            igdb_id=form.igdb_id.data,
            name=form.name.data,
            summary=form.summary.data,
            storyline=form.storyline.data,
            url=form.url.data,
            full_disk_path=form.full_disk_path.data,
            category=form.category.data,
            status=form.status.data,
            first_release_date=form.first_release_date.data,
            video_urls=form.video_urls.data,
            library_uuid=form.library_uuid.data
        )
        new_game.genres = form.genres.data
        new_game.game_modes = form.game_modes.data
        new_game.themes = form.themes.data
        new_game.platforms = form.platforms.data
        new_game.player_perspectives = form.player_perspectives.data

        # Handle developer
        if form.developer.data and form.developer.data != 'Not Found':
            developer = Developer.query.filter_by(name=form.developer.data).first()
            if not developer:
                developer = Developer(name=form.developer.data)
                db.session.add(developer)
                db.session.flush() 
            new_game.developer = developer

        if form.publisher.data and form.publisher.data != 'Not Found':
            publisher = Publisher.query.filter_by(name=form.publisher.data).first()
            if not publisher:
                publisher = Publisher(name=form.publisher.data)
                db.session.add(publisher)
                db.session.flush()
            new_game.publisher = publisher
        new_game.nfo_content = read_first_nfo_content(form.full_disk_path.data)

        # print("New game:", new_game)
        try:
            db.session.add(new_game)
            db.session.commit()
            if full_disk_path: 
                unmatched_folder = UnmatchedFolder.query.filter_by(folder_path=full_disk_path).first()
                if unmatched_folder:
                    db.session.delete(unmatched_folder)
                    print("Deleted unmatched folder:", unmatched_folder)
                    db.session.commit()
            flash('Game added successfully.', 'success')
            print(f"add_game_manual Game: {game_name} added by user {current_user.name}.")
            # Trigger image refresh after adding the game
            @copy_current_request_context
            def refresh_images_in_thread():
                refresh_images_in_background(new_game.uuid)

            # Start the background process for refreshing images
            thread = Thread(target=refresh_images_in_thread)
            thread.start()
            print(f"Refresh images thread started for game UUID: {new_game.uuid}")
            
            if from_unmatched:
                return redirect(url_for('main.scan_management', active_tab='unmatched'))
            else:
                return redirect(url_for('library.library'))
        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"Error saving the game to the database: {e}")
            flash('An error occurred while adding the game. Please try again.', 'error')
    else:
        print(f"Form validation failed: {form.errors}")
    return render_template(
        'admin/admin_game_identify.html',
        form=form,
        from_unmatched=from_unmatched,
        action="add",
        library_uuid=library_uuid,
        library_name=library_name,
        platform_name=platform_name,
        platform_id=platform_id
    )

@bp.route('/game_edit/<game_uuid>', methods=['GET', 'POST'])
@login_required
@admin_required
def game_edit(game_uuid):
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    form = AddGameForm(obj=game)
    form.library_uuid.choices = [(str(lib.uuid), lib.name) for lib in Library.query.order_by(Library.name).all()]
    platform_id = PLATFORM_IDS.get(game.library.platform.value.upper(), None)
    platform_name = game.library.platform.value
    library_name = game.library.name
    print(f"game_edit1 Platform ID: {platform_id}, Platform Name: {platform_name} Library Name: {library_name}")
    if form.validate_on_submit():
        if is_scan_job_running():
            flash('Cannot edit the game while a scan job is running. Please try again later.', 'error')
            print("Attempt to edit a game while a scan job is running by user:", current_user.name)
            # Re-render the template with the current form data
            return render_template('admin/admin_game_identify.html', form=form, game_uuid=game_uuid, action="edit")

        # Check if any other game has the same igdb_id and is not the current game
        existing_game_with_igdb_id = Game.query.filter(
            Game.igdb_id == form.igdb_id.data,
            Game.id != game.id 
        ).first()
        
        if existing_game_with_igdb_id is not None:
            flash(f'The IGDB ID {form.igdb_id.data} is already used by another game.', 'error')
            return render_template('admin/admin_game_identify.html', form=form, library_name=library_name, game_uuid=game_uuid, action="edit")
        
        igdb_id_changed = game.igdb_id != form.igdb_id.data
        game.library_uuid = form.library_uuid.data
        game.igdb_id = form.igdb_id.data
        game.name = form.name.data
        game.summary = form.summary.data
        game.storyline = form.storyline.data
        game.url = form.url.data
        game.full_disk_path = form.full_disk_path.data
        game.video_urls = form.video_urls.data         
        game.aggregated_rating = form.aggregated_rating.data
        game.first_release_date = form.first_release_date.data
        game.status = form.status.data
        category_str = form.category.data 
        category_str = category_str.replace('Category.', '')
        if category_str in Category.__members__:
            game.category = Category[category_str]
        else:
            flash(f'Invalid category: {category_str}', 'error')
            return render_template('admin/admin_game_identify.html', form=form, game_uuid=game_uuid, action="edit")
        
        # Handling Developer
        developer_name = form.developer.data
        if developer_name:
            developer = Developer.query.filter_by(name=developer_name).first()
            if not developer:
                developer = Developer(name=developer_name)
                db.session.add(developer)
                db.session.flush()
            game.developer = developer

        # Handling Publisher
        publisher_name = form.publisher.data
        if publisher_name:
            publisher = Publisher.query.filter_by(name=publisher_name).first()
            if not publisher:
                publisher = Publisher(name=publisher_name)
                db.session.add(publisher)
                db.session.flush()
            game.publisher = publisher

        # Update many-to-many relationships
        game.genres = form.genres.data
        game.game_modes = form.game_modes.data
        game.themes = form.themes.data
        game.platforms = form.platforms.data
        game.player_perspectives = form.player_perspectives.data
        
        # Updating size
        print(f"Calculating folder size for {game.full_disk_path}.")
        new_folder_size_bytes = get_folder_size_in_bytes_updates(game.full_disk_path)
        print(f"New folder size for {game.full_disk_path}: {format_size(new_folder_size_bytes)}")
        game.size = new_folder_size_bytes
        game.nfo_content = read_first_nfo_content(game.full_disk_path)
        game.date_identified = datetime.utcnow()
               
        # DB commit and conditional image update
        try:
            db.session.commit()
            flash('Game updated successfully.', 'success')
            
            if igdb_id_changed:
                flash('IGDB ID changed. Triggering image update.')
                @copy_current_request_context
                def refresh_images_in_thread():
                    refresh_images_in_background(game_uuid)
                thread = Thread(target=refresh_images_in_thread)
                thread.start()
                print(f"Refresh images thread started for game UUID: {game_uuid}")
            else:
                print(f"IGDB ID unchanged. Skipping image refresh for game UUID: {game_uuid}")
                    
            return redirect(url_for('library.library'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('An error occurred while updating the game. Please try again.', 'error')

    if request.method == 'POST':
        print(f"/game_edit/: Form validation failed: {form.errors}")

    # For GET or if form fails
    print(f"game_edit2 Platform ID: {platform_id}, Platform Name: {platform_name}, Library Name: {library_name}")
    return render_template('admin/admin_game_identify.html', form=form, game_uuid=game_uuid, platform_id=platform_id, platform_name=platform_name, library_name=library_name, action="edit")

# @bp.route('/get_platform_by_library/<library_uuid>')
# @login_required
# @admin_required
# def get_platform_by_library(library_uuid):
#     library = Library.query.filter_by(uuid=library_uuid).first()
#     if library:
#         platform_name = library.platform.name
#         platform_id = PLATFORM_IDS.get(library.platform.value.upper(), None)
#         return jsonify({'platform_name': platform_name, 'platform_id': platform_id})
#     return jsonify({'error': 'Library not found'}), 404


@bp.route('/edit_game_images/<game_uuid>', methods=['GET'])
@login_required
@admin_required
def edit_game_images(game_uuid):
    if is_scan_job_running():
        flash('Image editing is restricted while a scan job is running. Please try again later.', 'warning')
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    cover_image = Image.query.filter_by(game_uuid=game_uuid, image_type='cover').first()
    screenshots = Image.query.filter_by(game_uuid=game_uuid, image_type='screenshot').all()
    return render_template('games/game_edit_images.html', game=game, cover_image=cover_image, images=screenshots)


@bp.route('/upload_image/<game_uuid>', methods=['POST'])
@login_required
@admin_required
def upload_image(game_uuid):
    print(f"Uploading image for game {game_uuid}")
    if is_scan_job_running():
        print(f"Attempt to upload image for game UUID: {game_uuid} while scan job is running")
        flash('Cannot upload images while a scan job is running. Please try again later.', 'error')
        return jsonify({'error': 'Cannot upload images while a scan job is running. Please try again later.'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    image_type = request.form.get('image_type', 'screenshot')  # Default to 'screenshot'

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Validate file extension and content type
    allowed_extensions = {'jpg', 'jpeg', 'png'}
    filename = secure_filename(file.filename)
    file_extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    if file_extension not in allowed_extensions:
        return jsonify({'error': 'Only JPG and PNG files are allowed'}), 400

    # Further validate the file's data to ensure it's a valid image
    try:
        img = PILImage.open(file)
        img.verify()  # Verify that it is, in fact, an image
        img = PILImage.open(file)
    except (IOError, SyntaxError):
        return jsonify({'error': 'Invalid image data'}), 400

    file.seek(0)
    max_width, max_height = 1200, 1600
    if image_type == 'cover':
        if img.width > max_width or img.height > max_height:
            img.thumbnail((max_width, max_height), PILImage.ANTIALIAS)
    file.seek(0) 
    # Efficient file size check
    if file.content_length > 3 * 1024 * 1024:  # 3MB in bytes
        return jsonify({'error': 'File size exceeds the 3MB limit'}), 400

    # Handle cover image logic
    if image_type == 'cover':
        # Check if a cover image already exists
        existing_cover = Image.query.filter_by(game_uuid=game_uuid, image_type='cover').first()
        if existing_cover:
            # If exists, delete the old cover image file and record
            old_cover_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], existing_cover.url)
            if os.path.exists(old_cover_path):
                os.remove(old_cover_path)
            db.session.delete(existing_cover)
            db.session.commit()
    short_uuid = str(uuid.uuid4())[:8]
    if image_type == 'cover':
        unique_identifier = str(uuid.uuid4())[:8]
        filename = f"{game_uuid}_cover_{unique_identifier}.{file_extension}"
    else:
        unique_identifier = datetime.now().strftime('%Y%m%d%H%M%S')
        short_uuid = str(uuid.uuid4())[:8]
        filename = f"{game_uuid}_{unique_identifier}_{short_uuid}.{file_extension}"
    save_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], filename)
    file.save(save_path)
    print(f"File saved to: {save_path}")
    new_image = Image(game_uuid=game_uuid, image_type=image_type, url=filename)
    db.session.add(new_image)
    db.session.commit()
    print(f"File saved to DB with ID: {new_image.id}")

    return jsonify({
        'message': 'File uploaded successfully',
        'url': url_for('static', filename=f'library/images/{filename}'),
        'flash': 'Image uploaded successfully!',
        'image_id': new_image.id
    })

@bp.route('/delete_image', methods=['POST'])
@login_required
@admin_required
def delete_image():
    if is_scan_job_running():
        print("Attempt to delete image while scan job is running")
        return jsonify({'error': 'Cannot delete images while a scan job is running. Please try again later.'}), 403

    try:
        data = request.get_json()
        if not data or 'image_id' not in data:
            return jsonify({'error': 'Invalid request. Missing image_id parameter'}), 400
        
        image_id = data['image_id']
        is_cover = data.get('is_cover', False)
        image = Image.query.get(image_id)
        if not image:
            return jsonify({'error': 'Image not found'}), 404

        # Delete image file from disk
        image_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], image.url)
        if os.path.exists(image_path):
            print(f"Deleting image file: {image_path}")
            os.remove(image_path)

        # Delete image record from database
        db.session.delete(image)
        db.session.commit()

        response_data = {'message': 'Image deleted successfully'}
        if is_cover:
            response_data['default_cover'] = url_for('static', filename='newstyle/default_cover.jpg')
            
        return jsonify(response_data)
    except Exception as e:
        # Log the error for debugging purposes
        print(f"Error deleting image: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred while deleting the image'}), 500


@bp.route('/delete_scan_job/<job_id>', methods=['POST'])
@login_required
@admin_required
def delete_scan_job(job_id):
    job = ScanJob.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()
    flash('Scan job deleted successfully.', 'success')
    return redirect(url_for('main.scan_management'))

@bp.route('/clear_all_scan_jobs', methods=['POST'])
@login_required
@admin_required
def clear_all_scan_jobs():
    session['active_tab'] = 'auto'
    db.session.query(ScanJob).delete()
    db.session.commit()
    flash('All scan jobs cleared successfully.', 'success')
    return redirect(url_for('main.scan_management'))


@bp.route('/delete_all_unmatched_folders', methods=['POST'])
@login_required
@admin_required
def delete_all_unmatched_folders():
    try:
        UnmatchedFolder.query.delete()  # Deletes all unmatched folder records
        db.session.commit()
        flash('All unmatched folders deleted successfully.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        error_message = f"Database error while deleting all unmatched folders: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
    except Exception as e:
        db.session.rollback()
        error_message = f"An unexpected error occurred while deleting all unmatched folders: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
    return redirect(url_for('main.scan_management'))


def clear_only_unmatched_folders():
    print("Attempting to clear only unmatched folders")
    try:
        result = UnmatchedFolder.query.filter(UnmatchedFolder.status == 'Unmatched').delete(synchronize_session='fetch')
        print(f"Number of unmatched folders deleted: {result}")
        db.session.commit()
        flash(f'Successfully cleared {result} unmatched folders with status "Unmatched".', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        error_message = f"Database error while clearing unmatched folders: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
    except Exception as e:
        db.session.rollback()
        error_message = f"An unexpected error occurred while clearing unmatched folders: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
    
    print("Redirecting to scan management page")
    return redirect(url_for('main.scan_management'))


def handle_delete_unmatched(all):
    print(f"Route: /delete_unmatched - {current_user.name} - {current_user.role} method: {request.method} arguments: all={all}")
    try:
        if all:
            print(f"Clearing all unmatched folders: {UnmatchedFolder.query.count()}")
            UnmatchedFolder.query.delete()
            flash('All unmatched folders cleared successfully.', 'success')
        else:
            count = UnmatchedFolder.query.filter(UnmatchedFolder.status == 'Unmatched').count()
            print(f"Clearing this number of unmatched folders: {count}")
            UnmatchedFolder.query.filter(UnmatchedFolder.status == 'Unmatched').delete()
            flash('Unmatched folders with status "Unmatched" cleared successfully.', 'success')
        db.session.commit()
        session['active_tab'] = 'unmatched'
    except SQLAlchemyError as e:
        db.session.rollback()
        error_message = f"Database error while clearing unmatched folders: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
    except Exception as e:
        db.session.rollback()
        error_message = f"An unexpected error occurred while clearing unmatched folders: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
    return redirect(url_for('main.scan_management'))




@bp.route('/api/scan_jobs_status', methods=['GET'])
@login_required
@admin_required
def scan_jobs_status():
    jobs = ScanJob.query.all()
    jobs_data = [{
        'id': job.id,
        'library_name': job.library.name if job.library else 'No Library Assigned',
        'folders': job.folders,
        'status': job.status,
        'total_folders': job.total_folders,
        'folders_success': job.folders_success,
        'folders_failed': job.folders_failed,
        'error_message': job.error_message,
        'last_run': job.last_run.strftime('%Y-%m-%d %H:%M:%S') if job.last_run else 'Not Available',
        'next_run': job.next_run.strftime('%Y-%m-%d %H:%M:%S') if job.next_run else 'Not Scheduled'
    } for job in jobs]
    return jsonify(jobs_data)

@bp.route('/api/unmatched_folders', methods=['GET'])
@login_required
@admin_required
def unmatched_folders():
    unmatched = UnmatchedFolder.query.join(Library).with_entities(
        UnmatchedFolder, Library.name.label('library_name'), Library.platform
    ).order_by(UnmatchedFolder.status.desc()).all()
    
    unmatched_data = [{
        'id': folder.id,
        'folder_path': folder.folder_path,
        'status': folder.status,
        'library_name': library_name,
        'platform_name': platform.name if platform else '',
        'platform_id': PLATFORM_IDS.get(platform.name) if platform else None
    } for folder, library_name, platform in unmatched]
    
    return jsonify(unmatched_data)



@bp.route('/update_unmatched_folder_status', methods=['POST'])
@login_required
@admin_required
def update_unmatched_folder_status():
    print("Route: /update_unmatched_folder_status")
    folder_id = request.form.get('folder_id')
    new_status = request.form.get('new_status')
    session['active_tab'] = 'unmatched'
    folder = UnmatchedFolder.query.filter_by(id=folder_id).first()
    if folder:
        folder.status = new_status
        try:
            db.session.commit()
            print(f'Folder {folder_id} status updated successfully.', 'success')
            flash(f'Folder {folder_id} status updated successfully.', 'success')
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error updating folder status: {str(e)}', 'error')
    else:
        flash('Folder not found.', 'error')

    return redirect(url_for('main.scan_management'))


@bp.route('/check_path_availability', methods=['GET'])
@login_required
def check_path_availability():
    full_disk_path = request.args.get('full_disk_path', '')
    is_available = os.path.exists(full_disk_path)
    return jsonify({'available': is_available})



@bp.route('/api/check_igdb_id')
@login_required
def check_igdb_id():
    igdb_id = request.args.get('igdb_id', type=int)
    if igdb_id is None:
        return jsonify({'message': 'Invalid request', 'available': False}), 400

    game_exists = check_existing_game_by_igdb_id(igdb_id) is not None
    return jsonify({'available': not game_exists})


@bp.route('/game_details/<string:game_uuid>')
@login_required
def game_details(game_uuid):
    print(f"Fetching game details for UUID: {game_uuid}")
    csrf_form = CsrfForm()
    try:
        valid_uuid = uuid.UUID(game_uuid, version=4)
    except ValueError:
        print(f"Invalid UUID format: {game_uuid}")
        abort(404)

    game = get_game_by_uuid(str(valid_uuid))

    if game:
        # Explicitly load updates and extras
        updates = GameUpdate.query.filter_by(game_uuid=game.uuid).all()
        extras = GameExtra.query.filter_by(game_uuid=game.uuid).all()
        print(f"Found {len(updates)} updates and {len(extras)} extras for game {game.name}")
        
        game_data = {
            "id": game.id,
            "uuid": game.uuid,
            "igdb_id": game.igdb_id,
            "name": game.name,
            "summary": game.summary,
            "storyline": game.storyline,
            "aggregated_rating": game.aggregated_rating,
            "aggregated_rating_count": game.aggregated_rating_count,
            "updates": [{
                "id": update.id,
                "file_path": update.file_path,
                "times_downloaded": update.times_downloaded,
                "created_at": update.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "nfo_content": update.nfo_content
            } for update in game.updates],
            "extras": [{
                "id": extra.id,
                "file_path": extra.file_path,
                "times_downloaded": extra.times_downloaded,
                "created_at": extra.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "nfo_content": extra.nfo_content
            } for extra in game.extras],
            "cover": game.cover,
            "first_release_date": game.first_release_date.strftime('%Y-%m-%d') if game.first_release_date else 'Not available',
            "rating": game.rating,
            "rating_count": game.rating_count,
            "slug": game.slug,
            "status": game.status.value if game.status else 'Not available',
            "category": game.category.value if game.category else 'Not available',
            "total_rating": game.total_rating,
            "total_rating_count": game.total_rating_count,
            "url_igdb": game.url_igdb,
            "url": game.url,
            "video_urls": game.video_urls,
            "full_disk_path": game.full_disk_path,
            "images": [{"id": img.id, "type": img.image_type, "url": img.url} for img in game.images.all()],
            "genres": [genre.name for genre in game.genres],
            "game_modes": [mode.name for mode in game.game_modes],
            "themes": [theme.name for theme in game.themes],
            "platforms": [platform.name for platform in game.platforms],
            "player_perspectives": [perspective.name for perspective in game.player_perspectives],
            "developer": game.developer.name if game.developer else 'Not available',
            "publisher": game.publisher.name if game.publisher else 'Not available',
            "multiplayer_modes": [mode.name for mode in game.multiplayer_modes],
            "nfo_content": game.nfo_content if game.nfo_content else 'none',
            "size": format_size(game.size),
            "date_identified": game.date_identified.strftime('%Y-%m-%d %H:%M:%S') if game.date_identified else 'Not available',
            "steam_url": game.steam_url if game.steam_url else 'Not available',
            "times_downloaded": game.times_downloaded,
            "last_updated": game.last_updated.strftime('%Y-%m-%d') if game.last_updated else 'N/A',
            "updates": [{
                "id": update.id,
                "file_path": update.file_path,
                "times_downloaded": update.times_downloaded,
                "created_at": update.created_at.strftime('%Y-%m-%d %H:%M:%S')
            } for update in game.updates]
        }
        
        # URL Icons Mapping
        url_icons = {
            "official": "fa-solid fa-globe",
            "wikia": "fa-brands fa-wikimedia",
            "wikipedia": "fa-brands fa-wikipedia-w",
            "facebook": "fa-brands fa-facebook",
            "twitter": "fa-brands fa-twitter",
            "twitch": "fa-brands fa-twitch",
            "instagram": "fa-brands fa-instagram",
            "youtube": "fa-brands fa-youtube",
            "steam": "fa-brands fa-steam",
            "reddit": "fa-brands fa-reddit",
            "itch": "fa-brands fa-itch-io",
            "epicgames": "fa-brands fa-epic-games",
            "gog": "fa-brands fa-gog",
            "discord": "fa-brands fa-discord",
        }
        # Augment game_data with URLs
        game_data['urls'] = [{
            "type": url.url_type,
            "url": url.url,
            "icon": url_icons.get(url.url_type, "fa-link")
        } for url in game.urls]
        
        library_uuid = game.library_uuid
        
        return render_template('games/game_details.html', game=game_data, form=csrf_form, library_uuid=library_uuid)
    else:
        return jsonify({"error": "Game not found"}), 404


@bp.route('/refresh_game_images/<game_uuid>', methods=['POST'])
@login_required
@admin_required
def refresh_game_images(game_uuid):
    game_name = get_game_name_by_uuid(game_uuid)
    print(f"Route: /refresh_game_images - {current_user.name} - {current_user.role} method: {request.method} UUID: {game_uuid} Name: {game_name}")

    @copy_current_request_context
    def refresh_images_in_thread():
        refresh_images_in_background(game_uuid)

    thread = Thread(target=refresh_images_in_thread)
    thread.start()
    print(f"Refresh images thread started for game UUID: {game_uuid} and Name: {game_name}.")

    # Check if the request is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return a JSON response for AJAX requests
        return jsonify({f"message": "Game images refresh process started for {game_name}.", "status": "info"})
    else:
        # For non-AJAX requests, perform the usual redirec
        flash(f"Game images refresh process started for {game_name}.", "info")
        return redirect(url_for('library.library'))



@bp.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    print(f"Route: /admin/dashboard - {current_user.name} - {current_user.role} method: {request.method}")
    return render_template('admin/admin_dashboard.html')





@bp.route('/delete_game/<string:game_uuid>', methods=['POST'])
@login_required
@admin_required
def delete_game_route(game_uuid):
    print(f"Route: /delete_game - {current_user.name} - {current_user.role} method: {request.method} UUID: {game_uuid}")
    
    if is_scan_job_running():
        print(f"Error: Attempt to delete game UUID: {game_uuid} while scan job is running")
        flash('Cannot delete the game while a scan job is running. Please try again later.', 'error')
        return redirect(url_for('library.library'))
    delete_game(game_uuid)
    return redirect(url_for('library.library'))

def is_scan_job_running():
    """
    Check if there is any scan job with the status 'Running'.
    
    Returns:
        bool: True if there is a running scan job, False otherwise.
    """
    running_scan_job = ScanJob.query.filter_by(status='Running').first()
    return running_scan_job is not None


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




@bp.route('/delete_folder', methods=['POST'])
@login_required
@admin_required
def delete_folder():
    data = request.get_json()
    folder_path = data.get('folder_path') if data else None

    if not folder_path:
        return jsonify({'status': 'error', 'message': 'Path is required.'}), 400

    full_path = os.path.abspath(folder_path)

    folder_entry = UnmatchedFolder.query.filter_by(folder_path=folder_path).first()

    if not os.path.exists(full_path):
        if folder_entry:
            db.session.delete(folder_entry)
            db.session.commit()
        return jsonify({'status': 'error', 'message': 'The specified path does not exist. Entry removed if it was in the database.'}), 404

    try:
        if os.path.isfile(full_path):
            os.remove(full_path)
        else:
            shutil.rmtree(full_path)
        
        if not os.path.exists(full_path):
            if folder_entry:
                db.session.delete(folder_entry)
                db.session.commit()
            return jsonify({'status': 'success', 'message': 'Item deleted successfully. Database entry removed.'}), 200
    except PermissionError:
        return jsonify({'status': 'error', 'message': 'Failed to delete the item due to insufficient permissions. Database entry retained.'}), 403
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error deleting item: {e}. Database entry retained.'}), 500


@bp.route('/delete_full_game', methods=['POST'])
@login_required
@admin_required
def delete_full_game():
    print(f"Route: /delete_full_game - {current_user.name} - {current_user.role} method: {request.method}")
    data = request.get_json()
    game_uuid = data.get('game_uuid') if data else None
    print(f"Route: /delete_full_game - Game UUID: {game_uuid}")
    if not game_uuid:
        print(f"Route: /delete_full_game - Game UUID is required.")
        return jsonify({'status': 'error', 'message': 'Game UUID is required.'}), 400

    if is_scan_job_running():
        print(f"Error: Attempt to delete full game UUID: {game_uuid} while scan job is running")
        return jsonify({'status': 'error', 'message': 'Cannot delete the game while a scan job is running. Please try again later.'}), 403

    game_to_delete = Game.query.filter_by(uuid=game_uuid).first()
    print(f"Route: /delete_full_game - Game to delete: {game_to_delete}")

    if not game_to_delete:
        print(f"Route: /delete_full_game - Game not found.")
        return jsonify({'status': 'error', 'message': 'Game not found.'}), 404

    full_path = game_to_delete.full_disk_path
    print(f"Route: /delete_full_game - Full path: {full_path}")

    if not os.path.isdir(full_path):
        print(f"Route: /delete_full_game - Game folder does not exist.")
        return jsonify({'status': 'error', 'message': 'Game folder does not exist.'}), 404

    try:
        # Delete the game folder
        print(f"Deleting game folder: {full_path}")
        shutil.rmtree(full_path)
        if os.path.exists(full_path):
            raise Exception("Folder deletion failed")
        print(f"Game folder deleted: {full_path} initiating database cleanup.")
        delete_game(game_uuid)
        print(f"Database and image cleanup complete.")
        return jsonify({'status': 'success', 'message': 'Game and its folder have been deleted successfully.'}), 200
    except Exception as e:
        print(f"Error deleting game and folder: {e}")
        return jsonify({'status': 'error', 'message': f'Error deleting game and folder: {e}'}), 500


@bp.route('/delete_full_library/<library_uuid>', methods=['POST'])
@bp.route('/delete_full_library/KILL_ALL_LIBRARIES', methods=['POST'])
@login_required
@admin_required
def delete_full_library(library_uuid=None):
    print(f"Route: /delete_full_library - {current_user.name} - {current_user.role} method: {request.method} UUID: {library_uuid}")
    try:
        if library_uuid == "KILL_ALL_LIBRARIES":
            print(f"KILL ALL Deleting all libraries and their games.")
            libraries = Library.query.all()
            for library in libraries:
                games_to_delete = Game.query.filter_by(library_uuid=library.uuid).all()
                for game in games_to_delete:
                    try:
                        delete_game(game.uuid)
                    except FileNotFoundError as fnfe:
                        print(f'File not found for game with UUID {game.uuid}: {fnfe}')
                        flash(f'File not found for game with UUID {game.uuid}. Skipping...', 'info')
                    except Exception as e:
                        print(f'Error deleting game with UUID {game.uuid}: {e}')
                        flash(f'Error deleting game with UUID {game.uuid}: {e}', 'error')
                db.session.delete(library)
            flash('All libraries and their games have been deleted.', 'success')
        elif library_uuid:
            library = Library.query.filter_by(uuid=library_uuid).first()
            if library:
                print(f"Deleting full library: {library}")
                games_to_delete = Game.query.filter_by(library_uuid=library.uuid).all()
                for game in games_to_delete:
                    try:
                        delete_game(game.uuid)
                    except FileNotFoundError as fnfe:
                        print(f'File not found for game with UUID {game.uuid}: {fnfe}')
                        flash(f'File not found for game with UUID {game.uuid}. Skipping...', 'info')
                    except Exception as e:
                        print(f'Error deleting game with UUID {game.uuid}: {e}')
                        flash(f'Error deleting game with UUID {game.uuid}: {e}', 'error')
                db.session.delete(library)
                flash(f'Library "{library.name}" and all its games have been deleted.', 'success')
            else:
                flash('Library not found.', 'error')
        else:
            flash('No operation specified.', 'error')

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Error during deletion: {str(e)}", 'error')

    return redirect(url_for('library.libraries'))




    
@bp.add_app_template_global  
def verify_file(full_path):
    if os.path.exists(full_path) or os.access(full_path, os.R_OK):
        # print(f"File Exists: {full_path}.")
        return True
    else:
        # print(f"Cannot find theme specific file: {full_path}. Using default theme file.", 'warning')
        return False