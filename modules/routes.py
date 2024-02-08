# modules/routes.py
import shutil
import traceback
from threading import Thread
import ast, uuid, json, random, requests, html, os, re
from config import Config
from flask import Flask, render_template, flash, redirect, url_for, request, Blueprint, jsonify, session, abort, current_app, send_from_directory
from flask import copy_current_request_context
from flask_login import current_user, login_user, logout_user, login_required
from flask_wtf import FlaskForm
from flask_mail import Message as MailMessage
from wtforms import StringField, PasswordField, SubmitField, FieldList, BooleanField
from wtforms.validators import DataRequired, Email, Length
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy import func, Integer, Text
from werkzeug.urls import url_parse
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from modules import db, mail
from modules.forms import UserPasswordForm, UserDetailForm, EditProfileForm, NewsletterForm, WhitelistForm, EditUserForm, UserManagementForm, ScanFolderForm, IGDBApiForm, ClearDownloadRequestsForm, CsrfProtectForm, AddGameForm
from modules.models import User, Whitelist, ReleaseGroup, Game, Image, DownloadRequest, category_mapping, status_mapping, player_perspective_mapping, Platform, Genre, Publisher, Developer, Theme, GameMode, MultiplayerMode

from functools import wraps
from uuid import uuid4
from datetime import datetime, timedelta
from PIL import Image as PILImage
from PIL import ImageOps
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from authlib.jose import jwt
from authlib.jose.errors import DecodeError
import logging
from logging.handlers import RotatingFileHandler
import os


bp = Blueprint('main', __name__)
log_filename = "sharewarez.log"
s = URLSafeTimedSerializer('YMecr3tK?IzzsSa@e!Zithpze') 



# Initialization flag
has_initialized_whitelist = False
has_upgraded_admin = False

has_initialized_setup = False

# Define a simple form for CSRF protection
class CsrfForm(FlaskForm):
    pass 


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
        print('Default email already exists in the Whitelist.')
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f'An error occurred while adding the default email to the Whitelist: {e}')

    # Upgrade first user to admin
    try:
        user = User.query.get(1)
        if user and user.role != 'admin':
            user.role = 'admin'
            db.session.commit()
            print(f"User '{user.name}' (ID: 1) has been upgraded to admin.")
        elif not user:
            print("No user with ID 1 found in the database.")
        else:
            print("User with ID 1 already has admin role.")
    except IntegrityError:
        db.session.rollback()
        print('An error occurred while trying to upgrade the user to admin.')
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f'An error occurred while upgrading the user to admin: {e}')


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
def index():
    return redirect(url_for('main.login'))


@bp.route('/favicon.ico')
def favicon():
    favidir = "images"
    full_dir = os.path.join(current_app.static_folder, favidir)
    print(full_dir)
    return send_from_directory(full_dir, 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.restricted'))

    print("Route: /login")

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(name=username).first()

        if user and not user.is_email_verified:
            flash('Your account is not activated, check your email.', 'warning')
            return redirect(url_for('main.login'))

        # Check if the user's account is disabled
        if user and not user.state:
            flash('Your account has been banned.', 'error')
            print(f"Error: Attempted login to disabled account - User: {username}")
            return redirect(url_for('main.login'))

        return _authenticate_and_redirect(username, password)

    return render_template('login/login.html', title='Log In')



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
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            if user.token_creation_time and (datetime.utcnow() - user.token_creation_time).total_seconds() < RATE_LIMIT_SECONDS:
                flash('Please wait a bit before requesting another password reset.')
                return redirect(url_for('main.login'))
            password_reset_token = str(uuid.uuid4())
            user.password_reset_token = password_reset_token
            user.token_creation_time = datetime.utcnow()
            db.session.commit()
            send_password_reset_email(user.email, password_reset_token)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('main.login'))

    return render_template('login/reset_password_request.html')


@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    user = User.query.filter_by(password_reset_token=token).first()
    if not user or user.token_creation_time + timedelta(minutes=15) < datetime.utcnow():
        flash('The password reset link is invalid or has expired.')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        new_password = request.form['password']
        confirm_password = request.form['confirm_password']
        if new_password != confirm_password:
            flash('Passwords do not match.')
            return render_template('reset_password.html', token=token)
        user.set_password(new_password)
        user.password_reset_token = None
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('main.login'))

    return render_template('login/reset_password.html', token=token)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("You must be an admin to access this page.", "danger")
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/api/current_user_role', methods=['GET'])
@login_required
def get_current_user_role():
    print("Route: /api/current_user_role")
    return jsonify({'role': current_user.role}), 200


@bp.route('/api/check_username', methods=['POST'])
@login_required
def check_username():
    print("Route: /api/check_username")
    data = request.get_json()  # Get the JSON data from the request
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
    print("Route: /delete_avatar")
    print("avatar_path:", avatar_path)

    # Get the full path of the avatar image
    full_avatar_path = os.path.join(current_app.static_folder, avatar_path)
    print("full_avatar_path:", full_avatar_path)

    # Check if the file exists
    if os.path.exists(full_avatar_path):
        # Delete the file
        os.remove(full_avatar_path)
        flash(f'Avatar image {full_avatar_path} deleted successfully!')
    else:
        flash(f'Avatar image {full_avatar_path} not found.')

    return redirect(url_for('main.bot_generator'))


@bp.route('/help')
def privacy():
    print("Route: /help")
    return render_template('site/help.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    print("Route: /register")

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            email_address = form.email.data
            print(f"Debug: Extracted email - {email_address}")
            
            # Check if the email is already used by another user
            existing_user_email = User.query.filter_by(email=email_address).first()
            if existing_user_email:
                print(f"Debug: Email already in use - {email_address}")
                flash('This email is already in use. Please use a different email or log in.')
                return redirect(url_for('main.register'))
            
            # Check if the entire email address is in the whitelist
            whitelist = Whitelist.query.filter_by(email=email_address).first()
            if not whitelist:
                print(f"Debug: No matching whitelist entry found for - {email_address}")
                flash('Your email is not whitelisted.')
                return redirect(url_for('main.register'))

            print(f"Debug: Whitelist entry found - {whitelist.email}")

            existing_user = User.query.filter_by(name=form.username.data).first()
            if existing_user is not None:
                print(f"Debug: User already exists - {form.username.data}")
                flash('User already exists. Please Log in.')
                return redirect(url_for('main.register'))

            # Generate UUID and check for uniqueness
            user_uuid = str(uuid4())
            existing_uuid = User.query.filter_by(user_id=user_uuid).first()
            if existing_uuid is not None:
                print("Debug: UUID collision detected.")
                flash('An error occurred while registering. Please try again.')
                return redirect(url_for('main.register'))

            # Create a new User object with role set to a default value (e.g., 'user')
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
            # Send verification email
            token = user.email_verification_token
            confirm_url = url_for('main.confirm_email', token=token, _external=True)
            html = render_template('login/registration_activate.html', confirm_url=confirm_url)
            subject = "Please confirm your email"
            send_email(user.email, subject, html)

            flash('A confirmation email has been sent via email.', 'success')
            return redirect(url_for('main.index'))
        except IntegrityError as e:
            db.session.rollback()
            print(f"IntegrityError occurred: {e}")
            flash('An error occurred while registering. Please try again.')

    return render_template('login/registration.html', title='Register', form=form)


@bp.route('/restricted')
@login_required
def restricted():
    print("Route: /restricted")
    return render_template('site/restricted_area.html', title='Restricted Area')


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))



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
    print("Request method:", request.method)  # Debug line
    user = User.query.get(current_user.id)

    if form.validate_on_submit():
        try:
            print("Form data:", form.data)  # Debug line
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

@bp.route('/admin/base')
@login_required
def admin_main():
    print("ADMIN MAIN: Request method:", request.method)
    return render_template('admin/base.html')


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


@bp.route('/get_user/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def get_user(user_id):
    print(f"Accessing get_user route with user_id: {user_id}")
    user = User.query.get(user_id)
    if user:
        user_data = {
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'state': user.state,
            
            
            # Add other fields as needed
        }
        return jsonify(user_data)
    else:
        print(f"User not found with id: {user_id}")
        return jsonify({'error': 'User not found'}), 404


@bp.route('/admin/usrmgr', methods=['GET', 'POST'])
@login_required
@admin_required
def usermanager():
    form = UserManagementForm()
    users_query = User.query.order_by(User.name).all()
    form.user_id.choices = [(user.id, user.name) for user in users_query]

    if form.validate_on_submit():
        user_id = form.user_id.data
        action = "Delete" if form.delete.data else "Update"

        print(f"Attempting to {action} user with ID: {user_id}")

        user = User.query.get(user_id)
        if not user:
            print(f"User not found with ID: {user_id}")
            flash(f'User not found with ID: {user_id}', 'danger')
            return redirect(url_for('main.usermanager'))

        if form.submit.data:
            # Update user logic
            try:
                # Update fields
                user.name = form.name.data or user.name
                user.email = form.email.data or user.email
                user.role = form.role.data or user.role
                user.state = form.state.data if form.state.data is not None else user.state
                

                db.session.commit()
                print(f"User updated: {user}")
                flash('User updated successfully!', 'success')

                # Set the form's user_id field to the just edited user
                form.user_id.data = user_id
            except Exception as e:
                db.session.rollback()
                print(f"Database error on update: {e}")
                flash('Database error. Update failed.', 'danger')

        elif form.delete.data:
            # Delete user logic
            user = User.query.get(form.user_id.data)
            if not user:
                print(f"User not found with ID: {form.user_id.data}")
                flash('User not found.', 'danger')
                return redirect(url_for('main.usermanager'))

            try:
                # Delete associated message threads
                Message.query.filter_by(owner=user.id).delete()

                # Delete associated favorites
                Favorite.query.filter_by(user_id=user.id).delete()

                # Delete associated highscores
                Highscore.query.filter_by(user_id=user.user_id).delete()

                # Finally, delete the user
                db.session.delete(user)
                db.session.commit()
                print(f"User deleted: {user}")
                flash('User deleted successfully!', 'success')
            except SQLAlchemyError as e:
                db.session.rollback()
                error_msg = f"Database error on delete: {e}"
                print(error_msg)
                flash(error_msg, 'danger')


    else:
        form.user_id.data = 3

    return render_template('admin/usrmgr.html', form=form, users=users_query)


def _authenticate_and_redirect(username, password):
    user = User.query.filter(func.lower(User.name) == func.lower(username)).first()
    if user is None or not user.check_password(password):
        flash('Invalid username or password')
        return redirect(url_for('main.login'))

    user.lastlogin = datetime.utcnow()
    db.session.commit()
    login_user(user, remember=True)
    next_page = request.args.get('next')
    if not next_page or url_parse(next_page).netloc != '':
        next_page = url_for('main.restricted')
    return redirect(next_page)

def square_image(image, size):
    # Resize the image to the desired size while maintaining aspect ratio
    image.thumbnail((size, size))

    # If the image is not square, pad it with black bars
    if image.size[0] != size or image.size[1] != size:
        new_image = PILImage.new('RGB', (size, size), color='black')
        offset = ((size - image.size[0]) // 2, (size - image.size[1]) // 2)
        new_image.paste(image, offset)
        image = new_image

    return image



def send_email(to, subject, template):
    msg = MailMessage(
        subject,
        sender='halliday@pleasewaitloading.com',
        recipients=[to],
        html=template
    )
    mail.send(msg)

def send_password_reset_email(user_email, token):
    reset_url = url_for('main.reset_password', token=token, _external=True)
    msg = MailMessage(
        'Password Reset Request',
        sender='halliday@sharewarez.pleasewaitloading.com',  # Replace with your actual sender email
        recipients=[user_email],
        body=f'Please click on the link to reset your password: {reset_url}'
    )
    mail.send(msg)

# Define the RegistrationForm class
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    submit = SubmitField('Register')

########################################################################################
########################################################################################
########################################################################################
########################################################################################
########################################################################################
######################            basic site above                  ####################
########################################################################################
########################################################################################
########################################################################################
########################################################################################
########################################################################################


@bp.route('/admin/beta', methods=['GET'])
def beta():
    return render_template('admin/beta.html') 


    
    
@bp.route('/api_debug', methods=['GET', 'POST'])
def api_debug():
    form = IGDBApiForm()
    api_response = None  # Initialize variable to store API response

    if form.validate_on_submit():
        selected_endpoint = form.endpoint.data
        query_params = form.query.data
        print(f"Selected endpoint: {selected_endpoint} with query params: {query_params}")
        api_response = make_igdb_api_request(selected_endpoint, query_params)
        
    return render_template('games/scan_apidebug.html', form=form, api_response=api_response)


@bp.route('/check_igdb_id')
def check_igdb_id():
    igdb_id = request.args.get('igdb_id', type=int)
    if igdb_id is None:
        return jsonify({'message': 'Invalid request', 'available': False}), 400

    game_exists = check_existing_game_by_igdb_id(igdb_id) is not None
    return jsonify({'available': not game_exists})


@bp.route('/check_path_availability', methods=['GET'])
def check_path_availability():
    full_disk_path = request.args.get('full_disk_path', '')
    is_available = os.path.exists(full_disk_path)
    return jsonify({'available': is_available})

@bp.route('/scan_folder', methods=['GET', 'POST'])
def scan_folder():
    form = ScanFolderForm()
    # Initialize game_names_with_ids with a default value
    game_names_with_ids = None
    
    if form.validate_on_submit():
        if form.cancel.data:
            return redirect(url_for('main.scan_folder'))
        
        folder_path = form.folder_path.data
        print(f"Scanning folder: {folder_path}")

        if os.path.exists(folder_path) and os.access(folder_path, os.R_OK):
            print("Folder exists and is accessible.")

            # Assuming load_release_group_patterns and clean_game_name are defined elsewhere
            insensitive_patterns, sensitive_patterns = load_release_group_patterns()
            
            # Now get_game_names_from_folder returns a list of dicts with names and full paths
            games_with_paths = get_game_names_from_folder(folder_path, insensitive_patterns, sensitive_patterns)
            
            # Update the session with this new structure
            session['game_paths'] = {game['name']: game['full_path'] for game in games_with_paths}
            print("Session updated with game paths.")
            
            # Define game_names_with_ids here after ensuring folder is accessible and games are found
            game_names_with_ids = [{'name': game['name'], 'id': i} for i, game in enumerate(games_with_paths)]
        else:
            flash("Folder does not exist or cannot be accessed.", "error")
            print("Folder does not exist or cannot be accessed.")
            # It's already initialized to None at the top, so it's safe even if this branch is hit

    print("Game names with IDs:", game_names_with_ids)
    return render_template('games/scan_folder.html', form=form, game_names_with_ids=game_names_with_ids)



@bp.route('/add_game/<game_name>')
def add_game(game_name):
    print(f"Adding game: {game_name}")

    # Retrieve the full disk path from the session
    full_disk_path = session.get('game_paths', {}).get(game_name)
    
    if not full_disk_path:
        flash("Could not find the game's disk path.", "error")
        return redirect(url_for('main.scan_folder'))
    
    # Attempt to add the game with the provided name and disk path
    game = retrieve_and_save_game(game_name, full_disk_path)
    if game:
        # If the game is successfully added, remove its path from the session
        if game_name in session.get('game_paths', {}):
            del session['game_paths'][game_name]
            
            # If there are no more games left in the session, clear the entire 'game_paths' entry
            if not session['game_paths']:
                del session['game_paths']
        
        flash("Game added successfully.", "success")
        return render_template('games/scan_add_game.html', game=game)
    else:
        flash("Game not found or API error occurred.", "error")
        return redirect(url_for('main.scan_folder'))
    
    
@bp.route('/add_game_manual', methods=['GET', 'POST'])
def add_game_manual():
    form = AddGameForm()
    if form.validate_on_submit():
        if check_existing_game_by_igdb_id(form.igdb_id.data):
            flash('A game with this IGDB ID already exists.', 'error')
            return render_template('games/manual_game_add.html', form=form)
        
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
            video_urls={"videos": [form.video_urls.data]} if form.video_urls.data else {}
        )
        new_game.genres = form.genres.data
        new_game.game_modes = form.game_modes.data
        new_game.themes = form.themes.data
        new_game.platforms = form.platforms.data
        new_game.player_perspectives = form.player_perspectives.data
        if form.developer.data:
            new_game.developer = form.developer.data[0]
        if form.publisher.data:
            new_game.publisher = form.publisher.data[0]
        db.session.add(new_game)
        db.session.commit()
        flash('Game added successfully.', 'success')
        return redirect(url_for('.browse_games'))

    return render_template('games/manual_game_add.html', form=form)

@bp.route('/browse_games')
def browse_games():
    games = Game.query.all()  # Retrieve all games from the database
    game_data = []

    for game in games:
        # For each game, find the cover image
        cover_image = Image.query.filter_by(game_uuid=game.uuid, image_type='cover').first()
        cover_url = cover_image.url if cover_image else None  # Use cover image URL if available

        game_data.append({
            'id': game.id,
            'uuid': game.uuid,
            'name': game.name,
            'cover_url': cover_url,
            'summary': game.summary,
            'url': game.url
        })

    csrf_form = CsrfForm()

    return render_template('games/library_browser.html', games=game_data, form=csrf_form)    

@bp.route('/game_details/<string:game_uuid>')
def game_details(game_uuid):
    print(f"Fetching game details for UUID: {game_uuid}")
    
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
            "multiplayer_modes": [mode.name for mode in game.multiplayer_modes]
        }
        return render_template('games/games_details.html', game=game_data)
    else:
        return jsonify({"error": "Game not found"}), 404


@bp.route('/delete_game/<string:game_uuid>', methods=['POST'])
def delete_game(game_uuid):
    try:
        valid_uuid = uuid.UUID(game_uuid, version=4)
    except ValueError:
        print(f"Invalid UUID format: {game_uuid}")
        abort(404)

    game_uuid_str = str(valid_uuid)

    try:
        game_to_delete = Game.query.filter_by(uuid=game_uuid_str).first_or_404()
        images_to_delete = Image.query.filter_by(game_uuid=game_uuid_str).all()

        for image in images_to_delete:
            
            relative_image_path = image.url.replace('/static/images/', '').strip("/")
            image_file_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], relative_image_path)
            image_file_path = os.path.normpath(image_file_path)

            #print(f"Attempting to delete image file: {image_file_path}")

            if os.path.exists(image_file_path):
                os.remove(image_file_path)
                print(f"Deleted image file: {image_file_path}")
            else:
                print(f"Image file not found: {image_file_path}")

            db.session.delete(image)

        db.session.delete(game_to_delete)
        db.session.commit()
        flash('Game and its images have been deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        print(f'Error deleting game with UUID {game_uuid_str}: {e}')
        flash(f'Error deleting game: {e}', 'error')
    
    return redirect(url_for('main.browse_games'))

@bp.route('/download_game/<game_uuid>', methods=['GET'])
@login_required
def download_game(game_uuid):
    print(f"Downloading game with UUID: {game_uuid}")
    game = Game.query.filter_by(uuid=game_uuid).first_or_404()
    print(f"Game found: {game}")
    # Check if there's already an active download request for this user
    print(f"Checking if there's already an active download request for user {current_user.id}: {DownloadRequest.query.filter_by(user_id=current_user.id, status='processing').first()}")
    active_request = DownloadRequest.query.filter_by(user_id=current_user.id, status='processing').first()
    if active_request:
        flash(f"You already have an active download request for {active_request.game.name}. Please wait until it's completed.")
        return redirect(url_for('main.browse_games'))

    # Create a new download request with status 'processing'
    print(f"Creating a new download request for user {current_user.id}: {DownloadRequest.query.filter_by(user_id=current_user.id, status='processing').first()}")
    new_request = DownloadRequest(user_id=current_user.id, game_uuid=game.uuid, status='processing') 
    db.session.add(new_request)
    db.session.commit()

    # Copy the current request context to use the correct app instance
    @copy_current_request_context
    def thread_function():
        print(f"Thread function started for download request {new_request.id}")
        zip_game(new_request.id, current_app._get_current_object())

    thread = Thread(target=thread_function)
    thread.start()
    
    flash("Your download request is being processed. You will be notified when the download is ready.")
    return redirect(url_for('main.browse_games'))


@bp.route('/download_zip/<download_id>')
@login_required
def download_zip(download_id):
    print(f"Downloading zip with ID: {download_id}")
    download_request = DownloadRequest.query.filter_by(id=download_id, user_id=current_user.id).first_or_404()
    
    if download_request.status != 'available':
        flash("The requested download is not ready yet.")
        return redirect(url_for('main.browse_games'))

    relative_path = download_request.zip_file_path
    absolute_path = os.path.join(current_app.static_folder, relative_path)
    
    if not os.path.exists(absolute_path):
        flash("Error: File does not exist.")
        return redirect(url_for('main.browse_games'))

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
        return redirect(url_for('main.browse_games'))


@bp.route('/check_download_status/<game_uuid>')
@login_required
def check_download_status(game_uuid):
    print(f"Requested check for game_uuid: {game_uuid}")
    
    print(f"Current user ID: {current_user.id}, Game UUID: {game_uuid}")
    
    # Attempt to fetch all download requests for debug purposes
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
        # Delete all DownloadRequest records
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


@bp.route('/downloads')
@login_required
def downloads():
    user_id = current_user.id
    download_requests = DownloadRequest.query.filter_by(user_id=user_id).all()
    form = CsrfProtectForm()
    return render_template('games/downloads_manager.html', download_requests=download_requests, form=form)


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


@bp.route('/search_igdb_by_id')
def search_igdb_by_id():
    igdb_id = request.args.get('igdb_id')
    if not igdb_id:
        return jsonify({"error": "IGDB ID is required"}), 400

    endpoint_url = "https://api.igdb.com/v4/games"
    query_params = f"""
        fields name, summary, cover.url, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name, 
               screenshots.url, videos.video_id, first_release_date, aggregated_rating,
               aggregated_rating_count, rating, rating_count, slug, status, category, total_rating,
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
def search_igdb_by_name():
    game_name = request.args.get('name')
    if game_name:
        query = f"""
            fields id, name, cover.url, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name,
                   screenshots.url, videos.video_id, first_release_date, aggregated_rating, 
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



##########################################################################################
##########################################################################################
##########################################################################################

def get_game_by_uuid(game_uuid):
    print(f"Searching for game UUID: {game_uuid}")

    game = Game.query.filter_by(uuid=game_uuid).first()
    if game:
        print(f"Game ID {game.id} with name {game.name} and UUID {game.uuid} relating to IGDB ID {game.igdb_id} found")

        images = game.images.all()
        # for img in images:
            # print(f"Image ID: {img.id}, Type: {img.image_type}, URL: {img.url}")
        
        return game
    else:
        print("Game not found")
        return None

def escape_special_characters(pattern):
    return re.escape(pattern)

def load_release_group_patterns():
    try:
        insensitive_patterns = ["-" + rg.rlsgroup for rg in ReleaseGroup.query.filter(ReleaseGroup.rlsgroup != None).all()]
        
        sensitive_patterns = []
        for rg in ReleaseGroup.query.filter(ReleaseGroup.rlsgroupcs != None).all():
            pattern = rg.rlsgroupcs
            if pattern.lower() == 'yes':
                pattern = "-" + pattern  # Add '-' prefix for case-sensitive patterns
                sensitive_patterns.append((pattern, True))  # True indicates case sensitivity
            elif pattern.lower() == 'no':
                sensitive_patterns.append((pattern, False))  # False indicates case insensitivity
        
        print("Loaded release groups:", ", ".join(insensitive_patterns + [p[0] for p in sensitive_patterns]))

        return insensitive_patterns, sensitive_patterns
    except SQLAlchemyError as e:
        print(f"An error occurred while fetching release group patterns: {e}")
        return [], []





def get_access_token(client_id, client_secret):
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, params=params)
    if response.status_code == 200:
        return response.json()['access_token']
        print("Access token obtained successfully")
    else:
        print("Failed to obtain access token")
        return None



def clean_game_name(filename, insensitive_patterns, sensitive_patterns):
    # print(f"Original filename: {filename}")
    original_filename = filename

    for pattern in insensitive_patterns:
        escaped_pattern = escape_special_characters(pattern)
        filename = re.sub(escaped_pattern, '', filename, flags=re.IGNORECASE)
        # print(f"After removing insensitive pattern '{pattern}': {filename}")

    for pattern, is_case_sensitive in sensitive_patterns:
        escaped_pattern = escape_special_characters(pattern)
        if is_case_sensitive:
            filename = re.sub(escaped_pattern, '', filename)
            # print(f"After removing case-sensitive pattern '{pattern}': {filename}")
        else:
            filename = re.sub(escaped_pattern, '', filename, flags=re.IGNORECASE)
            # print(f"After removing case-insensitive pattern '{pattern}': {filename}")

    filename = re.sub(r'[_\.]', ' ', filename)
    cleaned_name = ' '.join(filename.split()).title()

    # print(f"Original filename: '{original_filename}' cleaned to: '{cleaned_name}'")
    
    return cleaned_name

def get_game_names_from_folder(folder_path, insensitive_patterns, sensitive_patterns):
    print(f"Processing folder: {folder_path}")
    if not os.path.exists(folder_path) or not os.access(folder_path, os.R_OK):
        print(f"Error: The folder '{folder_path}' does not exist or is not readable.")
        flash(f"Error: The folder '{folder_path}' does not exist or is not readable.")
        return []

    folder_contents = os.listdir(folder_path)
    print("Folder contents before filtering:", folder_contents)

    game_names_with_paths = []
    for item in folder_contents:
        full_path = os.path.join(folder_path, item)
        if os.path.isdir(full_path):
            game_name = clean_game_name(item, insensitive_patterns, sensitive_patterns)
            game_names_with_paths.append({'name': game_name, 'full_path': full_path})

    print("Extracted game names with paths:", game_names_with_paths)
    return game_names_with_paths


def create_game_instance(game_data, full_disk_path):
            
    category_id = game_data.get('category')
    category_enum = category_mapping.get(category_id, None)
    status_id = game_data.get('status')
    status_enum = status_mapping.get(status_id, None)
    player_perspective_id = game_data.get('player_perspective')
    player_perspective_enum = player_perspective_mapping.get(player_perspective_id, None)
    
    new_game = Game(
        igdb_id=game_data['id'],
        name=game_data['name'],
        summary=game_data.get('summary'),
        storyline=game_data.get('storyline'),
        url=game_data.get('url'),
        first_release_date=datetime.utcfromtimestamp(game_data.get('first_release_date', 0)) if game_data.get('first_release_date') else None,
        aggregated_rating=game_data.get('aggregated_rating'),
        aggregated_rating_count=game_data.get('aggregated_rating_count'),
        rating=game_data.get('rating'),
        rating_count=game_data.get('rating_count'),
        slug=game_data.get('slug'),
        status=status_enum,
        category=category_enum,
        total_rating=game_data.get('total_rating'),
        total_rating_count=game_data.get('total_rating_count'),
        video_urls={"videos": game_data.get('videos', [])},
        full_disk_path=full_disk_path
    )
    
    db.session.add(new_game)
    db.session.flush()
    print(f"Game {new_game.name} instance created with UUID: {new_game.uuid}.")
    return new_game


def process_and_save_image(game_uuid, image_data, image_type='cover'):
    url = None
    save_path = None
    print(f"Processing and saving {image_type} image for game {game_uuid} with UUID {image_data}.")
    if image_type == 'cover':
        print(f"Processing cover image for game {game_uuid}.")
        cover_query = f'fields url; where id={image_data};'
        cover_response = make_igdb_api_request('https://api.igdb.com/v4/covers', cover_query)
        print(f'Cover response: {cover_response}')
        if cover_response and 'error' not in cover_response:
            url = cover_response[0].get('url')
            if not url:
                print(f"Cover URL not found for ID {image_data}.")
                return
        else:
            print(f"Failed to retrieve URL for cover ID {image_data}.")
            return

        # Download cover image
        file_name = secure_filename(f"{game_uuid}_cover_{image_data}.jpg")  # Adjust extension if needed
        save_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], file_name)
        download_image(url, save_path)
        # print(f"Cover image saved to {save_path} for game {game_uuid} with UUID {image_data}.")

    elif image_type == 'screenshot':
        screenshot_query = f'fields url; where id={image_data};'
        response = make_igdb_api_request('https://api.igdb.com/v4/screenshots', screenshot_query)
        # print(f'Screenshot response: {response}')
        if response and 'error' not in response:
            url = response[0].get('url')
            if not url:
                print(f"Screenshot URL not found for ID {image_data}.")
                return
            file_name = secure_filename(f"{game_uuid}_{image_data}.jpg")  # Adjust extension if needed
            save_path = os.path.join(current_app.config['IMAGE_SAVE_PATH'], file_name)
            download_image(url, save_path)
            # print(f"Screenshot image saved to {save_path} for game {game_uuid} with UUID {image_data}.")

    # Create and add the image record to the database
    image = Image(
        game_uuid=game_uuid,
        image_type=image_type,
        url=file_name,  # Store only the filename in the database
    )
    #print(f"Image record created for game {game_uuid} with UUID {image_data} and URL {url}.")
    db.session.add(image)
    
def retrieve_and_save_game(game_name, full_disk_path):

    print(f"Fetching game data for {game_name} with full disk path {full_disk_path}.")
    response_json = make_igdb_api_request(current_app.config['IGDB_API_ENDPOINT'],
        f"""fields id, name, cover, summary, url, release_dates.date, platforms.name, genres.name, themes.name, game_modes.name,
                   screenshots, videos.video_id, first_release_date, aggregated_rating, involved_companies,
                   aggregated_rating_count, rating, rating_count, slug, status, category, total_rating, 
                   total_rating_count;
            search "{game_name}"; limit 1;
        """)

    if 'error' not in response_json and response_json:

        igdb_id = response_json[0].get('id')


        existing_game = check_existing_game_by_igdb_id(igdb_id)
        if existing_game:
            print(f"Game with IGDB ID {igdb_id} already exists in the database.")
            flash(f"Game '{game_name}' already exists in the database.")
            return existing_game
        else:

            new_game = create_game_instance(response_json[0], full_disk_path)
            if 'genres' in response_json[0]:
                for genre_data in response_json[0]['genres']:
                    genre_name = genre_data['name']
                    genre = Genre.query.filter_by(name=genre_name).first()
                    if not genre:
                        genre = Genre(name=genre_name)
                        db.session.add(genre)
                    new_game.genres.append(genre)

            if 'involved_companies' in response_json[0]:
                involved_company_ids = response_json[0]['involved_companies']
                if involved_company_ids:
                    print(f"Enumerating companies for game {game_name}.")
                    enumerate_companies(new_game, new_game.igdb_id, involved_company_ids)
                else:
                    print("No involved companies found for this game.")

            if 'themes' in response_json[0]:
                for theme_data in response_json[0]['themes']:
                    theme_name = theme_data['name']
                    
                    theme = Theme.query.filter_by(name=theme_name).first()
                    if not theme:
                        
                        theme = Theme(name=theme_name)
                        db.session.add(theme)
                    
                    new_game.themes.append(theme)

            if 'game_modes' in response_json[0]:
                for game_mode_data in response_json[0]['game_modes']:
                    game_mode_name = game_mode_data['name']
                    
                    game_mode = GameMode.query.filter_by(name=game_mode_name).first()
                    if not game_mode:
                        
                        game_mode = GameMode(name=game_mode_name)
                        db.session.add(game_mode)
                        db.session.flush()

                    new_game.game_modes.append(game_mode)
                    print(f"Game mode {game_mode_name} added to game {new_game.name}.")


            if 'platforms' in response_json[0]:
                for platform_data in response_json[0]['platforms']:
                    platform_name = platform_data['name']
                    platform = Platform.query.filter_by(name=platform_name).first()
                    if not platform:
                        platform = Platform(name=platform_name)
                        db.session.add(platform)
                    new_game.platforms.append(platform)
                    print(f"Platform {platform_name} added to game {new_game.name} with UUID {new_game.uuid}.")

            if 'cover' in response_json[0]:
                print(f"Cover debug: {response_json[0]['cover']}")
                process_and_save_image(new_game.uuid, response_json[0]['cover'], 'cover')
            
            for screenshot_id in response_json[0].get('screenshots', []):
                process_and_save_image(new_game.uuid, screenshot_id, 'screenshot')
            
            try:
                db.session.commit()
                print(f"Game and its images saved successfully with UUID: {new_game.uuid}.")
                flash("Game and its images saved successfully.")
            except IntegrityError as e:
                db.session.rollback()
                print(f"Failed to save game due to a database error: {e}")
                flash("Failed to save game due to a duplicate entry.")
            return new_game
    else:
        print(f"Failed to retrieve game data from IGDB API: {response_json}")
        error_message = "No game data found for the given name or failed to retrieve data from IGDB API."
        print(error_message)
        flash(error_message)
        return None

def enumerate_companies(game_instance, igdb_game_id, involved_company_ids):
    print(f"Enumerating companies for game with IGDB ID {igdb_game_id}.")
    company_ids_str = ','.join(map(str, involved_company_ids))

    print(f"Company IDs: {company_ids_str}")
    response_json = make_igdb_api_request(
        "https://api.igdb.com/v4/involved_companies",
        f"""fields company.name, developer, publisher, game;
            where game={igdb_game_id} & id=({company_ids_str});"""
    )
    print(f"Companies Response JSON: {response_json}")
    
    for company in response_json:
        company_name = company['company']['name']
        is_developer = company.get('developer', False)
        is_publisher = company.get('publisher', False)

        if is_developer:
            print(f"Company {company_name} is a developer.")
            developer = Developer.query.filter_by(name=company_name).first()
            if not developer:
                developer = Developer(name=company_name)
                db.session.add(developer)
            
            game_instance.developer = developer
        
        if is_publisher:
            
            publisher = Publisher.query.filter_by(name=company_name).first()
            if not publisher:
                publisher = Publisher(name=company_name)
                db.session.add(publisher)
            game_instance.publisher = publisher

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Failed to enumerate companies due to a database error: {e}")


def make_igdb_api_request(endpoint_url, query_params):
    client_id = current_app.config['IGDB_CLIENT_ID']
    client_secret = current_app.config['IGDB_CLIENT_SECRET']
    access_token = get_access_token(client_id, client_secret) 

    if not access_token:
        return {"error": "Failed to retrieve access token"}

    headers = {
        'Client-ID': client_id,
        'Authorization': f"Bearer {access_token}"
    }

    try:
        print(f"Making API request to {endpoint_url} with query params: {query_params}")
        response = requests.post(endpoint_url, headers=headers, data=query_params)
        response.raise_for_status()
        data = response.json()
        print(f"API request successful: {json.dumps(data, indent=4)}")
        return response.json()

    except requests.RequestException as e:
        return {"error": f"API Request failed: {e}"}

    except ValueError:
        return {"error": "Invalid JSON in response"}

    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

def download_image(url, save_path):
    if not url.startswith(('http://', 'https://')):
        url = 'https:' + url

    
    url = url.replace('/t_thumb/', '/t_original/')

    print(f"Downloading image from {url}.")
    response = requests.get(url)
    if response.status_code == 200:
        # print(f"Image downloaded successfully to {save_path}.")
        with open(save_path, 'wb') as f:
            f.write(response.content)
    else:
        print(f"Failed to download the image. Status Code: {response.status_code}")

def zip_game(download_request_id, app):
    with app.app_context():
        download_request = DownloadRequest.query.get(download_request_id)
        game = download_request.game
        print(f"Zipping game: {game.name}")
        if not game:
            print(f"No game found for DownloadRequest ID: {download_request_id}")
            return
        
        zip_save_path = app.config['ZIP_SAVE_PATH']
        output_zip_base = os.path.join(zip_save_path, game.uuid)
        source_folder = game.full_disk_path
        
        if not os.path.exists(source_folder):
            print(f"Source folder does not exist: {source_folder}")
            return
        
        try:
            print(f"Zipping game folder: {source_folder} to {output_zip_base}.")
            output_zip = shutil.make_archive(output_zip_base, 'zip', source_folder)
            print(f"Archive created at {output_zip}")
                        
            download_request.status = 'available'
            download_request.zip_file_path = output_zip
            download_request.completion_time = datetime.utcnow()
            print(f"Download request updated: {download_request}")
            db.session.commit()
        except Exception as e:
            error_message = str(e)
            print(f"An error occurred while zipping: {error_message}")

            download_request.status = 'failed'
            download_request.zip_file_path = error_message
            db.session.commit()
            print(f"Failed to zip game for DownloadRequest ID: {download_request_id}, Error: {error_message}")
   
        
def check_existing_game_by_igdb_id(igdb_id):
    return Game.query.filter_by(igdb_id=igdb_id).first()
