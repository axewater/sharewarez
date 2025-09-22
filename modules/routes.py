# modules/routes.py
import sys, uuid, json, os, shutil, os
from threading import Thread
from config import Config
from flask import (
    Flask, render_template, flash, redirect, url_for, request, Blueprint, 
    jsonify, session, abort, current_app, Response,
    copy_current_request_context, g, current_app
)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case, select, delete
from werkzeug.utils import secure_filename
from modules import db, mail, cache
from functools import wraps
from datetime import datetime, timedelta, timezone
from PIL import Image as PILImage
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from modules.forms import (
    ScanFolderForm, CsrfProtectForm,
    AutoScanForm, UpdateUnmatchedFolderForm, CsrfForm,
    ReleaseGroupForm
)
from modules.models import (
    Game, Image, ScanJob, UnmatchedFolder,
    Genre, Theme, GameMode, PlayerPerspective,
    Category, Library, user_favorites,
    ReleaseGroup, AllowedFileType
)
from modules.utils_functions import load_release_group_patterns, format_size, PLATFORM_IDS
from modules.utilities import handle_auto_scan, handle_manual_scan, scan_and_add_games
from modules.utils_auth import admin_required
from modules.utils_gamenames import get_game_names_from_folder, get_game_name_by_uuid
from modules.utils_scanning import refresh_images_in_background, is_scan_job_running
from modules.utils_game_core import delete_game
from modules.utils_security import is_safe_path, get_allowed_base_directories
from modules.utils_unmatched import handle_delete_unmatched
from modules.utils_processors import get_global_settings
from modules import app_start_time, app_version

bp = Blueprint('main', __name__)
s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
has_initialized_whitelist = False
has_upgraded_admin = False
has_initialized_setup = False

# Progress tracking for library deletion
deletion_progress = {}

@bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()


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
    query = select(Game).options(joinedload(Game.genres))
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
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    games = pagination.items
    
    # Get game data
    game_data = []
    for game in games:
        cover_image = db.session.execute(select(Image).filter_by(game_uuid=game.uuid, image_type='cover')).scalars().first()
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
    release_group_form = ReleaseGroupForm()

    libraries = db.session.execute(select(Library)).scalars().all()
    form.library_uuid.choices = [(str(lib.uuid), lib.name) for lib in libraries]

    csrf_form = CsrfProtectForm()
    game_names_with_ids = None

    # Data for template consistency with scan_management
    release_groups = db.session.execute(select(ReleaseGroup).order_by(ReleaseGroup.rlsgroup.asc())).scalars().all()
    allowed_file_types = db.session.execute(select(AllowedFileType).order_by(AllowedFileType.value.asc())).scalars().all()
    
    if form.validate_on_submit():
        if form.cancel.data:
            return redirect(url_for('main.scan_folder'))
        
        folder_path = form.folder_path.data
        print(f"Scanning folder: {folder_path}")

        # Validate folder path security
        allowed_bases = get_allowed_base_directories(current_app)
        if not allowed_bases:
            flash('Service configuration error: No allowed base directories configured.', 'error')
            return render_template('admin/admin_manage_scanjobs.html',
                                  form=form, manual_form=form, csrf_form=csrf_form,
                                  game_names_with_ids=game_names_with_ids,
                                  release_group_form=release_group_form,
                                  release_groups=release_groups,
                                  allowed_file_types=allowed_file_types)
        
        # Security validation: ensure the folder path is within allowed directories
        is_safe, error_message = is_safe_path(folder_path, allowed_bases)
        if not is_safe:
            print(f"Security error: Scan folder path validation failed for {folder_path}: {error_message}")
            flash(f"Access denied: {error_message}", 'error')
            return render_template('admin/admin_manage_scanjobs.html',
                                  form=form, manual_form=form, csrf_form=csrf_form,
                                  game_names_with_ids=game_names_with_ids,
                                  release_group_form=release_group_form,
                                  release_groups=release_groups,
                                  allowed_file_types=allowed_file_types)

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
            
    return render_template('admin/admin_manage_scanjobs.html',
                          form=form,
                          manual_form=form,
                          csrf_form=csrf_form,
                          game_names_with_ids=game_names_with_ids,
                          release_group_form=release_group_form,
                          release_groups=release_groups,
                          allowed_file_types=allowed_file_types)



@bp.route('/scan_management', methods=['GET', 'POST'])
@login_required
@admin_required
def scan_management():
    auto_form = AutoScanForm()
    manual_form = ScanFolderForm()
    release_group_form = ReleaseGroupForm()

    libraries = db.session.execute(select(Library)).scalars().all()
    auto_form.library_uuid.choices = [(str(lib.uuid), lib.name) for lib in libraries]
    manual_form.library_uuid.choices = [(str(lib.uuid), lib.name) for lib in libraries]

    selected_library_uuid = request.args.get('library_uuid')
    if selected_library_uuid:
        auto_form.library_uuid.data = selected_library_uuid
        manual_form.library_uuid.data = selected_library_uuid

    jobs = db.session.execute(select(ScanJob).order_by(ScanJob.last_run.desc())).scalars().all()
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

    game_count = db.session.scalar(select(func.count(Game.id)))  # Fetch the game count here

    # Data for new tabs
    release_groups = db.session.execute(select(ReleaseGroup).order_by(ReleaseGroup.rlsgroup.asc())).scalars().all()
    allowed_file_types = db.session.execute(select(AllowedFileType).order_by(AllowedFileType.value.asc())).scalars().all()

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
        elif submit_action == 'AddReleaseGroup' and release_group_form.validate_on_submit():
            # Handle adding release group filter
            rlsgroupcs_value = release_group_form.rlsgroupcs.data == 'yes'
            new_group = ReleaseGroup(
                rlsgroup=release_group_form.rlsgroup.data,
                rlsgroupcs=rlsgroupcs_value
            )
            db.session.add(new_group)
            db.session.commit()
            flash('New release group filter added.', 'success')
            return redirect(url_for('main.scan_management', active_tab='scan_filters'))
        elif submit_action == 'DeleteReleaseGroup':
            # Handle deleting release group filter
            filter_id = request.form.get('filter_id')
            if filter_id:
                group_to_delete = db.session.get(ReleaseGroup, filter_id)
                if group_to_delete:
                    db.session.delete(group_to_delete)
                    db.session.commit()
                    flash('Release group filter removed.', 'success')
                else:
                    flash('Filter not found.', 'error')
            return redirect(url_for('main.scan_management', active_tab='scan_filters'))
        else:
            flash("Unrecognized action.", "error")
            return redirect(url_for('main.scan_management'))

    game_paths_dict = session.get('game_paths', {})
    game_names_with_ids = [{'name': name, 'full_path': path} for name, path in game_paths_dict.items()]
    # Handle active_tab from URL parameter, default to 'auto'
    active_tab = request.args.get('active_tab', 'auto')

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
                           game_names_with_ids=game_names_with_ids,
                           release_group_form=release_group_form,
                           release_groups=release_groups,
                           allowed_file_types=allowed_file_types,
                           selected_library_uuid=selected_library_uuid)


@bp.route('/cancel_scan_job/<job_id>', methods=['POST'])
@login_required
@admin_required
def cancel_scan_job(job_id):
    job = db.session.get(ScanJob, job_id)
    if job and job.status == 'Running':
        job.is_enabled = False
        job.status = 'Cancelled'
        job.error_message = 'Scan cancelled by user'
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
    job = db.session.get(ScanJob, job_id) or abort(404)    
    if job.status == 'Running':
        flash('Cannot restart a running scan.', 'error')
        return redirect(url_for('main.scan_management'))

    # Reset the existing job's counters instead of creating a new job
    job.status = 'Running'
    job.total_folders = 0
    job.folders_success = 0
    job.folders_failed = 0
    job.removed_count = 0
    job.last_run = datetime.now(timezone.utc)
    job.error_message = None
    job.is_enabled = True
    db.session.commit()

    # Start scan using the existing job
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
        download_missing_images = getattr(job, 'setting_download_missing_images', False)
        scan_and_add_games(
            full_path,
            scan_mode=scan_mode,
            library_uuid=job.library_uuid,
            remove_missing=job.setting_remove,
            existing_job=job,
            download_missing_images=download_missing_images,
            force_updates_extras_scan=getattr(job, 'setting_force_updates_extras', False)
        )

    thread = Thread(target=start_scan, daemon=True)
    thread.start()
    return redirect(url_for('main.scan_management'))


@bp.route('/edit_game_images/<game_uuid>', methods=['GET'])
@login_required
@admin_required
def edit_game_images(game_uuid):
    if is_scan_job_running():
        flash('Image editing is restricted while a scan job is running. Please try again later.', 'warning')
    game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalar_one_or_none() or abort(404)
    cover_image = db.session.execute(select(Image).filter_by(game_uuid=game_uuid, image_type='cover')).scalars().first()
    screenshots = db.session.execute(select(Image).filter_by(game_uuid=game_uuid, image_type='screenshot')).scalars().all()
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
        existing_cover = db.session.execute(select(Image).filter_by(game_uuid=game_uuid, image_type='cover')).scalars().first()
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
        image = db.session.get(Image, image_id)
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
    job = db.session.get(ScanJob, job_id) or abort(404)
    db.session.delete(job)
    db.session.commit()
    flash('Scan job deleted successfully.', 'success')
    return redirect(url_for('main.scan_management'))

@bp.route('/clear_all_scan_jobs', methods=['POST'])
@login_required
@admin_required
def clear_all_scan_jobs():
    db.session.execute(delete(ScanJob))
    db.session.commit()
    flash('All scan jobs cleared successfully.', 'success')
    return redirect(url_for('main.scan_management'))




@bp.route('/delete_all_unmatched_folders', methods=['POST'])
@login_required
@admin_required
def delete_all_unmatched_folders():
    try:
        db.session.execute(delete(UnmatchedFolder))
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
    folder = db.session.execute(select(UnmatchedFolder).filter_by(id=folder_id)).scalar_one_or_none()
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
        folder = db.session.get(UnmatchedFolder, folder_id) or abort(404)
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

@bp.route('/toggle_ignore_status/<folder_id>', methods=['POST'])
@login_required
@admin_required
def toggle_ignore_status(folder_id):
    """Toggle the ignore status of an unmatched folder."""
    try:
        folder = db.session.get(UnmatchedFolder, folder_id) or abort(404)
        # Toggle between 'Ignore' and the original status (likely 'Unmatched' or 'Duplicate')
        if folder.status == 'Ignore':
            # Restore to Unmatched or keep as Duplicate if that was the original status
            folder.status = 'Unmatched'  # Default to Unmatched when un-ignoring
        else:
            folder.status = 'Ignore'

        db.session.commit()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'success',
                'new_status': folder.status,
                'message': f'Status changed to {folder.status}'
            })
        flash(f'Folder status changed to {folder.status}.', 'success')
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': str(e)}), 500
        flash(f'Error toggling ignore status: {str(e)}', 'error')

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

    thread = Thread(target=refresh_images_in_thread, daemon=True)
    thread.start()
    print(f"Refresh images thread started for game UUID: {game_uuid} and Name: {game_name}.")

    # Check if the request is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return a JSON response for AJAX requests
        return jsonify({"message": f"Game images refresh process started for {game_name}.", "status": "info"})
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
        return jsonify({'success': False, 'message': 'Cannot delete the game while a scan job is running. Please try again later.'}), 403
    
    try:
        delete_game(game_uuid)
        return jsonify({'success': True, 'message': 'Game removed from library successfully.'}), 200
    except Exception as e:
        print(f"Error deleting game {game_uuid}: {e}")
        return jsonify({'success': False, 'message': f'Error removing game: {str(e)}'}), 500


@bp.route('/delete_folder', methods=['POST'])
@login_required
@admin_required
def delete_folder():
    data = request.get_json()
    folder_path = data.get('folder_path') if data else None

    if not folder_path:
        return jsonify({'status': 'error', 'message': 'Path is required.'}), 400

    full_path = os.path.abspath(folder_path)

    folder_entry = db.session.execute(select(UnmatchedFolder).filter_by(folder_path=folder_path)).scalar_one_or_none()

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
        return jsonify({'success': False, 'message': 'Game UUID is required.'}), 400

    if is_scan_job_running():
        print(f"Error: Attempt to delete full game UUID: {game_uuid} while scan job is running")
        return jsonify({'success': False, 'message': 'Cannot delete the game while a scan job is running. Please try again later.'}), 403

    game_to_delete = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalar_one_or_none()
    print(f"Route: /delete_full_game - Game to delete: {game_to_delete}")

    if not game_to_delete:
        print(f"Route: /delete_full_game - Game not found.")
        return jsonify({'success': False, 'message': 'Game not found.'}), 404

    full_path = game_to_delete.full_disk_path
    print(f"Route: /delete_full_game - Full path: {full_path}")

    if not os.path.exists(full_path):
        print(f"Route: /delete_full_game - Game does not exist on disk.")
        return jsonify({'success': False, 'message': 'Game does not exist on disk.'}), 404

    try:
        is_directory = os.path.isdir(full_path)
        
        if is_directory:
            print(f"Deleting game folder: {full_path}")
            shutil.rmtree(full_path)
        else:
            print(f"Deleting game file: {full_path}")
            os.remove(full_path)
        
        if os.path.exists(full_path):
            raise Exception("Deletion failed - file/folder still exists")
        
        print(f"Game deleted from disk: {full_path} - initiating database cleanup.")
        delete_game(game_uuid)
        print(f"Database and image cleanup complete.")
        
        success_message = 'Game and its folder have been deleted successfully.' if is_directory else 'Game file has been deleted successfully.'
        return jsonify({'success': True, 'message': success_message}), 200
    except Exception as e:
        error_message = f"Error deleting game from disk: {e}"
        print(error_message)
        return jsonify({'success': False, 'message': error_message}), 500


@bp.route('/delete_library_progress/<job_id>')
@login_required 
@admin_required
def delete_library_progress(job_id):
    """SSE endpoint for library deletion progress"""
    print(f"SSE endpoint accessed for job_id: {job_id} by user: {current_user.name if current_user.is_authenticated else 'Anonymous'}")
    def event_stream():
        import time
        
        # Initial delay to ensure EventSource connection is established
        time.sleep(0.2)
        
        # Send initial connection confirmation
        yield f"data: {json.dumps({'status': 'connected', 'message': 'Progress tracking connected'})}\n\n"
        
        # Wait for progress data to appear (up to 10 seconds)
        wait_count = 0
        while job_id not in deletion_progress and wait_count < 20:
            time.sleep(0.5)
            wait_count += 1
        
        if job_id not in deletion_progress:
            yield f"data: {json.dumps({'status': 'error', 'message': 'Progress data not found'})}\n\n"
            return
        
        # Stream progress updates
        while job_id in deletion_progress:
            progress_data = deletion_progress[job_id]
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            if progress_data.get('status') == 'completed' or progress_data.get('status') == 'error':
                # Keep data for a moment to ensure client receives it
                time.sleep(1)
                # Clean up after completion
                if job_id in deletion_progress:
                    del deletion_progress[job_id]
                break
            
            # Wait before checking again
            time.sleep(0.3)
    
    # Create response with proper SSE headers
    response = Response(event_stream(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    return response

def delete_library_background(library_uuid, job_id):
    """Background task for deleting a library with progress updates"""
    @copy_current_request_context
    def delete_task():
        import time
        try:
            library = db.session.execute(select(Library).filter_by(uuid=library_uuid)).scalar_one_or_none()
            if not library:
                deletion_progress[job_id] = {
                    'status': 'error',
                    'message': 'Library not found',
                    'current': 0,
                    'total': 0
                }
                return
            
            print(f"Background deletion of library: {library.name}")
            
            # Update progress - starting (give UI time to connect)
            deletion_progress[job_id].update({
                'status': 'starting',
                'message': f'Preparing to delete library "{library.name}"...',
                'current': 0,
                'total': 0
            })
            
            # Small delay to allow EventSource to connect
            time.sleep(0.5)
            
            # Safety check: Cancel any running scan jobs for this library first
            running_scan_jobs = db.session.execute(
                select(ScanJob).filter_by(library_uuid=library.uuid, status='Running')
            ).scalars().all()
            
            for running_job in running_scan_jobs:
                running_job.status = 'Failed'
                running_job.error_message = 'Scan cancelled due to library deletion'
                running_job.is_enabled = False
                print(f"Cancelled running scan job: {running_job.id}")
            
            if running_scan_jobs:
                db.session.commit()  # Commit the cancellation first
                print(f"Cancelled {len(running_scan_jobs)} running scan jobs before library deletion")
            
            # Get all games to delete
            games_to_delete = db.session.execute(select(Game).filter_by(library_uuid=library.uuid)).scalars().all()
            total_games = len(games_to_delete)
            games_deleted = 0
            games_failed = 0
            
            deletion_progress[job_id].update({
                'status': 'deleting_games',
                'total': total_games,
                'current': 0
            })
            
            # Delete games with progress updates
            for i, game in enumerate(games_to_delete, 1):
                try:
                    # Update progress
                    deletion_progress[job_id].update({
                        'current': i,
                        'message': f'Deleting game {i}/{total_games}: {game.name}',
                        'current_game': game.name
                    })
                    
                    # Use the existing delete_game function which handles all related data
                    delete_game(game.uuid)
                    games_deleted += 1
                    print(f'Successfully deleted game: {game.name}')
                    
                except FileNotFoundError as fnfe:
                    print(f'File not found for game {game.name} (UUID: {game.uuid}): {fnfe}')
                    games_deleted += 1  # Still count as deleted since it's not blocking
                except Exception as e:
                    print(f'Error deleting game {game.name} (UUID: {game.uuid}): {e}')
                    games_failed += 1
                    # Continue with other games instead of stopping
            
            # Update progress - cleaning up
            deletion_progress[job_id].update({
                'status': 'cleanup',
                'message': 'Cleaning up scan jobs and library data...',
                'current': total_games,
                'total': total_games
            })
            
            # Delete scan jobs related to this library
            scan_jobs = db.session.execute(select(ScanJob).filter_by(library_uuid=library.uuid)).scalars().all()
            for scan_job in scan_jobs:
                try:
                    db.session.delete(scan_job)
                    print(f'Deleted scan job: {scan_job.id}')
                except Exception as e:
                    print(f'Error deleting scan job {scan_job.id}: {e}')
            
            # Finally delete the library itself
            library_name = library.name
            db.session.delete(library)
            
            # Commit all changes
            db.session.commit()
            
            # Update progress - completed
            if games_failed == 0:
                message = f'Library "{library_name}" and all {games_deleted} games have been deleted successfully.'
            else:
                message = f'Library "{library_name}" deleted. {games_deleted} games deleted successfully, {games_failed} failed.'
            
            deletion_progress[job_id] = {
                'status': 'completed',
                'message': message,
                'current': total_games,
                'total': total_games,
                'games_deleted': games_deleted,
                'games_failed': games_failed,
                'library_name': library_name
            }
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error during library deletion: {str(e)}"
            print(error_msg)
            deletion_progress[job_id] = {
                'status': 'error',
                'message': error_msg,
                'current': 0,
                'total': 0
            }
    
    # Start the background task
    thread = Thread(target=delete_task, daemon=True)
    thread.start()

@bp.route('/delete_full_library/<library_uuid>', methods=['POST'])
@login_required
@admin_required
def delete_full_library(library_uuid=None):
    print(f"Route: /delete_full_library - {current_user.name} - {current_user.role} method: {request.method} UUID: {library_uuid}")
    
    if not library_uuid:
        return jsonify({'status': 'error', 'message': 'No library specified'}), 400
    
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Get library info immediately for progress tracking
    library = db.session.execute(select(Library).filter_by(uuid=library_uuid)).scalar_one_or_none()
    if not library:
        return jsonify({'status': 'error', 'message': 'Library not found'}), 404
    
    # Create initial progress data immediately in main thread to prevent race condition
    deletion_progress[job_id] = {
        'status': 'initializing',
        'message': f'Preparing to delete library "{library.name}"...',
        'current': 0,
        'total': 0,
        'library_name': library.name
    }
    
    # Start background deletion
    delete_library_background(library_uuid, job_id)
    
    # Return job ID for progress tracking
    return jsonify({'status': 'started', 'job_id': job_id})

@bp.route('/check_deletion_progress/<job_id>')
@login_required
@admin_required
def check_deletion_progress(job_id):
    """Simple progress check endpoint as fallback for SSE"""
    if job_id in deletion_progress:
        return jsonify(deletion_progress[job_id])
    else:
        return jsonify({'status': 'not_found', 'message': 'Job not found'}), 404

    
@bp.add_app_template_global
def verify_file(full_path):
    if os.path.exists(full_path) or os.access(full_path, os.R_OK):
        return True
    else:
        return False

@bp.app_template_filter('theme_asset')
def theme_asset_filter(path):
    """Convert a relative theme path to the correct themed URL with fallback to default"""
    from flask_login import current_user

    # Get current theme from user preferences or default
    if current_user.is_authenticated and hasattr(current_user, 'preferences') and current_user.preferences:
        current_theme = current_user.preferences.theme or 'default'
    else:
        current_theme = 'default'

    # Check if themed asset exists
    full_path = f'./modules/static/library/themes/{current_theme}/{path}'
    if os.path.exists(full_path):
        return url_for('static', filename=f'library/themes/{current_theme}/{path}')

    # Fallback to default theme
    return url_for('static', filename=f'library/themes/default/{path}')
