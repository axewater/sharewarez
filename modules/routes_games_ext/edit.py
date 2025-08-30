from flask import render_template, redirect, url_for, flash, copy_current_request_context, request, abort
from flask_login import login_required, current_user
from modules.forms import AddGameForm
from modules.models import Game, Library, Category, Developer, Publisher
from modules.utils_functions import read_first_nfo_content, get_folder_size_in_bytes_updates, format_size, PLATFORM_IDS
from modules.utils_auth import admin_required
from modules.utils_scanning import is_scan_job_running, refresh_images_in_background
from modules.utils_logging import log_system_event
from modules import db
from threading import Thread
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select

from . import games_bp


@games_bp.route('/game_edit/<game_uuid>', methods=['GET', 'POST'])
@login_required
@admin_required
def game_edit(game_uuid):
    game = db.session.get(Game, game_uuid) or abort(404)
    form = AddGameForm(obj=game)
    form.library_uuid.choices = [(str(lib.uuid), lib.name) for lib in db.session.execute(select(Library).order_by(Library.name)).scalars().all()]
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
        existing_game_with_igdb_id = db.session.execute(select(Game).filter(
            Game.igdb_id == form.igdb_id.data,
            Game.id != game.id
        )).scalars().first()
        
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
            developer = db.session.execute(select(Developer).filter_by(name=developer_name)).scalars().first()
            if not developer:
                developer = Developer(name=developer_name)
                db.session.add(developer)
                db.session.flush()
            game.developer = developer

        # Handling Publisher
        publisher_name = form.publisher.data
        if publisher_name:
            publisher = db.session.execute(select(Publisher).filter_by(name=publisher_name)).scalars().first()
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
        game.date_identified = datetime.now(timezone.utc)
               
        try:
            db.session.commit()
            log_system_event(f"Game {game.name} updated by admin {current_user.name}", event_type='game', event_level='information')
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
