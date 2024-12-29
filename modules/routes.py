# modules/routes.py
import sys, uuid, json, os, shutil, os
from threading import Thread
from config import Config
from flask import (
    Flask, render_template, flash, redirect, url_for, request, Blueprint, 
    jsonify, session, abort, current_app, send_from_directory, 
    copy_current_request_context, g, current_app
)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case
from werkzeug.utils import secure_filename
from modules import db, mail, cache
from functools import wraps
from uuid import uuid4
from datetime import datetime, timedelta
from PIL import Image as PILImage
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from modules.forms import (
    UserPasswordForm, EditProfileForm, 
    ScanFolderForm, ClearDownloadRequestsForm, CsrfProtectForm, 
    AddGameForm, LoginForm, ResetPasswordRequestForm, AutoScanForm,
    UpdateUnmatchedFolderForm, RegistrationForm, UserPreferencesForm, 
    InviteForm, CsrfForm
)
from modules.models import (
    User, Whitelist, Game, Image, DownloadRequest, ScanJob, UnmatchedFolder,
    Publisher, Developer, Genre, Theme, GameMode, PlayerPerspective, GameUpdate, GameExtra,
    Category, UserPreference, GameURL, GlobalSettings, InviteToken, Library, AllowedFileType,
    user_favorites
)
from modules.utilities import (
    scan_and_add_games
)
from modules.utils_auth import _authenticate_and_redirect, admin_required
from modules.utils_smtp import send_email, send_password_reset_email, send_invite_email
from modules.utils_gamenames import get_game_names_from_folder, get_game_names_from_files
from modules.utils_scanning import refresh_images_in_background, delete_game_images
from modules.utils_game_core import get_game_by_uuid, check_existing_game_by_igdb_id
from modules.utils_download import update_download_request, zip_folder, zip_game
from modules.utils_functions import square_image, load_release_group_patterns, get_folder_size_in_bytes, get_folder_size_in_bytes_updates, format_size, read_first_nfo_content, PLATFORM_IDS
from modules.utils_igdb_api import make_igdb_api_request, get_cover_thumbnail_url
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


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.discover'))

    print("Route: /login")
    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(name=username).first()

        if user:
            if not user.is_email_verified:
                flash('Your account is not activated, check your email.', 'warning')
                return redirect(url_for('main.login'))

            if not user.state:
                flash('Your account has been banned.', 'error')
                print(f"Error: Attempted login to disabled account - User: {username}")
                return redirect(url_for('main.login'))

            return _authenticate_and_redirect(username, password)
        else:
            flash('Invalid username or password. USERNAMES ARE CASE SENSITIVE!', 'error')
            return redirect(url_for('main.login'))

    return render_template('login/login.html', form=form)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.login'))
    print("Route: /register")

    # Attempt to get the invite token from the query parameters
    invite_token_from_url = request.args.get('token')
    print(f"Invite token from URL: {invite_token_from_url}")
    invite = None
    if invite_token_from_url:
        invite = InviteToken.query.filter_by(token=invite_token_from_url, used=False).first()
        print(f"Invite found: {invite}")
        if invite and invite.expires_at >= datetime.utcnow():
            # The invite is valid; skip the whitelist check later
            pass
        else:
            invite = None  # Invalidate
            flash('The invite is invalid or has expired.', 'warning')
            return redirect(url_for('main.register'))
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            email_address = form.email.data.lower()
            existing_user_email = User.query.filter(func.lower(User.email) == email_address).first()
            if existing_user_email:
                print(f"/register: Email already in use - {email_address}")
                flash('This email is already in use. Please use a different email or log in.')
                return redirect(url_for('main.register'))
                    # Proceed with the whitelist check only if no valid invite token is provided
            if not invite:
                whitelist = Whitelist.query.filter(func.lower(Whitelist.email) == email_address).first()
                if not whitelist:
                    flash('Your email is not whitelisted.')
                    return redirect(url_for('main.register'))

            existing_user = User.query.filter_by(name=form.username.data).first()
            if existing_user is not None:
                print(f"/register: User already exists - {form.username.data}")
                flash('User already exists. Please Log in.')
                return redirect(url_for('main.register'))

            user_uuid = str(uuid4())
            existing_uuid = User.query.filter_by(user_id=user_uuid).first()
            if existing_uuid is not None:
                print("/register: UUID collision detected.")
                flash('An error occurred while registering. Please try again.')
                return redirect(url_for('main.register'))

            user = User(
                user_id=user_uuid,
                name=form.username.data,
                email=form.email.data.lower(),  # Ensuring lowercase
                role='user',
                is_email_verified=False,
                email_verification_token=s.dumps(form.email.data, salt='email-confirm'),
                token_creation_time=datetime.utcnow(),
                created=datetime.utcnow()
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            print(f"Invite Token from URL: {invite_token_from_url}")

            if invite:
                print(f"Found valid invite: {invite.token}, expires at: {invite.expires_at}, used: {invite.used}")
                invite.used = True
                invite.used_by = user.user_id
                invite.used_at = datetime.utcnow()
                db.session.commit()
            else:
                print("No valid invite found or invite expired/used.")
            # Verification email
            verification_token = user.email_verification_token
            confirm_url = url_for('main.confirm_email', token=verification_token, _external=True)
            html = render_template('login/registration_activate.html', confirm_url=confirm_url)
            subject = "Please confirm your email"
            send_email(user.email, subject, html)


            flash('A confirmation email has been sent via email.', 'success')
            return redirect(url_for('site.index'))
        except IntegrityError as e:
            db.session.rollback()
            print(f"IntegrityError occurred: {e}")
            flash('error while registering. Please try again.')

    return render_template('login/registration.html', title='Register', form=form)


@bp.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=900)  # 15 minutes
    except SignatureExpired:
        return render_template('login/confirmation_expired.html'), 400
    except BadSignature:
        return render_template('login/confirmation_invalid.html'), 400

    user = User.query.filter_by(email=email).first_or_404()
    if user.is_email_verified:
        return render_template('login/registration_already_confirmed.html')
    else:
        user.is_email_verified = True
        db.session.add(user)
        db.session.commit()
        return render_template('login/confirmation_success.html')



@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.login'))
    print(f'pwr Reset Password Request')
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        print(f'pwr form data: {form.data}')
        user = User.query.filter_by(email=form.email.data.lower()).first()
        print(f'pwr user: {user}')
        if user:
            # Generate a unique token
            token = s.dumps(user.email, salt='password-reset-salt')
            user.password_reset_token = token
            user.token_creation_time = datetime.utcnow()
            print(f'pwr token: {token}')
            db.session.commit()

            # Send reset email
            print('Calling send password reset email function...')
            send_password_reset_email(user.email, token)
            flash('Check your email for instructions to reset your password.')
            return redirect(url_for('main.login'))
        else:
            flash('Email address not found.')
            return redirect(url_for('main.reset_password_request'))

    return render_template('login/reset_password_request.html', title='Reset Password', form=form)

@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.login'))

    user = User.query.filter_by(password_reset_token=token).first()
    if not user or user.token_creation_time + timedelta(minutes=15) < datetime.utcnow():
        flash('The password reset link is invalid or has expired.')
        return redirect(url_for('main.login'))

    form = CsrfProtectForm()

    if form.validate_on_submit():
        new_password = request.form['password']
        confirm_password = request.form['confirm_password']
        if new_password != confirm_password:
            flash('Passwords do not match.')
            return render_template('reset_password.html', form=form, token=token)
        user.set_password(new_password)
        user.password_reset_token = None
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('main.login'))

    return render_template('login/reset_password.html', form=form, token=token)


@bp.route('/login/invites', methods=['GET', 'POST'])
@login_required
def invites():
    settings = GlobalSettings.query.first()
    site_url = settings.site_url if settings else 'http://127.0.0.1'
    if site_url == 'http://127.0.0.1'and current_user.role == 'admin':
        flash('Please configure the site URL in the admin settings.', 'danger')
    form = InviteForm()
    if form.validate_on_submit():
        email = request.form.get('email')
        # Ensure the user has invites left to send
        current_invites = InviteToken.query.filter_by(creator_user_id=current_user.user_id, used=False).count()
        if current_user.invite_quota > current_invites:
            token = str(uuid.uuid4())
            invite_token = InviteToken(
                token=token, 
                creator_user_id=current_user.user_id,
                recipient_email=email
            )
            db.session.add(invite_token)
            db.session.commit()

            settings = GlobalSettings.query.first()
            site_url = settings.site_url if settings else 'http://127.0.0.1'
            
            # Build the invite URL using the configured site URL
            invite_url = f"{site_url}/register?token={token}"

            send_invite_email(email, invite_url)

            flash('Invite sent successfully. The invite expires after 48 hours.', 'success')
        else:
            flash('You have reached your invite limit.', 'danger')
        return redirect(url_for('main.invites'))

    invites = InviteToken.query.filter_by(creator_user_id=current_user.user_id, used=False).all()
    current_invites_count = len(invites)
    remaining_invites = max(0, current_user.invite_quota - current_invites_count)

    return render_template('/login/user_invites.html', form=form, invites=invites, invite_quota=current_user.invite_quota, site_url=site_url, current_invites_count=current_invites_count, remaining_invites=remaining_invites, datetime=datetime.utcnow())

@bp.route('/delete_invite/<token>', methods=['POST'])
@login_required
def delete_invite(token):
    try:
        invite = InviteToken.query.filter_by(token=token, creator_user_id=current_user.user_id).first()
        if invite:
            db.session.delete(invite)
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Invite not found or you do not have permission to delete it.'})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting invite: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while deleting the invite.'}), 500






@bp.route('/api/current_user_role', methods=['GET'])
@login_required
def get_current_user_role():
    return jsonify({'role': current_user.role}), 200

@bp.route('/api/check_username', methods=['POST'])
@login_required
def check_username():
    print(F"Route: /api/check_username - {current_user.name} - {current_user.role}")    
    data = request.get_json()
    username = data.get('username')
    if not username:
        print(f"Check username: Missing username")
        return jsonify({"error": "Missing username parameter"}), 400
    print(f"Checking username: {username}")
    existing_user = User.query.filter(func.lower(User.name) == func.lower(username)).first()
    return jsonify({"exists": existing_user is not None})


@bp.route('/settings_profile_edit', methods=['GET', 'POST'])
@login_required
def settings_profile_edit():
    print("Route: Settings profile edit")
    form = EditProfileForm()

    if form.validate_on_submit():
        file = form.avatar.data
        if file:
            # Ensure UPLOAD_FOLDER exists
            upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'images/avatars_users')
            if not os.path.exists(upload_folder):
                try:
                    # Safe check to avoid creating 'static' directly
                    os.makedirs(upload_folder, exist_ok=True)
                except Exception as e:
                    print(f"Error creating upload directory: {e}")
                    flash("Error processing request. Please try again.", 'error')
                    return redirect(url_for('main.settings_profile_edit'))

            old_avatarpath = current_user.avatarpath
            if old_avatarpath and old_avatarpath != 'newstyle/avatar_default.jpg':
                old_thumbnailpath = os.path.splitext(old_avatarpath)[0] + '_thumbnail' + os.path.splitext(old_avatarpath)[1]
            else:
                old_thumbnailpath = None
            filename = secure_filename(file.filename)
            uuid_filename = str(uuid4()) + '.' + filename.rsplit('.', 1)[1].lower()
            image_path = os.path.join(upload_folder, uuid_filename)
            file.save(image_path)
            # Image processing
            img = PILImage.open(image_path)
            img = square_image(img, 500)
            img.save(image_path)
            img = PILImage.open(image_path)
            img = square_image(img, 50)
            thumbnail_path = os.path.splitext(image_path)[0] + '_thumbnail' + os.path.splitext(image_path)[1]
            img.save(thumbnail_path)
            if old_avatarpath and old_avatarpath != 'newstyle/avatar_default.jpg':
                try:
                    os.remove(os.path.join(upload_folder, os.path.basename(old_avatarpath)))
                    if old_thumbnailpath:  # Check if old_thumbnailpath was defined
                        os.remove(os.path.join(upload_folder, os.path.basename(old_thumbnailpath)))
                except Exception as e:
                    print(f"Error deleting old avatar: {e}")
                    flash("Error deleting old avatar. Please try again.", 'error')

            current_user.avatarpath = 'library/images/avatars_users/' + uuid_filename
        else:
            if not current_user.avatarpath:
                current_user.avatarpath = 'newstyle/avatar_default.jpg'

        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Error updating profile: {e}")
            flash('Failed to update profile. Please try again.', 'error')

        return redirect(url_for('main.settings_profile_edit'))

    print("Form validation failed" if request.method == 'POST' else "Settings profile Form rendering")

    for field, errors in form.errors.items():
        for error in errors:
            print(f"Error in field '{getattr(form, field).label.text}': {error}")
            flash(f"Error in field '{getattr(form, field).label.text}': {error}", 'error')

    return render_template('settings/settings_profile_edit.html', form=form, avatarpath=current_user.avatarpath)

@bp.route('/settings_profile_view', methods=['GET'])
@login_required
def settings_profile_view():
    print("Route: Settings profile view")
    # Calculate remaining invites
    unused_invites = InviteToken.query.filter_by(
        creator_user_id=current_user.user_id, 
        used=False
    ).count()
    remaining_invites = max(0, current_user.invite_quota - unused_invites)
    
    return render_template('settings/settings_profile_view.html', 
                         remaining_invites=remaining_invites,
                         total_invites=current_user.invite_quota)

@bp.route('/settings_password', methods=['GET', 'POST'])
@login_required
def account_pw():
    form = UserPasswordForm()
    user = User.query.get(current_user.id)

    if form.validate_on_submit():
        try:
            user.set_password(form.password.data)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            print('Password changed successfully for user ID:', current_user.id)
            return redirect(url_for('main.account_pw'))
        except Exception as e:
            db.session.rollback()
            print('An error occurred while changing the password:', str(e))
            flash('An error occurred. Please try again.', 'error')

    return render_template('settings/settings_password.html', title='Change Password', form=form, user=user)

@bp.route('/settings_panel', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_panel():
    print("Route: /settings_panel")
    form = UserPreferencesForm()
    
    if request.method == 'POST' and form.validate_on_submit():
        # Ensure preferences exist
        if not current_user.preferences:
            current_user.preferences = UserPreference(user_id=current_user.id)
        
        current_user.preferences.items_per_page = form.items_per_page.data or current_user.preferences.items_per_page
        current_user.preferences.default_sort = form.default_sort.data or current_user.preferences.default_sort
        current_user.preferences.default_sort_order = form.default_sort_order.data or current_user.preferences.default_sort_order
        current_user.preferences.theme = form.theme.data if form.theme.data != 'default' else None
        db.session.add(current_user.preferences)
        db.session.commit()
        flash('Your settings have been updated.', 'success')
        return redirect(url_for('main.discover'))
    elif request.method == 'GET':
        # Ensure preferences exist
        if not current_user.preferences:
            current_user.preferences = UserPreference(user_id=current_user.id)
            db.session.add(current_user.preferences)
            db.session.commit()
        
        form.items_per_page.data = current_user.preferences.items_per_page
        form.default_sort.data = current_user.preferences.default_sort
        form.default_sort_order.data = current_user.preferences.default_sort_order
        form.theme.data = current_user.preferences.theme or 'default'

    return render_template('settings/settings_panel.html', form=form)

@bp.route('/api/genres')
@login_required
def get_genres():
    genres = Genre.query.all()
    genres_list = [{'id': genre.id, 'name': genre.name} for genre in genres]
    return jsonify(genres_list)

@bp.route('/api/themes')
@login_required
def get_themes():
    themes = Theme.query.all()
    themes_list = [{'id': theme.id, 'name': theme.name} for theme in themes]
    return jsonify(themes_list)

@bp.route('/api/game_modes')
@login_required
def get_game_modes():
    game_modes = GameMode.query.all()
    game_modes_list = [{'id': game_mode.id, 'name': game_mode.name} for game_mode in game_modes]
    return jsonify(game_modes_list)

@bp.route('/api/player_perspectives')
@login_required
def get_player_perspectives():
    perspectives = PlayerPerspective.query.all()
    perspectives_list = [{'id': perspective.id, 'name': perspective.name} for perspective in perspectives]
    return jsonify(perspectives_list)



@bp.route('/browse_games')
@login_required
def browse_games():
    print(f"Route: /browse_games - {current_user.name}")
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Filters
    library_uuid = request.args.get('library_uuid')
    category = request.args.get('category')
    genre = request.args.get('genre')
    rating = request.args.get('rating', type=int)
    game_mode = request.args.get('game_mode')
    player_perspective = request.args.get('player_perspective')
    theme = request.args.get('theme')
    sort_by = request.args.get('sort_by', 'name')  # Adding sort_by parameter
    sort_order = request.args.get('sort_order', 'asc')  # Adding sort_order parameter

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
        # print(f'player_perspective query: {player_perspective}')
        query = query.filter(Game.player_perspectives.any(PlayerPerspective.name == player_perspective))
    if theme:
        query = query.filter(Game.themes.any(Theme.name == theme))

    # Apply sorting logic
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


@bp.route('/api/search')
@login_required
def search():
    query = request.args.get('query', '')
    results = []
    if query:
        games = Game.query.filter(Game.name.ilike(f'%{query}%')).all()
        results = [{'id': game.id, 'uuid': game.uuid, 'name': game.name} for game in games]

        # print(f'Search results for "{query}": {results}')
    return jsonify(results)


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

@bp.route('/favoritesz')
@login_required
def favoritesz():
    page = request.args.get('page', 1, type=int)
    per_page = current_user.preferences.items_per_page if current_user.preferences else 20
    
    # Create a proper query for pagination
    favorites_query = Game.query.join(user_favorites).filter(
        user_favorites.c.user_id == current_user.id
    )
    pagination = favorites_query.paginate(page=page, per_page=per_page, error_out=False)
    games = pagination.items
    
    # Process game data for display
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
            'genres': genres
        })
    
    return render_template('games/favorites.html', 
                         games=game_data,
                         pagination=pagination)


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
            # print("Session updated with game paths.")
            
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


def handle_auto_scan(auto_form):
    print("handle_auto_scan: function running.")
    if auto_form.validate_on_submit():
        library_uuid = auto_form.library_uuid.data
        remove_missing = auto_form.remove_missing.data
        
        running_job = ScanJob.query.filter_by(status='Running').first()
        if running_job:
            flash('A scan is already in progress. Please wait until the current scan completes.', 'error')
            session['active_tab'] = 'auto'
            return redirect(url_for('main.scan_management', library_uuid=library_uuid, active_tab='auto'))

    
        library = Library.query.filter_by(uuid=library_uuid).first()
        if not library:
            flash('Selected library does not exist. Please select a valid library.', 'error')
            return redirect(url_for('main.scan_management', active_tab='auto'))

        
        folder_path = auto_form.folder_path.data
        
        scan_mode = auto_form.scan_mode.data

        
        print(f"Auto-scan form submitted. Library: {library.name}, Folder: {folder_path}, Scan mode: {scan_mode}")
        # Prepend the base path
        base_dir = current_app.config.get('BASE_FOLDER_WINDOWS') if os.name == 'nt' else current_app.config.get('BASE_FOLDER_POSIX')
        full_path = os.path.join(base_dir, folder_path)
        if not os.path.exists(full_path) or not os.access(full_path, os.R_OK):
            flash(f"Cannot access folder: {full_path}. Please check the path and permissions.", 'error')
            print(f"Cannot access folder: {full_path}. Please check the path and permissions.", 'error')
            session['active_tab'] = 'auto'
            return redirect(url_for('library.library'))

        @copy_current_request_context
        def start_scan():
            scan_and_add_games(full_path, scan_mode, library_uuid, remove_missing)

        thread = Thread(target=start_scan)
        thread.start()
        
        flash(f"Auto-scan started for folder: {full_path} and library name: {library.name}", 'info')
        session['active_tab'] = 'auto'
    else:
        flash(f"Auto-scan form validation failed: {auto_form.errors}")
        print(f"Auto-scan form validation failed: {auto_form.errors}")
    return redirect(url_for('main.scan_management', library_uuid=library_uuid, active_tab='auto'))



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



def handle_manual_scan(manual_form):
    settings = GlobalSettings.query.first()
    session['active_tab'] = 'manual'
    if manual_form.validate_on_submit():
        # check job status
        running_job = ScanJob.query.filter_by(status='Running').first()
        if running_job:
            flash('A scan is already in progress. Please wait until the current scan completes.', 'error')
            session['active_tab'] = 'manual'
            return redirect(url_for('main.scan_management', active_tab='manual'))
        
        folder_path = manual_form.folder_path.data
        scan_mode = manual_form.scan_mode.data
        library_uuid = manual_form.library_uuid.data
        
        if not library_uuid:
            flash('Please select a library.', 'error')
            return redirect(url_for('main.scan_management', active_tab='manual'))
        
        # Store library_uuid in session for use in identify page
        session['selected_library_uuid'] = library_uuid
        print(f"Manual scan: Selected library UUID: {library_uuid}")

        base_dir = current_app.config.get('BASE_FOLDER_WINDOWS') if os.name == 'nt' else current_app.config.get('BASE_FOLDER_POSIX')
        full_path = os.path.join(base_dir, folder_path)
        print(f"Manual scan form submitted. Full path: {full_path}, Library UUID: {library_uuid}")

        if os.path.exists(full_path) and os.access(full_path, os.R_OK):
            print("Folder exists and can be accessed.")
            insensitive_patterns, sensitive_patterns = load_release_group_patterns()
            if scan_mode == 'folders':
                games_with_paths = get_game_names_from_folder(full_path, insensitive_patterns, sensitive_patterns)
            else:  # files mode
                # Load allowed file types from database
                allowed_file_types = AllowedFileType.query.all()
                supported_extensions = [file_type.value for file_type in allowed_file_types]
                if not supported_extensions:
                    flash("No allowed file types defined in the database.", "error")
                    return redirect(url_for('main.scan_management', active_tab='manual'))
                
                games_with_paths = get_game_names_from_files(full_path, supported_extensions, insensitive_patterns, sensitive_patterns)
            session['game_paths'] = {game['name']: game['full_path'] for game in games_with_paths}
            print(f"Found {len(session['game_paths'])} games in the folder.")
            flash('Manual scan processed for folder: ' + full_path, 'info')
            
        else:
            flash("Folder does not exist or cannot be accessed.", "error")
    else:
        flash('Manual scan form validation failed.', 'error')
        
    print("Game paths: ", session.get('game_paths', {}))
    return redirect(url_for('main.scan_management', library_uuid=library_uuid, active_tab='manual'))





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
    form = AddGameForm(obj=game)  # Pre-populate form
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
            # Inform user that igdb_id already in use
            flash(f'The IGDB ID {form.igdb_id.data} is already used by another game.', 'error')
            return render_template('admin/admin_game_identify.html', form=form, library_name=library_name, game_uuid=game_uuid, action="edit")
        
        # Check if IGDB ID has changed
        igdb_id_changed = game.igdb_id != form.igdb_id.data
        
        # Update game attributes
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

@bp.route('/get_platform_by_library/<library_uuid>')
@login_required
@admin_required
def get_platform_by_library(library_uuid):
    library = Library.query.filter_by(uuid=library_uuid).first()
    if library:
        platform_name = library.platform.name
        platform_id = PLATFORM_IDS.get(library.platform.value.upper(), None)
        return jsonify({'platform_name': platform_name, 'platform_id': platform_id})
    return jsonify({'error': 'Library not found'}), 404


@bp.route('/edit_game_images/<game_uuid>', methods=['GET'])
@login_required
@admin_required
def edit_game_images(game_uuid):
    if is_scan_job_running():
        # Inform the user that editing images might not be possible at the moment
        flash('Image editing might be restricted while a scan job is running. Please try again later.', 'warning')

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
        img = PILImage.open(file)  # Re-open the image for processing
    except (IOError, SyntaxError):
        return jsonify({'error': 'Invalid image data'}), 400

    file.seek(0)  # Seek to the beginning of the file after verifying
    max_width, max_height = 1200, 1600
    if image_type == 'cover':
        # Resize the image if it exceeds the maximum dimensions
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




@bp.route('/api/reorder_libraries', methods=['POST'])
@login_required
@admin_required
def reorder_libraries():
    try:
        new_order = request.json.get('order', [])
        for index, library_uuid in enumerate(new_order):
            library = Library.query.get(library_uuid)
            if library:
                library.display_order = index
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


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

def get_game_name_by_uuid(uuid):
    print(f"Searching for game UUID: {uuid}")
    game = Game.query.filter_by(uuid=uuid).first()
    if game:
        print(f"Game with name {game.name} and UUID {game.uuid} found")
        return game.name
    else:
        print("Game not found")
        return None

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


@bp.context_processor
def inject_current_theme():
    if current_user.is_authenticated and current_user.preferences:
        current_theme = current_user.preferences.theme or 'default'
    else:
        current_theme = 'default'
    return dict(current_theme=current_theme)


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

def delete_associations_for_game(game_to_delete):
    associations = [game_to_delete.genres, game_to_delete.platforms, game_to_delete.game_modes,
                    game_to_delete.themes, game_to_delete.player_perspectives, game_to_delete.multiplayer_modes]
    
    for association in associations:
        association.clear()




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




@bp.route('/download_game/<game_uuid>', methods=['GET'])
@login_required
def download_game(game_uuid):
    print(f"Downloading game with UUID: {game_uuid}")
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    print(f"Game found: {game}")

    # Check for any existing download request for the same game by the current user, regardless of status
    existing_request = DownloadRequest.query.filter_by(user_id=current_user.id, file_location=game.full_disk_path).first()
    
    if existing_request:
        flash("You already have a download request for this game in your basket. Please check your downloads page.", "info")
        return redirect(url_for('main.downloads'))
    
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
    return redirect(url_for('main.downloads'))

@bp.route('/download_other/<file_type>/<game_uuid>/<file_id>', methods=['GET'])
@login_required
def download_other(file_type, game_uuid, file_id):
    """Handle downloads for update and extra files"""
    
    # Validate file_type
    if file_type not in ['update', 'extra']:
        flash("Invalid file type", "error")
        return redirect(url_for('main.game_details', game_uuid=game_uuid))

    FileModel = GameUpdate if file_type == 'update' else GameExtra
    # Fetch the file record
    file_record = FileModel.query.filter_by(id=file_id, game_uuid=game_uuid).first()
    
    if not file_record:
        flash(f"{file_type.capitalize()} file not found", "error")
        return redirect(url_for('main.game_details', game_uuid=game_uuid))

    # Check if the file or folder exists
    if not os.path.exists(file_record.file_path):
        flash("File not found on disk", "error")
        return redirect(url_for('main.game_details', game_uuid=game_uuid))

    # Check for an existing download request
    existing_request = DownloadRequest.query.filter_by(
        user_id=current_user.id,
        file_location=file_record.file_path
    ).first()
    if existing_request:
        flash("You already have a download request for this file", "info")
        return redirect(url_for('main.downloads'))
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
        return redirect(url_for('main.game_details', game_uuid=game_uuid))

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
    return redirect(url_for('main.downloads'))


@bp.route('/download_file/<file_location>/<file_size>/<game_uuid>/<file_name>', methods=['GET'])
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
            return redirect(url_for('main.game_details', game_uuid=game_uuid))
    elif file_location == "extras":
        # Query the extra record directly
        extra = GameExtra.query.filter_by(game_uuid=game_uuid, file_path=file_name).first()
        if extra:
            file_location = extra.file_path
        else:
            print(f"Extra file not found for game {game_uuid}")
            flash("Extra file not found", "error")
            return redirect(url_for('main.game_details', game_uuid=game_uuid))
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
        return redirect(url_for('main.downloads'))

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
    return redirect(url_for('main.downloads'))

@bp.route('/discover')
@login_required
def discover():
    page_loc = get_loc("discover")
    
    def fetch_game_details(games_query, limit=8):
        # Handle both query objects and lists
        if hasattr(games_query, 'limit'):
            games = games_query.limit(limit).all()
        else:
            games = games_query[:limit] if limit else games_query

        game_details = []
        for game in games:
            # If game is a tuple (from group by query), get the Game object
            if isinstance(game, tuple):
                game = game[0]
                
            cover_image = Image.query.filter_by(game_uuid=game.uuid, image_type='cover').first()
            cover_url = cover_image.url if cover_image else url_for('static', filename='newstyle/default_cover.jpg')
            game_details.append({
                'id': game.id,
                'uuid': game.uuid,
                'name': game.name,
                'cover_url': cover_url,
                'summary': game.summary,
                'url': game.url,
                'size': format_size(game.size),
                'genres': [genre.name for genre in game.genres],
                'first_release_date': game.first_release_date.strftime('%Y-%m-%d') if game.first_release_date else 'Not available',
                # Optionally include library information here
            })
        return game_details

    # Fetch libraries directly from the Library model
    libraries_query = Library.query.all()
    libraries = []
    for lib in libraries_query:
        libraries.append({
            'uuid': lib.uuid,
            'name': lib.name,
            'image_url': lib.image_url if lib.image_url else url_for('static', filename='newstyle/default_library.jpg'),
            # Include the platform if needed
            'platform': lib.platform.name,
        })

    # Use the helper function to fetch games for each category
    latest_games = fetch_game_details(Game.query.order_by(Game.date_created.desc()))
    most_downloaded_games = fetch_game_details(Game.query.order_by(Game.times_downloaded.desc()))
    highest_rated_games = fetch_game_details(Game.query.filter(Game.rating != None).order_by(Game.rating.desc()))
    last_updated_games = fetch_game_details(Game.query.filter(Game.last_updated != None).order_by(Game.last_updated.desc()))
    
    # Get most favorited games using a subquery to count favorites
    most_favorited = db.session.query(
        Game,
        func.count(user_favorites.c.user_id).label('favorite_count')
    ).join(user_favorites).group_by(Game).order_by(
        func.count(user_favorites.c.user_id).desc()
    )
    
    # Extract just the Game objects from the query results
    most_favorited_games_list = [game[0] for game in most_favorited]
    most_favorited_games = fetch_game_details(most_favorited_games_list)

    return render_template('games/discover.html',
                           most_favorited_games=most_favorited_games,
                           latest_games=latest_games,
                           most_downloaded_games=most_downloaded_games,
                           highest_rated_games=highest_rated_games,
                           libraries=libraries, loc=page_loc, last_updated_games=last_updated_games)



@bp.route('/download_zip/<download_id>')
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

@bp.route('/check_download_status/<download_id>')
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


@bp.route('/admin/manage-downloads', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_downloads():
    print("Route: /admin/manage-downloads")
    form = ClearDownloadRequestsForm()
    if form.validate_on_submit():
        print("Deleting all download requests")
        try:
            DownloadRequest.query.filter(DownloadRequest.status == 'processing').delete()
            
            db.session.commit()
            flash('All processing downloads have been cleared.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {e}', 'danger')
        return redirect(url_for('main.manage_downloads'))

    download_requests = DownloadRequest.query.all()
    return render_template('admin/admin_manage_downloads.html', form=form, download_requests=download_requests)

@bp.route('/delete_download_request/<int:request_id>', methods=['POST'])
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


@bp.route('/delete_download/<int:download_id>', methods=['POST'])
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
            return redirect(url_for('main.downloads'))
        else:
            flash('Only the download request was deleted, the original game file was not removed.', 'info')
    else:
        flash('No file found to delete, only the download request was removed.', 'info')

    db.session.delete(download_request)
    db.session.commit()

    return redirect(url_for('main.downloads'))

@bp.route('/api/get_libraries')
def get_libraries():
    # Direct query to the Library model
    libraries_query = Library.query.all()
    libraries = [
        {
            'uuid': lib.uuid,
            'name': lib.name,
            'image_url': lib.image_url if lib.image_url else url_for('static', filename='newstyle/default_library.jpg')
        } for lib in libraries_query
    ]

    # Logging the count of libraries returned
    print(f"Returning {len(libraries)} libraries.")
    return jsonify(libraries)
    
@bp.route('/api/game_screenshots/<game_uuid>')
@login_required
def game_screenshots(game_uuid):
    screenshots = Image.query.filter_by(game_uuid=game_uuid, image_type='screenshot').all()
    screenshot_urls = [url_for('static', filename=f'library/images/{screenshot.url}') for screenshot in screenshots]
    return jsonify(screenshot_urls)


@bp.route('/api/get_company_role', methods=['GET'])
@login_required
def get_company_role():
    game_igdb_id = request.args.get('game_igdb_id')
    company_id = request.args.get('company_id')
    
    # Validate input
    if not game_igdb_id or not company_id or not game_igdb_id.isdigit() or not company_id.isdigit():
        print("Invalid input: Both game_igdb_id and company_id must be provided and numeric.")
        return jsonify({'error': 'Invalid input. Both game_igdb_id and company_id must be provided and numeric.'}), 400


    try:
        print(f"Requested company role for Game IGDB ID: {game_igdb_id} and Company ID: {company_id}")
        
        response_json = make_igdb_api_request(
            "https://api.igdb.com/v4/involved_companies",
            f"""fields company.name, developer, publisher, game;
                where game={game_igdb_id} & id=({company_id});"""
        )
        
        if not response_json or 'error' in response_json:
            print(f"No data found or error in response: {response_json}")
            return jsonify({'error': 'No data found or error in response.'}), 404

        for company_data in response_json:
            company_info = company_data.get('company')
            if isinstance(company_info, dict):  # Ensure company_info is a dictionary
                company_name = company_info.get('name', 'Unknown Company')
            else:
                print(f"Unexpected data structure for company info: {company_info}")
                continue  # Skip this iteration

            role = 'Not Found'
            if company_data.get('developer', False):
                role = 'Developer'
            elif company_data.get('publisher', False):
                role = 'Publisher'

            print(f"Company {company_name} role: {role} (igdb_id={game_igdb_id}, company_id={company_id})")
            return jsonify({
                'game_igdb_id': game_igdb_id,
                'company_id': company_id,
                'company_name': company_name,
                'role': role
            }), 200

            
        
        return jsonify({'error': 'Company with given ID not found in the specified game.'}), 404

    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({'error': 'An error occurred processing your request.'}), 500



@bp.route('/api/get_cover_thumbnail', methods=['GET'])
@login_required
def get_cover_thumbnail():
    igdb_id = request.args.get('igdb_id', default=None, type=str)
    if igdb_id is None or not igdb_id.isdigit():
        return jsonify({'error': 'Invalid input. The ID must be numeric.'}), 400
    cover_url = get_cover_thumbnail_url(int(igdb_id))
    if cover_url:
        return jsonify({'cover_url': cover_url}), 200
    else:
        return jsonify({'error': 'Cover URL could not be retrieved.'}), 404


@bp.route('/api/search_igdb_by_id')
@login_required
def search_igdb_by_id():
    igdb_id = request.args.get('igdb_id')
    if not igdb_id:
        return jsonify({"error": "IGDB ID is required"}), 400

    endpoint_url = "https://api.igdb.com/v4/games"
    query_params = f"""
        fields name, summary, cover.url, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name, 
               screenshots.url, videos.video_id, first_release_date, aggregated_rating, involved_companies, player_perspectives.name,
               aggregated_rating_count, rating, rating_count, status, category, total_rating,
               total_rating_count;
        where id = {igdb_id};
    """

    response = make_igdb_api_request(endpoint_url, query_params)
    if "error" in response:
        return jsonify({"error": response["error"]}), 500

    if response:
        game_data = response[0] if response else {}
        return jsonify(game_data)
    else:
        return jsonify({"error": "Game not found"}), 404


@bp.route('/api/search_igdb_by_name')
@login_required
def search_igdb_by_name():
    game_name = request.args.get('name')
    platform_id = request.args.get('platform_id')

    if game_name:
        # Start with basic search and expand the query conditionally
        query = f"""
            fields id, name, cover.url, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name,
                   screenshots.url, videos.video_id, first_release_date, aggregated_rating, involved_companies, player_perspectives.name,
                   aggregated_rating_count, rating, rating_count, slug, status, category, total_rating, 
                   total_rating_count;
            search "{game_name}";"""

        # Check if a platform_id was provided and is valid
        if platform_id and platform_id.isdigit():
            # Append the platform filter to the existing search query
            query += f" where platforms = ({platform_id});"
        else:
            query += ";"

        query += " limit 10;"  # Set a limit to the number of results

        results = make_igdb_api_request('https://api.igdb.com/v4/games', query)

        if 'error' not in results:
            return jsonify({'results': results})
        else:
            return jsonify({'error': results['error']})
    return jsonify({'error': 'No game name provided'})




@bp.route('/check_scan_status', methods=['GET'])
@login_required
@admin_required
def check_scan_status():
    active_job = ScanJob.query.filter_by(status='Running').first()
    
    is_active = active_job is not None
    return jsonify({"is_active": is_active})






def get_loc(page):
    
    with open(f'modules/static/localization/en/{page}.json', 'r', encoding='utf8') as f:
            loc_data = json.load(f)    
    return loc_data
    
@bp.add_app_template_global  
def verify_file(full_path):
    if os.path.exists(full_path) or os.access(full_path, os.R_OK):
        # print(f"File Exists: {full_path}.")
        return True
    else:
        # print(f"Cannot find theme specific file: {full_path}. Using default theme file.", 'warning')
        return False