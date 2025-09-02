import os
from flask import render_template, redirect, url_for, flash, copy_current_request_context, session, request, current_app
from flask_login import login_required, current_user
from modules.forms import AddGameForm
from modules.models import Game, Library, UnmatchedFolder, Category, Developer, Publisher
from modules.utils_functions import read_first_nfo_content, PLATFORM_IDS
from modules.utils_auth import admin_required
from modules.utils_scanning import is_scan_job_running, refresh_images_in_background
from modules.utils_logging import log_system_event
from modules.utils_security import is_safe_path, get_allowed_base_directories
from modules.utils_game_core import check_existing_game_by_igdb_id
from modules import db
from threading import Thread
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select

from . import games_bp


@games_bp.route('/add_game_manual', methods=['GET', 'POST'])
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
    form.library_uuid.choices = [(str(library.uuid), library.name) for library in db.session.execute(select(Library).order_by(Library.name)).scalars().all()]
    print(f'agm Library choices: {form.library_uuid.choices}')
    
    # Fetch library details for displaying on the form
    library_uuid = request.args.get('library_uuid')
    library = db.session.execute(select(Library).filter_by(uuid=library_uuid)).scalars().first()
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
        # Validate full_disk_path security
        allowed_bases = get_allowed_base_directories(current_app)
        if not allowed_bases:
            flash('Service configuration error: No allowed base directories configured.', 'error')
            return render_template('admin/admin_game_identify.html', form=form, library_uuid=library_uuid, library_name=library_name, platform_name=platform_name, platform_id=platform_id)

        is_safe, error_message = is_safe_path(form.full_disk_path.data, allowed_bases)
        if not is_safe:
            print(f"Security error: Game path validation failed for {form.full_disk_path.data}: {error_message}")
            flash(f"Access denied: {error_message}", 'error')
            return render_template('admin/admin_game_identify.html', form=form, library_uuid=library_uuid, library_name=library_name, platform_name=platform_name, platform_id=platform_id)

        # Check if this is a custom IGDB ID (above 2,000,000,420)
        is_custom_game = int(form.igdb_id.data) >= 2000000420
        
        # For custom games, skip IGDB ID check
        if not is_custom_game and check_existing_game_by_igdb_id(form.igdb_id.data):
            flash('A game with this IGDB ID already exists.', 'error')
            return render_template('admin/admin_game_identify.html', form=form, library_uuid=library_uuid, library_name=library_name, platform_name=platform_name, platform_id=platform_id)
        
        new_game = Game(
            igdb_id=form.igdb_id.data,
            name=form.name.data,
            summary=form.summary.data,
            storyline=form.storyline.data,
            url=form.url.data,
            full_disk_path=form.full_disk_path.data,
            # Set default cover for custom games
            cover=url_for('static', filename='newstyle/default_cover.jpg') if is_custom_game else None,
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
            developer = db.session.execute(select(Developer).filter_by(name=form.developer.data)).scalars().first()
            if not developer:
                developer = Developer(name=form.developer.data)
                db.session.add(developer)
                db.session.flush() 
            new_game.developer = developer

        if form.publisher.data and form.publisher.data != 'Not Found':
            publisher = db.session.execute(select(Publisher).filter_by(name=form.publisher.data)).scalars().first()
            if not publisher:
                publisher = Publisher(name=form.publisher.data)
                db.session.add(publisher)
                db.session.flush()
            new_game.publisher = publisher
        new_game.nfo_content = read_first_nfo_content(form.full_disk_path.data)

        try:
            db.session.add(new_game)
            db.session.commit()
            flash('Game added successfully.', 'success')
            log_system_event(f"Game {game_name} added manually by admin {current_user.name}",  event_type='game', event_level='information')
            
            if full_disk_path: 
                unmatched_folder = db.session.execute(select(UnmatchedFolder).filter_by(folder_path=full_disk_path)).scalars().first()
                if unmatched_folder:
                    db.session.delete(unmatched_folder)
                    print("Deleted unmatched folder:", unmatched_folder)
                    db.session.commit()
            print(f"add_game_manual Game: {game_name} added by user {current_user.name}.")
            log_system_event(f"Game {game_name} added manually by user {current_user.name}", event_type='game', event_level='information')
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
