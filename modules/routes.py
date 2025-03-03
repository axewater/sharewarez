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
    AutoScanForm, UpdateUnmatchedFolderForm, CsrfForm
)
from modules.models import (
    Game, Image, ScanJob, UnmatchedFolder,
    Genre, Theme, GameMode, PlayerPerspective,
    Category, Library, user_favorites
)
from modules.utils_functions import load_release_group_patterns, format_size, PLATFORM_IDS
from modules.utilities import handle_auto_scan, handle_manual_scan, scan_and_add_games
from modules.utils_auth import admin_required
from modules.utils_gamenames import get_game_names_from_folder, get_game_name_by_uuid
from modules.utils_scanning import refresh_images_in_background, is_scan_job_running
from modules.utils_game_core import delete_game
from modules.utils_unmatched import handle_delete_unmatched
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

@bp.route('/restart_scan_job/<job_id>', methods=['POST'])
@login_required
@admin_required
def restart_scan_job(job_id):
    print(f"Request to restart scan job: {job_id}")
    job = ScanJob.query.get_or_404(job_id)    
    if job.status == 'Running':
        flash('Cannot restart a running scan.', 'error')
        return redirect(url_for('main.scan_management'))

    # Start a new scan using the existing job's settings
    @copy_current_request_context
    def start_scan():
        base_dir = current_app.config.get('BASE_FOLDER_WINDOWS') if os.name == 'nt' else current_app.config.get('BASE_FOLDER_POSIX')
        full_path = os.path.join(base_dir, job.scan_folder)
        
        if not os.path.exists(full_path) or not os.access(full_path, os.R_OK):
            job.status = 'Failed'
            job.error_message = f"Cannot access folder: {full_path}"
            db.session.commit()
            return

        scan_mode = 'files' if job.setting_filefolder else 'folders'
        scan_and_add_games(
            full_path,
            scan_mode=scan_mode,
            library_uuid=job.library_uuid,
            remove_missing=job.setting_remove
        )

    thread = Thread(target=start_scan)
    thread.start()
    return redirect(url_for('main.scan_management'))


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
    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif'}
    filename = secure_filename(file.filename)
    file_extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    if file_extension not in allowed_extensions:
        return jsonify({'error': 'Only JPG, PNG and GIF files are allowed'}), 400

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
        UnmatchedFolder.query.delete()
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


@bp.route('/update_unmatched_folder_status', methods=['POST'])
@login_required
@admin_required
def update_unmatched_folder_status():
    print("Route: /update_unmatched_folder_status")
    folder_id = request.form.get('folder_id')
    session['active_tab'] = 'unmatched'
    folder = UnmatchedFolder.query.filter_by(id=folder_id).first()
    if folder:
        # Toggle between 'Ignore' and 'Unmatched'
        folder.status = 'Unmatched' if folder.status == 'Ignore' else 'Ignore'
        try:
            db.session.commit()
            response_data = {
                'status': 'success',
                'new_status': folder.status,
                'message': f'Folder status updated to {folder.status}'
            }
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(response_data)
            flash(response_data['message'], 'success')
        except SQLAlchemyError as e:
            error_msg = f'Error updating folder status: {str(e)}'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': error_msg}), 500
            db.session.rollback()
            flash(error_msg, 'error')
    else:
        flash('Folder not found.', 'error')

    return redirect(url_for('main.scan_management'))

@bp.route('/clear_unmatched_entry/<folder_id>', methods=['POST'])
@login_required
@admin_required
def clear_unmatched_entry(folder_id):
    """Clear a single unmatched folder entry from the database."""
    try:
        folder = UnmatchedFolder.query.get_or_404(folder_id)
        db.session.delete(folder)
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'success', 'message': 'Entry cleared successfully'})
        flash('Unmatched folder entry cleared successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': str(e)}), 500
        flash(f'Error clearing unmatched folder entry: {str(e)}', 'error')
    return redirect(url_for('main.scan_management'))


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
@login_required
@admin_required
def delete_full_library(library_uuid=None):
    print(f"Route: /delete_full_library - {current_user.name} - {current_user.role} method: {request.method} UUID: {library_uuid}")
    try:
        if library_uuid:
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
            flash('No library specified.', 'error')
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Error during deletion: {str(e)}", 'error')

    return redirect(url_for('library.libraries'))

    
@bp.add_app_template_global  
def verify_file(full_path):
    if os.path.exists(full_path) or os.access(full_path, os.R_OK):
        return True
    else:
        return False
