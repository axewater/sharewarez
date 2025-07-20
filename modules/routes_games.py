import os, uuid
from flask import Blueprint, render_template, redirect, url_for, flash, copy_current_request_context, jsonify, abort, session, request
from flask_login import login_required, current_user
from modules.forms import AddGameForm, CsrfForm
from modules.models import Game, Library, UnmatchedFolder, Category, Developer, Publisher, GameUpdate, GameExtra
from modules.utils_processors import get_global_settings
from modules.utils_functions import read_first_nfo_content, get_folder_size_in_bytes_updates, format_size, PLATFORM_IDS
from modules.utils_auth import admin_required
from modules.utils_scanning import is_scan_job_running, refresh_images_in_background
from modules.utils_logging import log_system_event
from modules.utils_game_core import check_existing_game_by_igdb_id, get_game_by_uuid
from modules import cache, db
from threading import Thread
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

games_bp = Blueprint('games', __name__)

@games_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()


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

        try:
            db.session.add(new_game)
            db.session.commit()
            flash('Game added successfully.', 'success')
            log_system_event(f"Game {game_name} added manually by admin {current_user.name}",  event_type='game', event_level='information')
            
            if full_disk_path: 
                unmatched_folder = UnmatchedFolder.query.filter_by(folder_path=full_disk_path).first()
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

@games_bp.route('/game_edit/<game_uuid>', methods=['GET', 'POST'])
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


@games_bp.route('/game_details/<string:game_uuid>')
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
