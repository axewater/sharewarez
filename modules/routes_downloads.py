import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from threading import Thread
from flask import copy_current_request_context
from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError
from modules.forms import CsrfProtectForm
from modules.models import Game, DownloadRequest, GameUpdate, GameExtra, GlobalSettings
from modules.utils_processors import get_global_settings
from modules.utils_functions import get_folder_size_in_bytes, format_size
from modules.utils_download import zip_game, zip_folder, update_download_request
from modules.utils_auth import admin_required
from modules import db
from modules import cache

download_bp = Blueprint('download', __name__)

@download_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()


@download_bp.context_processor
def inject_current_theme():
    if current_user.is_authenticated and current_user.preferences:
        current_theme = current_user.preferences.theme or 'default'
    else:
        current_theme = 'default'
    return dict(current_theme=current_theme)

@download_bp.route('/downloads')
@login_required
def downloads():
    user_id = current_user.id
    print(f"Route: /downloads user_id: {user_id}")
    download_requests = DownloadRequest.query.filter_by(user_id=user_id).all()
    for download_request in download_requests:
        download_request.formatted_size = format_size(download_request.download_size)
    form = CsrfProtectForm()
    return render_template('games/manage_downloads.html', download_requests=download_requests, form=form)

@download_bp.route('/download_game/<game_uuid>', methods=['GET'])
@login_required
def download_game(game_uuid):
    print(f"Downloading game with UUID: {game_uuid}")
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    print(f"Game found: {game}")

    # Check for any existing download request for the same game by the current user, regardless of status
    existing_request = DownloadRequest.query.filter_by(user_id=current_user.id, file_location=game.full_disk_path).first()
    
    if existing_request:
        flash("You already have a download request for this game in your basket. Please check your downloads page.", "info")
        return redirect(url_for('download.downloads'))
    
    if os.path.isdir(game.full_disk_path):
        # List all files, case-insensitively excluding .NFO and .SFV files, and file_id.diz
        files_in_directory = [f for f in os.listdir(game.full_disk_path) if os.path.isfile(os.path.join(game.full_disk_path, f))]
        significant_files = [f for f in files_in_directory if not f.lower().endswith(('.nfo', '.sfv')) and not f.lower() == 'file_id.diz']

        # If more than one significant file remains, expect a zip file
        if len(significant_files) > 1:
            zip_save_path = current_app.config['ZIP_SAVE_PATH']
            zip_file_path = os.path.join(zip_save_path, f"{game.name}.zip")
        else:
            zip_file_path = os.path.join(game.full_disk_path, significant_files[0])
    else:
        zip_file_path = game.full_disk_path
        
    print(f"Creating a new download request for user {current_user.id} for game {game_uuid}")
    new_request = DownloadRequest(
        user_id=current_user.id,
        game_uuid=game.uuid,
        status='processing',  
        download_size=game.size,
        file_location=game.full_disk_path,
        zip_file_path=zip_file_path
    )
    db.session.add(new_request)
    game.times_downloaded += 1
    db.session.commit()

    # Start the download process (potentially in a new thread as before)
    @copy_current_request_context
    def thread_function():
        print(f"Thread function started for download request {new_request.id}")
        zip_game(new_request.id, current_app._get_current_object(), zip_file_path)

    thread = Thread(target=thread_function)
    thread.start()

    flash("Your download request is being processed. You will be notified when the download is ready.", "info")
    return redirect(url_for('download.downloads'))

@download_bp.route('/download_other/<file_type>/<game_uuid>/<file_id>', methods=['GET'])
@login_required
def download_other(file_type, game_uuid, file_id):
    """Handle downloads for update and extra files"""
    
    # Validate file_type
    if file_type not in ['update', 'extra']:
        flash("Invalid file type", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))

    FileModel = GameUpdate if file_type == 'update' else GameExtra
    # Fetch the file record
    file_record = FileModel.query.filter_by(id=file_id, game_uuid=game_uuid).first()
    
    if not file_record:
        flash(f"{file_type.capitalize()} file not found", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))

    # Check if the file or folder exists
    if not os.path.exists(file_record.file_path):
        flash("File not found on disk", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))

    # Check for an existing download request
    existing_request = DownloadRequest.query.filter_by(
        user_id=current_user.id,
        file_location=file_record.file_path
    ).first()
    if existing_request:
        flash("You already have a download request for this file", "info")
        return redirect(url_for('download.downloads'))
    try:
        # Determine if the path is a file or a directory
        if os.path.isfile(file_record.file_path):
            # If it's already a zip file, set it as available
            if file_record.file_path.lower().endswith('.zip'):
                zip_file_path = file_record.file_path
                status = 'available'
            else:
                # For single files that aren't zips, create a zip
                zip_file_path = os.path.join(current_app.config['ZIP_SAVE_PATH'], f"{uuid4()}_{os.path.basename(file_record.file_path)}.zip")
                status = 'processing'
        else:
            # It's a directory; create a zip
            zip_file_path = os.path.join(current_app.config['ZIP_SAVE_PATH'], f"{uuid4()}_{os.path.basename(file_record.file_path)}.zip")
            status = 'processing'
        # Create a new download request
        new_request = DownloadRequest(
            user_id=current_user.id,
            game_uuid=game_uuid,
            status=status,
            download_size=0,  # Will be set after zipping
            file_location=file_record.file_path,
            zip_file_path=zip_file_path
        )
        
        db.session.add(new_request)
        file_record.times_downloaded += 1
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        flash("Database error occurred", "error")
        return redirect(url_for('games.game_details', game_uuid=game_uuid))

    # Start the download process in a background thread
    @copy_current_request_context
    def process_download():
        try:
            import zipfile
            if os.path.isfile(file_record.file_path):
                if file_record.file_path.lower().endswith('.zip'):
                    # Directly mark as available
                    update_download_request(new_request, 'available', file_record.file_path)
                else:
                    # Zip the single file
                    with zipfile.ZipFile(zip_file_path, 'w') as zipf:
                        zipf.write(file_record.file_path, arcname=os.path.basename(file_record.file_path))
                    new_request.download_size = os.path.getsize(zip_file_path)
                    update_download_request(new_request, 'available', zip_file_path)
            else:
                # Zip the entire directory
                with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(file_record.file_path):
                        for file in files:
                            abs_file_path = os.path.join(root, file)
                            relative_path = os.path.relpath(abs_file_path, os.path.dirname(file_record.file_path))
                            zipf.write(abs_file_path, arcname=relative_path)
                new_request.download_size = os.path.getsize(zip_file_path)
                update_download_request(new_request, 'available', zip_file_path)
        except Exception as e:
            with current_app.app_context():
                update_download_request(new_request, 'failed', str(e))
            print(f"Error during download processing: {e}")

    thread = Thread(target=process_download)
    thread.start()

    flash("Your download request is being processed. You will be notified when it's ready.", "info")
    return redirect(url_for('download.downloads'))


@download_bp.route('/download_file/<file_location>/<file_size>/<game_uuid>/<file_name>', methods=['GET'])
@login_required
def download_file(file_location, file_size, game_uuid, file_name):
    settings = GlobalSettings.query.first()
    game = get_game_by_uuid(game_uuid)
    
    if file_location == "updates":
        # Query the update record directly
        update = GameUpdate.query.filter_by(game_uuid=game_uuid, file_path=file_name).first()
        if update:
            file_location = update.file_path
        else:
            print(f"Update file not found for game {game_uuid}")
            flash("Update file not found", "error")
            return redirect(url_for('games.game_details', game_uuid=game_uuid))
    elif file_location == "extras":
        # Query the extra record directly
        extra = GameExtra.query.filter_by(game_uuid=game_uuid, file_path=file_name).first()
        if extra:
            file_location = extra.file_path
        else:
            print(f"Extra file not found for game {game_uuid}")
            flash("Extra file not found", "error")
            return redirect(url_for('games.game_details', game_uuid=game_uuid))
    else:
        print(f"Error - No location: {file_location}")
        return
    
    print(f"Downloading file with location: {file_location}")
    if os.path.isfile(file_location):
        file_size_stripped = ''.join(filter(str.isdigit, file_size))
        file_size_bytes = int(file_size_stripped)*10000
        zip_file_path = file_location
    else:
        file_size_bytes = get_folder_size_in_bytes(file_location)
        zip_save_path = current_app.config['ZIP_SAVE_PATH']
        zip_file_path = os.path.join(zip_save_path, f"{file_name}.zip")
        
    # Check for any existing download request for the same file by the current user, regardless of status
    existing_request = DownloadRequest.query.filter_by(user_id=current_user.id, file_location=file_location).first()
    
    if existing_request:
        flash("You already have a download request for this file in your basket. Please check your downloads page.", "info")
        return redirect(url_for('download.downloads'))

    print(f"Creating a new download request for user {current_user.id} for file {file_location}")
    new_request = DownloadRequest(
        user_id=current_user.id,
        zip_file_path=zip_file_path,
        status='processing',  
        download_size=file_size_bytes,
        game_uuid=game_uuid,
        file_location=file_location
    )
    db.session.add(new_request)
    db.session.commit()

    # Start the download process (potentially in a new thread as before)
    @copy_current_request_context
    def thread_function():
        print(f"Thread function started for download request {new_request.id}")
        zip_folder(new_request.id, current_app._get_current_object(), file_location, file_name)

    thread = Thread(target=thread_function)
    thread.start()
    
    flash("Your download request is being processed. You will be notified when the download is ready.", "info")
    return redirect(url_for('download.downloads'))


@download_bp.route('/download_zip/<download_id>')
@login_required
def download_zip(download_id):
    print(f"Downloading zip with ID: {download_id}")
    download_request = DownloadRequest.query.filter_by(id=download_id, user_id=current_user.id).first_or_404()
    
    if download_request.status != 'available':
        flash("The requested download is not ready yet.")
        return redirect(url_for('library.library'))

    relative_path = download_request.zip_file_path
    absolute_path = os.path.join(current_app.static_folder, relative_path)
    
    if not os.path.exists(absolute_path):
        flash("Error: File does not exist.")
        return redirect(url_for('library.library'))

    print(f"Found download request available: {download_request}")

    try:
        
        directory = os.path.dirname(absolute_path)
        filename = os.path.basename(absolute_path)
        # Serve the file
        print(f"Sending file: {directory}/{filename} to user {current_user.id} for download")
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        flash("An error occurred while trying to serve the file.")
        print(f"Error: {e}") 
        return redirect(url_for('library.library'))

@download_bp.route('/check_download_status/<download_id>')
@login_required
def check_download_status(download_id):
    download_request = DownloadRequest.query.filter_by(id=download_id, user_id=current_user.id).first()
    
    if download_request:
        return jsonify({
            'status': download_request.status,
            'downloadId': download_request.id,
            'found': True
        })
    
    return jsonify({
        'status': 'not_found',
        'downloadId': download_id,
        'found': False
    }), 200


@download_bp.route('/delete_download_request/<int:request_id>', methods=['POST'])
@login_required
@admin_required
def delete_download_request(request_id):
    download_request = DownloadRequest.query.get_or_404(request_id)
    
    if download_request.zip_file_path and os.path.exists(download_request.zip_file_path):
        if download_request.zip_file_path.startswith(current_app.config['ZIP_SAVE_PATH']):
            try:
                os.remove(download_request.zip_file_path)
                print(f"Deleted ZIP file: {download_request.zip_file_path}")
            except Exception as e:
                print(f"Error deleting ZIP file: {e}")
                flash(f"Error deleting ZIP file: {e}", 'error')
        else:
            print(f"ZIP file is not in the expected directory: {download_request.zip_file_path}")
            flash("ZIP file is not in the expected directory. Only the download request will be removed.", 'warning')
    
    db.session.delete(download_request)
    db.session.commit()
    
    flash('Download request deleted successfully.', 'success')
    return redirect(url_for('main.manage_downloads'))


@download_bp.route('/delete_download/<int:download_id>', methods=['POST'])
@login_required
def delete_download(download_id):
    download_request = DownloadRequest.query.filter_by(id=download_id, user_id=current_user.id).first_or_404()
    zip_save_path = current_app.config['ZIP_SAVE_PATH']
    # Allow deletion regardless of status
    if download_request.zip_file_path and os.path.exists(download_request.zip_file_path):
        # Only delete the file if it's a generated zip file in our ZIP_SAVE_PATH
        try:
            file_path = os.path.abspath(download_request.zip_file_path)
            zip_save_path = os.path.abspath(zip_save_path)
            
            if file_path.startswith(zip_save_path):
                os.remove(file_path)
                flash('Zipped download deleted successfully.', 'success')
            else:
                # For direct file downloads, just remove the download request
                flash('Download request removed. Original file preserved.', 'info')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while deleting the file: {e}', 'danger')
            return redirect(url_for('download.downloads'))
        else:
            flash('Only the download request was deleted, the original game file was not removed.', 'info')
    else:
        flash('No file found to delete, only the download request was removed.', 'info')
    db.session.delete(download_request)
    db.session.commit()

    return redirect(url_for('download.downloads'))