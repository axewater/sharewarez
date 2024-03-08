# modules/routes.py
import ast, uuid, json, random, requests, html, os, re, shutil, traceback, time, schedule, os, platform, tempfile
from threading import Thread
from config import Config
from flask import Flask, render_template, flash, redirect, url_for, request, Blueprint, jsonify, session, abort, current_app, send_from_directory
from flask import copy_current_request_context
from flask_login import current_user, login_user, logout_user, login_required
from flask_wtf import FlaskForm
from flask_mail import Message as MailMessage
from wtforms.validators import DataRequired, Email, Length
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy import func, Integer, Text, case
from werkzeug.urls import url_parse
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from modules import db, mail
from functools import wraps
from uuid import uuid4
from datetime import datetime, timedelta
from PIL import Image as PILImage
from PIL import ImageOps
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from authlib.jose import jwt
from authlib.jose.errors import DecodeError

from modules.forms import (
    UserPasswordForm, UserDetailForm, EditProfileForm, NewsletterForm, WhitelistForm, EditUserForm, 
    UserManagementForm, ScanFolderForm, IGDBApiForm, ClearDownloadRequestsForm, CsrfProtectForm, 
    AddGameForm, LoginForm, ResetPasswordRequestForm, AutoScanForm, UpdateUnmatchedFolderForm, 
    ReleaseGroupForm, RegistrationForm, CsrfForm
)
from modules.models import (
    User, User, Whitelist, ReleaseGroup, Game, Image, DownloadRequest, ScanJob, UnmatchedFolder, Publisher, Developer, 
    Platform, Genre, Theme, GameMode, MultiplayerMode, PlayerPerspective
)
from modules.utilities import (
    admin_required, _authenticate_and_redirect, square_image, refresh_images_in_background, send_email, send_password_reset_email,
    get_game_by_uuid, escape_special_characters, enumerate_companies, make_igdb_api_request, load_release_group_patterns, check_existing_game_by_igdb_id,
    log_unmatched_folder, get_game_names_from_folder, clean_game_name, get_cover_thumbnail_url, scan_and_add_games, get_game_names_from_folder,
    zip_game, retrieve_and_save_game, format_size, delete_game_images, get_folder_size_in_mb
)


bp = Blueprint('main', __name__)
s = URLSafeTimedSerializer('YMecr3tK?IzzsSa@e!Zithpze') 
has_initialized_whitelist = False
has_upgraded_admin = False
has_initialized_setup = False

@bp.before_app_request
def initial_setup():
    global has_initialized_setup
    if has_initialized_setup:
        return
    has_initialized_setup = True

    # Initialize whitelist
    try:
        if not Whitelist.query.first():
            default_email = Config.INITIAL_WHITELIST
            default_whitelist = Whitelist(email=default_email)
            db.session.add(default_whitelist)
            db.session.commit()
            print("Default email added to Whitelist.")
    except IntegrityError:
        db.session.rollback()
        print('Default email already exists in Whitelist.')
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f'error adding default email to Whitelist: {e}')

    # Upgrade first user to admin
    try:
        user = User.query.get(1)
        if user and user.role != 'admin':
            user.role = 'admin'
            user.is_email_verified = True
            db.session.commit()
            print(f"User '{user.name}' (ID: 1) upgraded to admin.")
        elif not user:
            print("No user with ID 1 found in the database.")
        else:
            print("User with ID 1 already has admin role.")
    except IntegrityError:
        db.session.rollback()
        print('error while trying to upgrade user to admin.')
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f'error upgrading user to admin: {e}')






@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('site.restricted'))

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

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            email_address = form.email.data.lower()
            existing_user_email = User.query.filter(func.lower(User.email) == email_address).first()
            if existing_user_email:
                print(f"Debug: Email already in use - {email_address}")
                flash('This email is already in use. Please use a different email or log in.')
                return redirect(url_for('main.register'))
            whitelist = Whitelist.query.filter(func.lower(Whitelist.email) == email_address).first()
            if not whitelist:
                flash('Your email is not whitelisted.')
                return redirect(url_for('main.register'))


            existing_user = User.query.filter_by(name=form.username.data).first()
            if existing_user is not None:
                print(f"Debug: User already exists - {form.username.data}")
                flash('User already exists. Please Log in.')
                return redirect(url_for('main.register'))

            user_uuid = str(uuid4())
            existing_uuid = User.query.filter_by(user_id=user_uuid).first()
            if existing_uuid is not None:
                print("Debug: UUID collision detected.")
                flash('An error occurred while registering. Please try again.')
                return redirect(url_for('main.register'))

            user = User(
                user_id=user_uuid,
                name=form.username.data,
                email=form.email.data,
                role='user',
                is_email_verified=False,
                email_verification_token=s.dumps(form.email.data, salt='email-confirm'),
                token_creation_time=datetime.utcnow(),
                created=datetime.utcnow()
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            # verification email
            token = user.email_verification_token
            confirm_url = url_for('main.confirm_email', token=token, _external=True)
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
    form = ResetPasswordRequestForm()
    
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        if user:
            if user.token_creation_time and (datetime.utcnow() - user.token_creation_time).total_seconds() < 120:
                flash('Please wait a bit before requesting another password reset.')
                return redirect(url_for('main.login'))
            password_reset_token = str(uuid.uuid4())
            user.password_reset_token = password_reset_token
            user.token_creation_time = datetime.utcnow()
            db.session.commit()
            send_password_reset_email(user.email, password_reset_token)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('main.login'))

    return render_template('login/reset_password_request.html', form=form)

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

################### API ROUTES ###################################################################################
################### API ROUTES ###################################################################################
################### API ROUTES ###################################################################################


@bp.route('/api/current_user_role', methods=['GET'])
@login_required
def get_current_user_role():
    print(f"Route: /api/current_user_role - {current_user.role}")
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


@bp.route('/delete_avatar/<path:avatar_path>', methods=['POST'])
@login_required
def delete_avatar(avatar_path):
    
    full_avatar_path = os.path.join(current_app.static_folder, avatar_path)
    print(f"Route: /delete_avatar {full_avatar_path}")

    if os.path.exists(full_avatar_path):
        os.remove(full_avatar_path)
        flash(f'Avatar image {full_avatar_path} deleted successfully!')
        print(f"Avatar image {full_avatar_path} deleted successfully!")
    else:
        flash(f'Avatar image {full_avatar_path} not found.')

    return redirect(url_for('main.bot_generator'))



#################################### SETTINGS ROUTES ############################################
#################################### SETTINGS ROUTES ############################################
#################################### SETTINGS ROUTES ############################################



@bp.route('/settings_account', methods=['GET', 'POST'])
@login_required
def account():
    print("Route: /settings_account")

    user = User.query.filter_by(id=current_user.id).first()
    form = UserDetailForm(about=str(user.about))
    

    if form.validate_on_submit():
      
        try:
            db.session.commit()
            

            flash('Account details updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Error updating account details: {e}")
            flash('Failed to update account details. Please try again.', 'error')

        return redirect(url_for('main.account'))

    return render_template('settings/settings_account.html', title='Account', form=form, user=user)

@bp.route('/settings_profile_edit', methods=['GET', 'POST'])
@login_required
def settings_profile_edit():
    print("Route: Settings profile edit")
    form = EditProfileForm()

    if form.validate_on_submit():
        file = form.avatar.data
        if file:
            old_avatarpath = current_user.avatarpath
            old_thumbnailpath = os.path.splitext(old_avatarpath)[0] + '_thumbnail' + os.path.splitext(old_avatarpath)[1]
            filename = secure_filename(file.filename)
            uuid_filename = str(uuid4()) + '.' + filename.rsplit('.', 1)[1].lower()
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], uuid_filename)
            file.save(image_path)

            # Create square avatar
            img = PILImage.open(image_path)
            img = square_image(img, 500)
            img.save(image_path)

            # Create square thumbnail
            img = PILImage.open(image_path)
            img = square_image(img, 50)
            thumbnail_path = os.path.splitext(image_path)[0] + '_thumbnail' + os.path.splitext(image_path)[1]
            img.save(thumbnail_path)

            if old_avatarpath != 'avatars_users/default.jpg':
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER_USER'], os.path.basename(old_avatarpath)))
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER_USER'], os.path.basename(old_thumbnailpath)))
                except Exception as e:
                    print(f"Error deleting old avatar: {e}")
                    flash("Error deleting old avatar. Please try again.", 'error')

            current_user.avatarpath = 'avatars_users/' + uuid_filename
        else:
            if not current_user.avatarpath:
                current_user.avatarpath = 'avatars_users/default.jpg'

        

        try:
            db.session.commit()
            print("Form validated and submitted successfully")
            print(f"Avatar Path: {current_user.avatarpath}")
        

            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Error updating profile: {e}")
            flash('Failed to update profile. Please try again.', 'error')

        return redirect(url_for('main.settings_profile_edit'))
       

    print("Form validation failed" if request.method == 'POST' else "Settings profile Form rendering")
    print(f"Avatar Path: {current_user.avatarpath}")
    

    for field, errors in form.errors.items():
        for error in errors:
            print(f"Error in field '{getattr(form, field).label.text}': {error}")
            flash(f"Error in field '{getattr(form, field).label.text}': {error}", 'error')

    return render_template('settings/settings_profile_edit.html', form=form, avatarpath=current_user.avatarpath)

@bp.route('/settings_profile_view', methods=['GET'])
@login_required
def settings_profile_view():
    print("Route: Settings profile view")
    return render_template('settings/settings_profile_view.html')


@bp.route('/settings_password', methods=['GET', 'POST'])
@login_required
def account_pw():
    form = UserPasswordForm()
    # print("Request method:", request.method)  # Debug line
    user = User.query.get(current_user.id)

    if form.validate_on_submit():
        try:
            # print("Form data:", form.data)  # Debug line
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


######################################## ADMIN ROUTES #####################################################
######################################## ADMIN ROUTES #####################################################
######################################## ADMIN ROUTES #####################################################



@bp.route('/admin/newsletter', methods=['GET', 'POST'])
@login_required
@admin_required
def newsletter():
    print("ADMIN NEWSLETTER: Request method:", request.method)
    form = NewsletterForm()
    users = User.query.all()
    if form.validate_on_submit():
        recipients = form.recipients.data.split(',')
        print(f"ADMIN NEWSLETTER: Recipient list : {recipients}")
        
        msg = MailMessage(form.subject.data, sender=current_app.config['MAIL_DEFAULT_SENDER'])
        msg.body = form.content.data
        
        msg.recipients = recipients
        try:
            print(f"ADMIN NEWSLETTER: Newsletter sent")
            mail.send(msg)
            flash('Newsletter sent successfully!', 'success')
        except Exception as e:
            flash(str(e), 'error')
        return redirect(url_for('main.newsletter'))
    return render_template('admin/newsletter.html', title='Newsletter', form=form, users=users)


@bp.route('/admin/whitelist', methods=['GET', 'POST'])
@login_required
@admin_required
def whitelist():
    form = WhitelistForm()
    if form.validate_on_submit():
        email = form.email.data
        new_whitelist = Whitelist(email=email)
        db.session.add(new_whitelist)
        try:
            db.session.commit()
            flash('The email was successfully added to the whitelist!', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('The email is already in the whitelist!', 'danger')
        return redirect(url_for('main.whitelist'))
    whitelist = Whitelist.query.all()
    return render_template('admin/whitelist.html', title='Whitelist', whitelist=whitelist, form=form)



@bp.route('/admin/usrmgr', methods=['GET', 'POST'])
@login_required
@admin_required
def usermanager():
    print("ADMIN USRMGR: username: Request method:", request.method)
    form = UserManagementForm()
    users_query = User.query.order_by(User.name).all()
    form.user_id.choices = [(user.id, user.name) for user in users_query]
    print(f"ADMIN USRMGR: User list : {users_query}")
    # Pre-populate the form when the page loads or re-populate upon validation failure
    if request.method == 'GET' or not form.validate_on_submit():
        # You could also use a default user here or based on some criteria
        default_user_id = request.args.get('user_id', 3)  # Example of getting a user_id from query parameters
        default_user = User.query.get(default_user_id)
        if default_user:
            form.user_id.data = default_user.id
            form.name.data = default_user.name
            form.email.data = default_user.email
            form.role.data = default_user.role
            form.state.data = default_user.state
            form.is_email_verified.data = default_user.is_email_verified
            form.about.data = default_user.about  # Pre-populate the 'about' field

    else:
        # This block handles the form submission for both updating and deleting users
        print(f"ADMIN USRMGR: Form data: {form.data}")
        user_id = form.user_id.data
        user = User.query.get(user_id)
        if not user:
            flash(f'User not found with ID: {user_id}', 'danger')
            return redirect(url_for('.usermanager'))  # Make sure the redirect is correct

        if form.submit.data:
            # Update user logic
            try:
                user.name = form.name.data or user.name
                user.email = form.email.data or user.email
                user.role = form.role.data or user.role
                user.state = form.state.data if form.state.data is not None else user.state
                user.is_email_verified = form.is_email_verified.data
                user.about = form.about.data
                print(f"ADMIN USRMGR: User updated: {user} about field : {user.about}")
                db.session.commit()
                flash('User updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Database error on update: {e}', 'danger')

        elif form.delete.data:
            # Delete user logic
            try:
                db.session.delete(user)
                db.session.commit()
                flash('User deleted successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Database error on delete: {e}', 'danger')

    return render_template('admin/user_manager.html', form=form, users=users_query)


@bp.route('/get_user/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def get_user(user_id):
    user = User.query.get(user_id)
    if user:
        user_data = {
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'state': user.state,
            'about': user.about,
            'is_email_verified': user.is_email_verified
        }
        return jsonify(user_data)
    else:
        print(f"User not found with id: {user_id}")
        return jsonify({'error': 'User not found'}), 404




######################            basic site above                  ####################
######################            basic site above                  ####################
######################            basic site above                  ####################


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


@bp.route('/library')
@login_required
def library():
    # Extract filters from request arguments
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    genre = request.args.get('genre')
    rating = request.args.get('rating', type=int)
    game_mode = request.args.get('game_mode')
    player_perspective = request.args.get('player_perspective')
    theme = request.args.get('theme')
    sort_by = request.args.get('sort_by', 'name')  # Default sorting by name
    sort_order = request.args.get('sort_order', 'asc')  # Default sorting order

    print(f"Filters: {genre}, {rating}, {game_mode}, {player_perspective}, {theme}")
    # Pass extracted filters to get_games
    filters = {
        'genre': genre,
        'rating': rating,
        'game_mode': game_mode,
        'player_perspective': player_perspective,
        'theme': theme
    }
    # Filter out None values
    filters = {k: v for k, v in filters.items() if v is not None}

    game_data, total, pages, current_page = get_games(page, per_page, sort_by=sort_by, sort_order=sort_order, **filters)
    # print(f'Game data: {game_data}, total: {total}, pages: {pages}, current_page: {current_page}, filters: {filters}, sort_by: {sort_by}, sort_order: {sort_order}')
    
    # You can modify this to pass additional context for rendering filters, etc.
    context = {
        'games': game_data,
        'total': total,
        'pages': pages,
        'current_page': current_page,
        # Add other necessary context variables for filters
        'form': CsrfForm()  # Assuming you're still using this for CSRF protection
    }

    return render_template('games/library_browser.html', **context)

def get_games(page=1, per_page=20, sort_by='name', sort_order='asc', **filters):
    query = Game.query.options(joinedload(Game.genres))

    # Filtering logic
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

    # Pagination logic
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    games = pagination.items

    game_data = []
    for game in games:
        cover_image = Image.query.filter_by(game_uuid=game.uuid, image_type='cover').first()
        cover_url = cover_image.url if cover_image else None
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

    return game_data, pagination.total, pagination.pages, page



@bp.route('/browse_games')
@login_required
def browse_games():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Filters
    category = request.args.get('category')
    genre = request.args.get('genre')
    rating = request.args.get('rating', type=int)
    game_mode = request.args.get('game_mode')
    player_perspective = request.args.get('player_perspective')
    theme = request.args.get('theme')
    sort_by = request.args.get('sort_by', 'name')  # Adding sort_by parameter
    sort_order = request.args.get('sort_order', 'asc')  # Adding sort_order parameter


    query = Game.query.options(joinedload(Game.genres))

    if category:
        query = query.filter(Game.category.has(Category.name == category))
    if genre:
        query = query.filter(Game.genres.any(Genre.name == genre))
    if rating is not None:
        query = query.filter(Game.rating >= rating)
    if game_mode:
        query = query.filter(Game.game_modes.any(GameMode.name == game_mode))
    if player_perspective:
        print(f'player_perspective query: {player_perspective}')
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

        
    # Pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    games = pagination.items
    

    # Get game data
    game_data = []

    for game in games:
        cover_image = Image.query.filter_by(game_uuid=game.uuid, image_type='cover').first()
        cover_url = cover_image.url if cover_image else url_for('static', filename='newstyle/default_cover.jpg')
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
    print(f'SS folder browser: Base directory: {base_dir}')
    req_path = request.args.get('path', '')

    if not req_path:
        folder_path = base_dir
    else:
        folder_path = os.path.abspath(os.path.join(base_dir, req_path))
        if not folder_path.startswith(base_dir):
            # no dir traversal
            return jsonify({'error': 'Access denied'}), 403

    if os.path.isdir(folder_path):
        contents = [{'name': item, 'isDir': True} for item in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, item))]
        return jsonify(contents)
    else:
        return jsonify({'error': 'Folder not found'}), 404




@bp.route('/api/search')
def search():
    query = request.args.get('query', '')
    results = []

    if query:
        games = Game.query.filter(Game.name.ilike(f'%{query}%')).all()
        results = [{'id': game.id, 'uuid': game.uuid, 'name': game.name} for game in games]

        # print(f'Search results for "{query}": {results}')
    return jsonify(results)


@bp.route('/downloads')
@login_required
def downloads():
    user_id = current_user.id
    print(f"Route: /downloads user_id: {user_id}")
    download_requests = DownloadRequest.query.filter_by(user_id=user_id).all()

    # Format the size for each download request before passing to the template
    for download_request in download_requests:
        download_request.formatted_size = format_size(download_request.download_size)

    form = CsrfProtectForm()
    return render_template('games/downloads_manager.html', download_requests=download_requests, form=form)




@bp.route('/scan_manual_folder', methods=['GET', 'POST'])
@login_required
@admin_required
def scan_folder():
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
            
            session['game_paths'] = {game['name']: game['full_path'] for game in games_with_paths}
            # print("Session updated with game paths.")
            
            game_names_with_ids = [{'name': game['name'], 'id': i} for i, game in enumerate(games_with_paths)]
        else:
            flash("Folder does not exist or cannot be accessed.", "error")
            print("Folder does not exist or cannot be accessed.")
            

    # print("Game names with IDs:", game_names_with_ids)
    return render_template('scan/scan_management.html', form=form, game_names_with_ids=game_names_with_ids)



@bp.route('/old_scan_auto_folder', methods=['GET', 'POST'])
@login_required
@admin_required
def scan_auto_folder():
    form = AutoScanForm()
    if form.validate_on_submit():
        folder_path = form.folder_path.data
        @copy_current_request_context
        def start_scan():
            scan_and_add_games(folder_path)

        thread = Thread(target=start_scan)
        thread.start()

        flash('Auto-scan started for folder: ' + folder_path, 'info')
        return redirect(url_for('main.scan_auto_folder'))
    
    return render_template('scan/scan_auto_folder.html', form=form)



    
@bp.route('/api_debug', methods=['GET', 'POST'])
@login_required
@admin_required
def api_debug():
    form = IGDBApiForm()
    api_response = None  # Initialize variable to store API response

    if form.validate_on_submit():
        selected_endpoint = form.endpoint.data
        query_params = form.query.data
        print(f"Selected endpoint: {selected_endpoint} with query params: {query_params}")
        api_response = make_igdb_api_request(selected_endpoint, query_params)
        
    return render_template('scan/scan_apidebug.html', form=form, api_response=api_response)




@bp.route('/add_game/<game_name>')
@login_required
@admin_required
def add_game(game_name):
    # print(f"Adding game: {game_name}")

    full_disk_path = session.get('game_paths', {}).get(game_name)
    
    if not full_disk_path:
        flash("Could not find the game's disk path.", "error")
        return redirect(url_for('main.scan_folder'))
    
    game = retrieve_and_save_game(game_name, full_disk_path)
    if game:
        if game_name in session.get('game_paths', {}):
            del session['game_paths'][game_name]
            
            if not session['game_paths']:
                del session['game_paths']
        
        flash("Game added successfully.", "success")
        print(f"Game {game_name} added successfully.")
        return render_template('scan/scan_add_game.html', game=game)
    else:
        flash("Game not found or API error occurred.", "error")
        return redirect(url_for('main.scan_folder'))


@bp.route('/add_game_manual', methods=['GET', 'POST'])
@login_required
@admin_required
def add_game_manual():
    # print(f"Received {request.method} request")
    full_disk_path = request.args.get('full_disk_path', None)
    from_unmatched = request.args.get('from_unmatched', 'false') == 'true'  # Detect origin
    game_name = os.path.basename(full_disk_path) if full_disk_path else ''

    form = AddGameForm()
    if request.method == 'GET' and full_disk_path:
        # Only pre-fill form on GET request
        form.full_disk_path.data = full_disk_path
        form.name.data = game_name
    if request.method == 'POST':
        # print("POST parameters received:", form.data)  # Log POST parameters
        if form.validate_on_submit():
            if check_existing_game_by_igdb_id(form.igdb_id.data):
                flash('A game with this IGDB ID already exists.', 'error')
                print(f"IGDB ID {form.igdb_id.data} already exists.")
                return render_template('games/manual_game_add.html', form=form)
            # print("Form data:", form.data)
            
            # Create new_game instance
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
                video_urls=form.video_urls.data 
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
                    return redirect(url_for('main.scan_management'))
                else:
                    return redirect(url_for('main.library'))
            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Error saving the game to the database: {e}")
                flash('An error occurred while adding the game. Please try again.', 'error')
        else:
            print(f"Form validation failed: {form.errors}")
    return render_template('games/manual_game_add.html', form=form, from_unmatched=from_unmatched, action="add")


@bp.route('/game_edit/<game_uuid>', methods=['GET', 'POST'])
@login_required
@admin_required
def game_edit(game_uuid):
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    form = AddGameForm(obj=game)  # Pre-populate form
    
    if form.validate_on_submit():
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
        game.category = form.category.data
        
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
        
        # Updating folder size
        print(f"Calculating folder size for {game.full_disk_path}.")
        new_folder_size_mb = get_folder_size_in_mb(game.full_disk_path)
        print(f"New folder size for {game.full_disk_path}: {format_size(new_folder_size_mb)}")
        
        # Database commit and image update trigger
        try:
            db.session.commit()
            flash('Game updated successfully.', 'success')
            flash('Triggering image update')
            

            @copy_current_request_context
            def refresh_images_in_thread():
                refresh_images_in_background(game_uuid)

            # Start the background process for refreshing images
            thread = Thread(target=refresh_images_in_thread)
            thread.start()
            print(f"Refresh images thread started for game UUID: {game_uuid}")
                    
            return redirect(url_for('main.library'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('An error occurred while updating the game. Please try again.', 'error')

    if request.method == 'POST':
        print(f"Form validation failed: {form.errors}")

    # For GET requests or if form validation fails
    return render_template('games/manual_game_add.html', form=form, game_uuid=game_uuid, action="edit")


@bp.route('/edit_game_images/<game_uuid>', methods=['GET'])
@login_required
@admin_required
def edit_game_images(game_uuid):
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    cover_image = Image.query.filter_by(game_uuid=game_uuid, image_type='cover').first()
    screenshots = Image.query.filter_by(game_uuid=game_uuid, image_type='screenshot').all()
    return render_template('games/edit_game_images.html', game=game, cover_image=cover_image, images=screenshots)


@bp.route('/upload_image/<game_uuid>', methods=['POST'])
@login_required
@admin_required
def upload_image(game_uuid):
    print(f"Uploading image for game {game_uuid}")
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    image_type = request.form.get('image_type', 'screenshot')  # Default to 'screenshot' if not provided

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

    flash('Image(s) uploaded successfully', 'success')
    return jsonify({
        'message': 'File uploaded successfully',
        'url': url_for('static', filename=f'images/{filename}'),
        'flash': 'Image uploaded successfully!',
        'image_id': new_image.id
    })

@bp.route('/delete_image', methods=['POST'])
@login_required
@admin_required
def delete_image():
    print(request.json)
    try:
        data = request.get_json()
        if not data or 'image_id' not in data:
            return jsonify({'error': 'Invalid request. Missing image_id parameter'}), 400
        
        image_id = data['image_id']
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

        return jsonify({'message': 'Image deleted successfully'})
    except Exception as e:
        # Log the error for debugging purposes
        print(f"Error deleting image: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred while deleting the image'}), 500


@bp.route('/scan_management', methods=['GET', 'POST'])
@login_required
@admin_required
def scan_management():
    auto_form = AutoScanForm()
    manual_form = ScanFolderForm()
    jobs = ScanJob.query.order_by(ScanJob.last_run.desc()).all()
    csrf_form = CsrfProtectForm()
    unmatched_folders = UnmatchedFolder.query.order_by(UnmatchedFolder.status.desc()).all()
    unmatched_form = UpdateUnmatchedFolderForm() 
    try:
        game_count = Game.query.count()  # Fetch the game count here
    except Exception as e:
        flash(f"Error fetching game count: {e}", "error")
        game_count = 0
        
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

    active_tab = session.get('active_tab', 'auto')
    print(f"Active tab: {active_tab}")
    return render_template('scan/scan_management.html', 
                           auto_form=auto_form, 
                           manual_form=manual_form, 
                           jobs=jobs, 
                           csrf_form=csrf_form, 
                           active_tab=active_tab, 
                           unmatched_folders=unmatched_folders, 
                           unmatched_form=unmatched_form,
                           game_count=game_count)

def handle_auto_scan(auto_form):
    if auto_form.validate_on_submit():
        folder_path = auto_form.folder_path.data

        # Prepend the base path
        base_dir = current_app.config.get('BASE_FOLDER_WINDOWS') if os.name == 'nt' else current_app.config.get('BASE_FOLDER_POSIX')
        full_path = os.path.join(base_dir, folder_path)

        @copy_current_request_context
        def start_scan():
            # Ensure that scan_and_add_games uses the full_path
            scan_and_add_games(full_path)

        thread = Thread(target=start_scan)
        thread.start()
        flash('Auto-scan started for folder: ' + full_path, 'info')  # Optionally show only folder_path to the user
        session['active_tab'] = 'auto'
    else:
        flash('Auto-scan form validation failed.', 'error')
    return redirect(url_for('main.scan_management'))

def handle_manual_scan(manual_form):
    if manual_form.validate_on_submit():
        folder_path = manual_form.folder_path.data
        if os.path.exists(folder_path) and os.access(folder_path, os.R_OK):
            insensitive_patterns, sensitive_patterns = load_release_group_patterns()
            games_with_paths = get_game_names_from_folder(folder_path, insensitive_patterns, sensitive_patterns)
            session['game_paths'] = {game['name']: game['full_path'] for game in games_with_paths}
            flash('Manual scan processed for folder: ' + folder_path, 'info')
            session['active_tab'] = 'manual'
        else:
            flash("Folder does not exist or cannot be accessed.", "error")
    else:
        flash('Manual scan form validation failed.', 'error')
    return redirect(url_for('main.scan_management'))

def handle_delete_unmatched(all):
    try:
        if all:
            print("Deleting all unmatched folders")
            UnmatchedFolder.query.delete()
            flash('All unmatched folders deleted successfully.', 'success')
        else:
            print("Deleting only unmatched folders")
            UnmatchedFolder.query.filter(UnmatchedFolder.status.ilike('unmatched')).delete()
            flash('Unmatched folders with status "unmatched" deleted successfully.', 'success')
        db.session.commit()
        session['active_tab'] = 'unmatched'
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting unmatched folders.', 'error')
    return redirect(url_for('main.scan_management'))
    
@bp.route('/scan_jobs_manager_old')
@login_required
@admin_required
def scan_jobs_manager_old():
    print("Route: /scan_jobs_manager")
    jobs = ScanJob.query.order_by(ScanJob.last_run.desc()).all()
    form = CsrfProtectForm()  # Instantiate the form
    return render_template('scan/scan_jobs_manager_old.html', jobs=jobs, form=form)

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
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting unmatched folders.', 'error')
        print(e)  # For debugging
    return redirect(url_for('main.scan_management'))


@bp.route('/clear_only_unmatched_folders', methods=['POST'])
@login_required
@admin_required
def clear_only_unmatched_folders():
    try:
        # Perform a case-insensitive filter and delete unmatched folders
        UnmatchedFolder.query.filter(func.lower(UnmatchedFolder.status) == 'unmatched'.lower()).delete()
        db.session.commit()
        flash('All unmatched folders with status "unmatched" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting unmatched folders.', 'error')
        print(e)  # For debugging
    return redirect(url_for('main.scan_management'))



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
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error updating folder status: {str(e)}', 'error')
    else:
        flash('Folder not found.', 'error')

    return redirect(url_for('main.scan_management'))


@bp.route('/admin/edit_filters', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_filters():
    form = ReleaseGroupForm()
    if form.validate_on_submit():
        new_group = ReleaseGroup(rlsgroup=form.rlsgroup.data, rlsgroupcs=form.rlsgroupcs.data)
        db.session.add(new_group)
        db.session.commit()
        flash('New release group filter added.')
        return redirect(url_for('main.edit_filters'))
    groups = ReleaseGroup.query.order_by(ReleaseGroup.rlsgroup.asc()).all()
    return render_template('admin/edit_filters.html', form=form, groups=groups)

@bp.route('/delete_filter/<int:id>', methods=['GET'])
@login_required
@admin_required
def delete_filter(id):
    group_to_delete = ReleaseGroup.query.get_or_404(id)
    db.session.delete(group_to_delete)
    db.session.commit()
    flash('Release group filter removed.')
    return redirect(url_for('main.edit_filters'))


@bp.route('/check_path_availability', methods=['GET'])
@login_required
def check_path_availability():
    full_disk_path = request.args.get('full_disk_path', '')
    is_available = os.path.exists(full_disk_path)
    return jsonify({'available': is_available})



@bp.route('/check_igdb_id')
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
        game_data = {
            "id": game.id,
            "uuid": game.uuid,
            "igdb_id": game.igdb_id,
            "name": game.name,
            "summary": game.summary,
            "storyline": game.storyline,
            "aggregated_rating": game.aggregated_rating,
            "aggregated_rating_count": game.aggregated_rating_count,
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
            "size": format_size(game.size)
        }
        return render_template('games/games_details.html', game=game_data, form=csrf_form)
    else:
        return jsonify({"error": "Game not found"}), 404

from flask import copy_current_request_context

from flask import jsonify  # Make sure to import jsonify

@bp.route('/refresh_game_images/<game_uuid>', methods=['POST'])
@login_required
@admin_required
def refresh_game_images(game_uuid):
    print(f"Route: /refresh_game_images - {current_user.name} - {current_user.role} method: {request.method} UUID: {game_uuid}")

    @copy_current_request_context
    def refresh_images_in_thread():
        refresh_images_in_background(game_uuid)

    thread = Thread(target=refresh_images_in_thread)
    thread.start()
    print(f"Refresh images thread started for game UUID: {game_uuid}")

    # Check if the request is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return a JSON response for AJAX requests
        return jsonify({"message": "Game images refresh process started.", "status": "info"})
    else:
        # For non-AJAX requests, perform the usual redirect
        flash("Game images refresh process started.", "info")
        return redirect(url_for('main.library'))



@bp.route('/admin/dashboard')
@login_required
@admin_required

def admin_dashboard():
    pass
    return render_template('admin/admin_dashboard.html')

    




@bp.route('/delete_game/<string:game_uuid>', methods=['POST'])
@login_required
@admin_required
def delete_game_route(game_uuid):
    print(f"Route: /delete_game - {current_user.name} - {current_user.role} method: {request.method} UUID: {game_uuid}")
    
    delete_game(game_uuid)
    return redirect(url_for('main.library'))

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
        return jsonify({'status': 'error', 'message': 'Folder path is required.'}), 400

    full_path = os.path.abspath(folder_path)

    folder_entry = UnmatchedFolder.query.filter_by(folder_path=folder_path).first()

    if not os.path.isdir(full_path):
        if folder_entry:
            db.session.delete(folder_entry)
            db.session.commit()
        return jsonify({'status': 'error', 'message': 'The specified path does not exist or is not a folder. Entry removed if it was in the database.'}), 404

    try:
        shutil.rmtree(full_path)
        if not os.path.exists(full_path):
            if folder_entry:
                db.session.delete(folder_entry)
                db.session.commit()
            return jsonify({'status': 'success', 'message': 'Folder deleted successfully. Database entry removed.'}), 200
    except PermissionError:
        return jsonify({'status': 'error', 'message': 'Failed to delete the folder due to insufficient permissions. Database entry retained.'}), 403
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error deleting folder: {e}. Database entry retained.'}), 500



@bp.route('/delete_full_game', methods=['POST'])
@login_required
@admin_required
def delete_full_game():
    print(f"Route: /delete_full_game - {current_user.name} - {current_user.role} method: {request.method}")
    data = request.get_json()
    game_uuid = data.get('game_uuid') if data else None

    if not game_uuid:
        return jsonify({'status': 'error', 'message': 'Game UUID is required.'}), 400

    game_to_delete = Game.query.filter_by(uuid=game_uuid).first()

    if not game_to_delete:
        return jsonify({'status': 'error', 'message': 'Game not found.'}), 404

    full_path = game_to_delete.full_disk_path

    if not os.path.isdir(full_path):
        return jsonify({'status': 'error', 'message': 'Game folder does not exist.'}), 404

    try:
        # Delete the game folder
        print(f"Deleting game folder: {full_path}")
        shutil.rmtree(full_path)
        if os.path.exists(full_path):
            raise Exception("Folder deletion failed")
        print(f"Game folder deleted: {full_path}")
        delete_game(game_uuid)

        return jsonify({'status': 'success', 'message': 'Game and its folder have been deleted successfully.'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error deleting game and folder: {e}'}), 500



@bp.route('/admin/delete_library')
@login_required
@admin_required
def delete_library():
    try:
        game_count = Game.query.count()
        form = CsrfForm()
    except Exception as e:
        print(f"Error fetching game count: {e}")
        flash("Failed to fetch game count.", "error")
        return redirect(url_for('main.login'))

    return render_template('admin/delete_library.html', game_count=game_count, form=form)

@bp.route('/delete_all_games', methods=['POST'])
@login_required
@admin_required
def delete_all_games():
    games_to_delete = Game.query.all()
    for game in games_to_delete:
        try:
            # Assuming delete_game is adjusted to accept a game object or UUID
            delete_game(game.uuid)  # If delete_game is adapted to work with UUIDs
        except Exception as e:
            print(f'Error deleting game with UUID {game.uuid}: {e}')
            flash(f'Error deleting game with UUID {game.uuid}: {e}', 'error')
            # Optionally, decide if you want to halt the process or continue with the next game
    
    flash('All games and their images have been deleted successfully.', 'success')
    return redirect(url_for('main.scan_management'))


@bp.route('/download_game/<game_uuid>', methods=['GET'])
@login_required
def download_game(game_uuid):
    print(f"Downloading game with UUID: {game_uuid}")
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    print(f"Game found: {game}")

    print(f"Checking if there's already an active download request for user {current_user.id}: {DownloadRequest.query.filter_by(user_id=current_user.id, status='processing').first()}")
    active_request = DownloadRequest.query.filter_by(user_id=current_user.id, status='processing').first()
    if active_request:
        flash(f"You already have an active download request for {active_request.game.name}. Please wait until it's completed.")
        return redirect(url_for('main.downloads'))


    print(f"Creating a new download request for user {current_user.id}: {DownloadRequest.query.filter_by(user_id=current_user.id, status='processing').first()}")
    new_request = DownloadRequest(
        user_id=current_user.id,
        game_uuid=game.uuid,
        status='processing',
        download_size=game.size  # Assign the game's size to the download request
    )
    db.session.add(new_request)
    db.session.commit()


    @copy_current_request_context
    def thread_function():
        print(f"Thread function started for download request {new_request.id}")
        zip_game(new_request.id, current_app._get_current_object())

    thread = Thread(target=thread_function)
    thread.start()
    
    flash("Your download request is being processed. You will be notified when the download is ready.")
    return redirect(url_for('main.downloads'))


@bp.route('/download_zip/<download_id>')
@login_required
def download_zip(download_id):
    print(f"Downloading zip with ID: {download_id}")
    download_request = DownloadRequest.query.filter_by(id=download_id, user_id=current_user.id).first_or_404()
    
    if download_request.status != 'available':
        flash("The requested download is not ready yet.")
        return redirect(url_for('main.library'))

    relative_path = download_request.zip_file_path
    absolute_path = os.path.join(current_app.static_folder, relative_path)
    
    if not os.path.exists(absolute_path):
        flash("Error: File does not exist.")
        return redirect(url_for('main.library'))

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
        return redirect(url_for('main.library'))


@bp.route('/check_download_status/<game_uuid>')
@login_required
def check_download_status(game_uuid):
    print(f"Requested check for game_uuid: {game_uuid}")
    
    print(f"Current user ID: {current_user.id}, Game UUID: {game_uuid}")
    
    all_requests_for_user = DownloadRequest.query.filter_by(user_id=current_user.id).all()
    print(f"All download requests for user: {all_requests_for_user}")
    
    download_request = DownloadRequest.query.filter_by(game_uuid=game_uuid, user_id=current_user.id).first()
    
    if download_request:
        print(f"Found download request: {download_request}")
        return jsonify({'status': download_request.status, 'downloadId': download_request.id})
    else:
        print("No matching download request found.")
    return jsonify({'status': 'error'}), 404



@bp.route('/admin/clear-downloads', methods=['GET', 'POST'])
@admin_required
def clear_downloads():
    print("Route: /admin/clear-downloads")
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
        return redirect(url_for('main.clear_downloads'))

    download_requests = DownloadRequest.query.all()
    return render_template('admin/clear_downloads.html', form=form, download_requests=download_requests)


@bp.route('/delete_download/<int:download_id>', methods=['POST'])
@login_required
def delete_download(download_id):
    download_request = DownloadRequest.query.filter_by(id=download_id, user_id=current_user.id).first_or_404()
    if download_request.zip_file_path and os.path.exists(download_request.zip_file_path):
        try:
            os.remove(download_request.zip_file_path)
            db.session.delete(download_request)
            db.session.commit()
            flash('Download deleted successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {e}', 'danger')
    else:
        db.session.delete(download_request)
        db.session.commit()
        flash('Download request deleted successfully.', 'success')

    return redirect(url_for('main.downloads'))


@bp.route('/api/game_screenshots/<game_uuid>')
@login_required
def game_screenshots(game_uuid):
    screenshots = Image.query.filter_by(game_uuid=game_uuid, image_type='screenshot').all()
    screenshot_urls = [url_for('static', filename=f'images/{screenshot.url}') for screenshot in screenshots]
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
            company_name = company_data['company']['name']
            role = 'Not Found'
            if company_data.get('developer', False):
                role = 'Developer'
            elif company_data.get('publisher', False):
                role = 'Publisher'

            print(f"Company {company_name} role: {role} (igdb_id=game_igdb_id, company_id={company_id})")
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


@bp.route('/search_igdb_by_id')
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


@bp.route('/search_igdb_by_name')
@login_required
def search_igdb_by_name():
    game_name = request.args.get('name')
    if game_name:
        query = f"""
            fields id, name, cover.url, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name,
                   screenshots.url, videos.video_id, first_release_date, aggregated_rating, involved_companies, player_perspectives.name,
                   aggregated_rating_count, rating, rating_count, slug, status, category, total_rating, 
                   total_rating_count;
            where name ~ *"{game_name}"*; limit 10;
        """
        
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

