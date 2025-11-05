from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from modules.models import Library, Game, Genre, GameMode, PlayerPerspective, Theme, Image, UserPreference
from modules import db
from modules.utils_functions import format_size, get_library_count, get_games_count
from modules.utils_auth import admin_required
from modules.forms import CsrfForm, CsrfProtectForm
from sqlalchemy.orm import joinedload
from sqlalchemy import select, func, and_
from modules.utils_processors import get_global_settings
from modules import cache
import json
import urllib.parse

library_bp = Blueprint('library', __name__)

def get_saved_filters_from_cookie():
    """Parse saved filters from the libraryFilters cookie"""
    try:
        cookie_value = request.cookies.get('libraryFilters')
        if not cookie_value:
            return {}
        
        # Decode URL-encoded cookie value and parse JSON
        decoded_value = urllib.parse.unquote(cookie_value)
        saved_filters = json.loads(decoded_value)
        
        # Return only non-empty filter values
        return {k: v for k, v in saved_filters.items() if v}
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        print(f"Error parsing saved filters cookie: {e}")
        return {}

@library_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()


@library_bp.route('/libraries')
@login_required
@admin_required
def libraries():
    libraries = db.session.execute(select(Library).order_by(Library.display_order.asc())).scalars().all()
    csrf_form = CsrfProtectForm()
    game_count = db.session.execute(select(func.count(Game.id))).scalar()  # Fetch the game count here
    return render_template('admin/admin_manage_libraries.html', libraries=libraries, csrf_form=csrf_form, game_count=game_count)

@library_bp.route('/library')
@login_required
def library():
    print(f"LIBRARY: current_user: {current_user} req :", request.method)
    # Ensure user preferences are loaded or default ones are created
    if not current_user.preferences:
        print("LIBRARY: User preferences not found, creating default...")
        current_user.preferences = UserPreference(user_id=current_user.id)
        db.session.add(current_user.preferences)
        db.session.commit()

    # Start with user prefs or default
    per_page = current_user.preferences.items_per_page if current_user.preferences else 20
    sort_by = current_user.preferences.default_sort if current_user.preferences else 'name'
    sort_order = current_user.preferences.default_sort_order if current_user.preferences else 'asc'

    # Get saved filters from cookie (fallback if no URL params)
    saved_filters = get_saved_filters_from_cookie()
    
    # Extract filters from request arguments (URL params take priority over cookie)
    page = request.args.get('page', 1, type=int)
    library_uuid = request.args.get('library_uuid') or saved_filters.get('library_uuid')
    library_name = request.args.get('library_name')
    # Only override per_page, sort_by, and sort_order if the URL parameters are provided
    per_page = request.args.get('per_page', type=int) or per_page
    genre = request.args.get('genre') or saved_filters.get('genre')
    rating = request.args.get('rating', type=int) or (int(saved_filters.get('rating')) if saved_filters.get('rating') and str(saved_filters.get('rating')).isdigit() else None)
    game_mode = request.args.get('game_mode') or saved_filters.get('game_mode')
    player_perspective = request.args.get('player_perspective') or saved_filters.get('player_perspective')
    theme = request.args.get('theme') or saved_filters.get('theme')
    sort_by = request.args.get('sort_by') or sort_by
    sort_order = request.args.get('sort_order') or sort_order

    filters = {
        'library_uuid': library_uuid,
        'genre': genre,
        'rating': rating,
        'game_mode': game_mode,
        'player_perspective': player_perspective,
        'theme': theme
    }
    # Filter out None values
    filters = {k: v for k, v in filters.items() if v is not None}

    # Determine the appropriate library filter to use
    if library_uuid:
        print(f'filtering by library_uuid: {library_uuid}')
        filters['library_uuid'] = library_uuid
    elif library_name:
        print(f'filtering by library_name: {library_name}')
        library = db.session.execute(select(Library).filter_by(name=library_name)).scalars().first()
        if library:
            print(f'Library found: {library}')
            filters['library_uuid'] = library.uuid
        else:
            flash('Library not found.', 'error')
            return redirect(url_for('library.library'))

    game_data, total, pages, current_page = get_games(page, per_page, sort_by=sort_by, sort_order=sort_order, **filters)
    # dont think the 2 below are used at all. check sometime
    library_data = get_library_count()
    games_count_data = get_games_count()
    
    context = {
        'games': game_data,
        'library_count': library_data,
        'games_count': games_count_data,
        'total': total,
        'pages': pages,
        'current_page': current_page,
        'user_per_page': per_page,
        'user_default_sort': sort_by,
        'user_default_sort_order': sort_order,
        'filters': filters,
        'form': CsrfForm()
    }
    games = game_data
    library_count = library_data
    games_count = games_count_data
    total = total
    pages = pages
    current_page = current_page
    user_per_page = per_page
    user_default_sort = sort_by
    user_default_sort_order = sort_order
    filters = filters
    form = CsrfForm()

    return render_template(
        'games/library_browser.html',
        games=games,
        library_count=library_count,
        games_count=games_count,
        total=total,
        pages=pages,
        current_page=current_page,
        user_per_page=user_per_page,
        user_default_sort=user_default_sort,
        user_default_sort_order=user_default_sort_order,
        filters=filters,
        form=form,
        library_uuid = library_uuid,
        is_admin=current_user.role == 'admin'
    )


def get_games(page=1, per_page=20, sort_by='name', sort_order='asc', **filters):
    query = select(Game).options(joinedload(Game.genres))
    # Add current_user to the query to check favorite status
    current_user_id = current_user.id if current_user.is_authenticated else None
    # Resolve library_name to library_uuid if necessary
    if 'library_name' in filters and filters['library_name']:
        library = db.session.execute(select(Library).filter_by(name=filters['library_name'])).scalars().first()
        if library:
            filters['library_uuid'] = library.uuid
        else:
            return [], 0, 0, page  # No such library exists, return empty

    if 'library_uuid' in filters and filters['library_uuid']:
        query = query.filter(Game.library.has(Library.uuid == filters['library_uuid']))

    # Filtering logic
    if filters.get('library_uuid'):
        query = query.filter(Game.library_uuid == filters['library_uuid'])

    if filters.get('genre'):
        query = query.filter(Game.genres.any(Genre.name == filters['genre']))
    if filters.get('rating') is not None:
        query = query.filter(Game.rating >= filters['rating'])
    if filters.get('game_mode'):
        query = query.filter(Game.game_modes.any(GameMode.name == filters['game_mode']))
    if filters.get('player_perspective'):
        query = query.filter(Game.player_perspectives.any(PlayerPerspective.name == filters['player_perspective']))
    if filters.get('theme'):
        query = query.filter(Game.themes.any(Theme.name == filters['theme']))
    # Sorting logic
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

    # Get all user statuses for games in this page (batch query for performance)
    game_uuids = [game.uuid for game in games]
    user_statuses = {}
    if current_user_id and game_uuids:
        from modules.models import user_game_status
        status_results = db.session.execute(
            select(user_game_status.c.game_uuid, user_game_status.c.status).where(
                and_(
                    user_game_status.c.user_id == current_user_id,
                    user_game_status.c.game_uuid.in_(game_uuids)
                )
            )
        ).all()
        user_statuses = {row[0]: row[1] for row in status_results}

    game_data = []
    for game in games:
        cover_image = db.session.execute(select(Image).filter_by(game_uuid=game.uuid, image_type='cover')).scalars().first()
        cover_url = cover_image.url if cover_image else "newstyle/default_cover.jpg"
        genres = [genre.name for genre in game.genres]
        game_size_formatted = format_size(game.size)
        first_release_date_formatted = game.first_release_date.strftime('%Y-%m-%d') if game.first_release_date else 'Not available'

        # Check if game has local metadata or images
        from modules.utils_local_metadata import has_local_metadata, has_local_images
        from modules.models import GlobalSettings
        has_local_override = False
        settings = db.session.execute(select(GlobalSettings)).scalar_one_or_none()
        if settings:
            if (settings.use_local_metadata and has_local_metadata(game.full_disk_path, settings.local_metadata_filename or 'sharewarez.json')) or \
               (settings.use_local_images and has_local_images(game.full_disk_path)):
                has_local_override = True

        # Get user status for this game
        user_status = user_statuses.get(game.uuid)

        game_data.append({
            'id': game.id,
            'uuid': game.uuid,
            'name': game.name,
            'cover_url': cover_url,
            'summary': game.summary,
            'url': game.url,
            'size': game_size_formatted,
            'genres': genres,
            'is_favorite': current_user_id in [user.id for user in game.favorited_by],
            'first_release_date': first_release_date_formatted,
            'has_local_override': has_local_override,
            'user_status': user_status
        })

    return game_data, pagination.total, pagination.pages, page
