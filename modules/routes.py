# modules/routes.py
import sys,ast, uuid, json, random, requests, html, os, re, shutil, traceback, time, schedule, os, platform, tempfile, socket
from threading import Thread
from config import Config
from flask import (
    Flask, render_template, flash, redirect, url_for, request, Blueprint, 
    jsonify, session, abort, current_app, send_from_directory, 
    copy_current_request_context, g, make_response
)
from flask_login import current_user, login_user, logout_user, login_required
from flask_wtf import FlaskForm
from flask_mail import Message as MailMessage
from wtforms.validators import DataRequired, Email, Length
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy import func, Integer, Text, case
from werkzeug.urls import url_parse
from werkzeug.utils import secure_filename
from glob import glob
from werkzeug.security import generate_password_hash, check_password_hash

from modules import db, mail, cache
from functools import wraps
from uuid import uuid4
from datetime import datetime, timedelta
from PIL import Image as PILImage
from PIL import ImageOps
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from authlib.jose import jwt

from urllib.parse import unquote

from .utilities import get_game_name_by_uuid


from modules.forms import (
    UserPasswordForm, UserDetailForm, EditProfileForm, NewsletterForm, WhitelistForm, EditUserForm, 
    UserManagementForm, ScanFolderForm, IGDBApiForm, ClearDownloadRequestsForm, CsrfProtectForm, 
    AddGameForm, LoginForm, ResetPasswordRequestForm, AutoScanForm, UpdateUnmatchedFolderForm, 
    ReleaseGroupForm, RegistrationForm, CreateUserForm, UserPreferencesForm, InviteForm, LibraryForm, CsrfForm,
    ThemeUploadForm
)
from modules.models import (
    User, User, Whitelist, ReleaseGroup, Game, Image, DownloadRequest, ScanJob, UnmatchedFolder, Publisher, Developer, 
    Genre, Theme, GameMode, PlayerPerspective, Category, UserPreference, GameURL, GlobalSettings, InviteToken, Library, LibraryPlatform
)
from modules.utilities import (
    admin_required, _authenticate_and_redirect, square_image, refresh_images_in_background, send_email, send_password_reset_email,
    get_game_by_uuid, make_igdb_api_request, load_release_group_patterns, check_existing_game_by_igdb_id,
    get_game_names_from_folder, get_cover_thumbnail_url, scan_and_add_games, get_game_names_from_files,
    zip_game, zip_folder, format_size, delete_game_images, read_first_nfo_content, get_folder_size_in_bytes, PLATFORM_IDS
)
from modules.theme_manager import ThemeManager


bp = Blueprint('main', __name__)
s = URLSafeTimedSerializer('YMecr3tK?IzzsSa@e!Zithpze') 
has_initialized_whitelist = False
has_upgraded_admin = False
has_initialized_setup = False
app_start_time = datetime.now()

app_version = '1.5.1'


@bp.before_app_request
def initial_setup():
    global has_initialized_setup
    if has_initialized_setup:
        return
    has_initialized_setup = True
    app_start_time = datetime.now()  # Record the startup time

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

@bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    settings_record = GlobalSettings.query.first()
    if settings_record:
        # Fetch existing settings
        show_logo = settings_record.settings.get('showSystemLogo', False)
        show_help_button = settings_record.settings.get('showHelpButton', False)
        enable_web_links = settings_record.settings.get('enableWebLinksOnDetailsPage', False)
        enable_server_status = settings_record.settings.get('enableServerStatusFeature', False)
        enable_newsletter = settings_record.settings.get('enableNewsletterFeature', False)
        show_version = settings_record.settings.get('showVersion', False)  # settings fix
        enable_delete_game_on_disk = settings_record.settings.get('enableDeleteGameOnDisk', True)
        enable_game_updates = settings_record.settings.get('enableGameUpdates', True)
        enable_game_extras = settings_record.settings.get('enableGameExtras', True)
    else:
        # Default values if no settings_record is found
        show_logo = True
        show_help_button = True
        enable_web_links = True
        enable_server_status = True
        enable_newsletter = True
        show_version = True  # Default to showing version
        enable_delete_game_on_disk = True
        enable_game_updates = True
        enable_game_extras = True

    return dict(
        show_logo=show_logo, 
        show_help_button=show_help_button, 
        enable_web_links=enable_web_links,
        enable_server_status=enable_server_status,
        enable_newsletter=enable_newsletter,
        show_version=show_version,
        app_version=app_version,
        enable_delete_game_on_disk=enable_delete_game_on_disk,
        enable_game_updates=enable_game_updates,
        enable_game_extras=enable_game_extras
    )

@bp.context_processor
def utility_processor():
    return dict(datetime=datetime)

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


@bp.route('/login/invites', methods=['GET', 'POST'])
@login_required
def invites():
    form = InviteForm()
    if form.validate_on_submit():
        email = request.form.get('email')
        # Ensure the user has invites left to send
        current_invites = InviteToken.query.filter_by(creator_user_id=current_user.user_id, used=False).count()
        if current_user.invite_quota > current_invites:
            token = str(uuid.uuid4())
            invite_token = InviteToken(token=token, creator_user_id=current_user.user_id)
            db.session.add(invite_token)
            db.session.commit()

            invite_url = url_for('main.register', token=token, _external=True, _scheme='https')

            send_invite_email(email, invite_url)

            flash('Invite sent successfully. The invite expires after 48 hours.', 'success')
        else:
            flash('You have reached your invite limit.', 'danger')
        return redirect(url_for('main.invites'))

    invites = InviteToken.query.filter_by(creator_user_id=current_user.user_id, used=False).all()
    current_invites_count = len(invites)
    remaining_invites = max(0, current_user.invite_quota - current_invites_count)

    return render_template('/login/user_invites.html', form=form, invites=invites, invite_quota=current_user.invite_quota, remaining_invites=remaining_invites)

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

def send_invite_email(email, invite_url):
    subject = "You're Invited!"
    html_content = render_template('login/invite_email.html', invite_url=invite_url)
    send_email(email, subject, html_content)




@bp.route('/api/current_user_role', methods=['GET'])
@login_required
def get_current_user_role():
    # print(f"Route: /api/current_user_role - {current_user.role}")
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
            # Define old_thumbnailpath based on old_avatarpath
            if old_avatarpath and old_avatarpath != 'newstyle/avatar_default.jpg':
                old_thumbnailpath = os.path.splitext(old_avatarpath)[0] + '_thumbnail' + os.path.splitext(old_avatarpath)[1]
            else:
                old_thumbnailpath = None  # No old thumbnail to worry about

            filename = secure_filename(file.filename)
            uuid_filename = str(uuid4()) + '.' + filename.rsplit('.', 1)[1].lower()
            image_path = os.path.join(upload_folder, uuid_filename)
            file.save(image_path)

            # Image processing
            img = PILImage.open(image_path)
            img = square_image(img, 500)  # Assume square_image is correctly defined elsewhere
            img.save(image_path)

            img = PILImage.open(image_path)
            img = square_image(img, 50)
            thumbnail_path = os.path.splitext(image_path)[0] + '_thumbnail' + os.path.splitext(image_path)[1]
            img.save(thumbnail_path)

            # Delete old avatar and thumbnail if they exist
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




@bp.route('/admin/newsletter', methods=['GET', 'POST'])
@login_required
@admin_required
def newsletter():
    settings_record = GlobalSettings.query.first()
    enable_newsletter = settings_record.settings.get('enableNewsletterFeature', False) if settings_record else False

    if not enable_newsletter:
        flash('Newsletter feature is disabled.', 'warning')
        print("ADMIN NEWSLETTER: Newsletter feature is disabled.")
        return redirect(url_for('main.admin_dashboard'))
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
    return render_template('admin/admin_newsletter.html', title='Newsletter', form=form, users=users)


@bp.route('/admin/whitelist', methods=['GET', 'POST'])
@login_required
@admin_required
def whitelist():
    form = WhitelistForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        new_whitelist = Whitelist(email=email)
        db.session.add(new_whitelist)
        try:
            db.session.commit()
            flash('The email was successfully added to the whitelist!', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('The email is already in the whitelist!', 'danger')
        return redirect(url_for('main.whitelist'))

    # Get whitelist entries and check registration status
    whitelist_entries = Whitelist.query.all()
    for entry in whitelist_entries:
        entry.is_registered = User.query.filter(func.lower(User.email) == entry.email.lower()).first() is not None

    return render_template('admin/admin_manage_whitelist.html', 
                         title='Whitelist', 
                         whitelist=whitelist_entries, 
                         form=form)

@bp.route('/admin/whitelist/<int:whitelist_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_whitelist(whitelist_id):
    try:
        whitelist_entry = Whitelist.query.get_or_404(whitelist_id)
        db.session.delete(whitelist_entry)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Entry deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500



@bp.route('/admin/users', methods=['GET'])
@login_required
@admin_required
def manage_users():
    users = User.query.all()
    return render_template('admin/admin_manage_users.html', users=users)

@bp.route('/admin/api/user/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@admin_required
def manage_user_api(user_id):
    if request.method == 'PUT' and user_id == 0:  # Special case for new user creation
        data = request.json
        try:
            new_user = User(
                name=data['username'],
                email=data['email'],
                role=data.get('role', 'user'),
                state=data.get('state', True),
                is_email_verified=data.get('is_email_verified', True),
                user_id=str(uuid4())
            )
            new_user.set_password(data['password'])
            db.session.add(new_user)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    user = User.query.get_or_404(user_id)
    
    if request.method == 'GET':
        return jsonify({
            'email': user.email,
            'role': user.role,
            'state': user.state,
            'is_email_verified': user.is_email_verified
        })
    
    elif request.method == 'PUT':
        if user_id == 1 and current_user.id != 1:
            return jsonify({'success': False, 'message': 'Cannot modify admin account'}), 403
        
        data = request.json
        user.email = data.get('email', user.email)
        user.role = data.get('role', user.role)
        user.state = data.get('state', user.state)
        user.is_email_verified = data.get('is_email_verified', user.is_email_verified)
        
        if data.get('password'):
            user.set_password(data['password'])
        
        try:
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
    
    elif request.method == 'DELETE':
        if user_id == 1:
            return jsonify({'success': False, 'message': 'Cannot delete admin account'}), 403
        
        try:
            db.session.delete(user)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/admin/user_manager', methods=['GET', 'POST'])
@login_required
@admin_required
def usermanager():
    # check if this is redundant
    return redirect(url_for('main.manage_users'))
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

    return render_template('admin/admin_manage_users.html', form=form, users=users_query)


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
    return render_template('games/downloads.html', download_requests=download_requests, form=form)


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
            

    # print("Game names with IDs:", game_names_with_ids)
    return render_template('admin/admin_manage_scanjobs.html', form=form, game_names_with_ids=game_names_with_ids)


  
@bp.route('/admin/api_debug', methods=['GET', 'POST'])
@login_required
@admin_required
def api_debug():
    form = IGDBApiForm()
    api_response = None

    if form.validate_on_submit():
        selected_endpoint = form.endpoint.data
        query_params = form.query.data
        print(f"Selected endpoint: {selected_endpoint} with query params: {query_params}")
        api_response = make_igdb_api_request(selected_endpoint, query_params)
        
    return render_template('admin/admin_debug_api.html', form=form, api_response=api_response)


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
        
        running_job = ScanJob.query.filter_by(status='Running').first()
        if running_job:
            flash('A scan is already in progress. Please wait until the current scan completes.', 'error')
            session['active_tab'] = 'auto'
            return redirect(url_for('main.scan_management', library_uuid=library_uuid, active_tab='auto'))

    
        library_uuid = auto_form.library_uuid.data
        library = Library.query.filter_by(uuid=library_uuid).first()
        if not library:
            flash('Selected library does not exist.', 'error')
            return redirect(url_for('main.scan_management', library_uuid=library_uuid, active_tab='auto'))

        
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
            return redirect(url_for('main.library'))

        @copy_current_request_context
        def start_scan():
            scan_and_add_games(full_path, scan_mode, library_uuid)

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
                supported_extensions = ["32x", "7z", "a26", "a52", "a78", "adf", "arj", "bin", "col", "crt", "d64", "exe", "fds", "fig", "gb", "gba", "gbc", "gen", "gg", "img", "iso", "lnx", "md", "n64", "nes", "ng", "pce", "rar", "rom", "sfc", "smc", "smd", "sms", "swc", "t64", "tap", "uae", "unf", "v64", "z64", "z80", "zip"]
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
            return redirect(url_for('main.library'))
    
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
                return redirect(url_for('main.library'))
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
        new_folder_size_bytes = get_folder_size_in_bytes(game.full_disk_path)
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
                    
            return redirect(url_for('main.library'))
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

    flash('Image(s) uploaded successfully', 'success')
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




@bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_settings():
    if request.method == 'POST':
        new_settings = request.json

        settings_record = GlobalSettings.query.first()
        if not settings_record:
            settings_record = GlobalSettings(settings={})
            db.session.add(settings_record)
        
        settings_record.settings = new_settings
        settings_record.enable_delete_game_on_disk = new_settings.get('enableDeleteGameOnDisk', True)
        settings_record.discord_notify_new_games = new_settings.get('discordNotifyNewGames', False)
        settings_record.discord_notify_game_updates = new_settings.get('discordNotifyGameUpdates', False)
        settings_record.discord_notify_downloads = new_settings.get('discordNotifyDownloads', False)
        settings_record.enable_game_updates = new_settings.get('enableGameUpdates', True)
        settings_record.update_folder_name = new_settings.get('updateFolderName', 'updates')
        settings_record.enable_game_extras = new_settings.get('enableGameExtras', True)
        settings_record.extras_folder_name = new_settings.get('extrasFolderName', 'extras')
        settings_record.last_updated = datetime.utcnow()
        db.session.commit()
        cache.delete('global_settings')
        return jsonify({'message': 'Settings updated successfully'}), 200

    else:  # GET request
        settings_record = GlobalSettings.query.first()
        current_settings = settings_record.settings if settings_record else {}
        current_settings['enableDeleteGameOnDisk'] = settings_record.enable_delete_game_on_disk if settings_record else True
        current_settings['discordNotifyNewGames'] = settings_record.discord_notify_new_games if settings_record else False
        current_settings['discordNotifyGameUpdates'] = settings_record.discord_notify_game_updates if settings_record else False
        current_settings['discordNotifyDownloads'] = settings_record.discord_notify_downloads if settings_record else False
        current_settings['enableGameUpdates'] = settings_record.enable_game_updates if settings_record else True
        current_settings['updateFolderName'] = settings_record.update_folder_name if settings_record else 'updates'
        current_settings['enableGameExtras'] = settings_record.enable_game_extras if settings_record else True
        current_settings['extrasFolderName'] = settings_record.extras_folder_name if settings_record else 'extras'
        return render_template('admin/admin_server_settings.html', current_settings=current_settings)


@bp.route('/admin/server_status_page')
@login_required
@admin_required
def admin_server_status():
    
    settings_record = GlobalSettings.query.first()
    enable_server_status = settings_record.settings.get('enableServerStatusFeature', False) if settings_record else False

    if not enable_server_status:
        flash('Server Status feature is disabled.', 'warning')
        return redirect(url_for('main.admin_dashboard'))
    
    uptime = datetime.now() - app_start_time
    config_values = {item: getattr(Config, item) for item in dir(Config) if not item.startswith("__")}
    
    
    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
    except Exception as e:
        ip_address = 'Unavailable'
        print(f"Error retrieving IP address: {e}")
    
    system_info = {
        'OS': platform.system(),
        'OS Version': platform.version(),
        'Python Version': platform.python_version(),
        'Hostname': socket.gethostname(),
        'IP Address': socket.gethostbyname(socket.gethostname()),
        'Flask Port': request.environ.get('SERVER_PORT'),
        'Uptime': str(uptime),
        'Current Time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return render_template('admin/admin_server_info.html', config_values=config_values, system_info=system_info, app_version=app_version)

@bp.route('/admin/manage_invites', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_invites():

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        invites_number = int(request.form.get('invites_number'))

        user = User.query.filter_by(user_id=user_id).first()
        if user:
            user.invite_quota += invites_number
            db.session.commit()
            flash('Invites updated successfully.', 'success')
        else:
            flash('User not found.', 'error')

    users = User.query.all()
    # Calculate unused invites for each user
    user_unused_invites = {}
    for user in users:
        unused_count = InviteToken.query.filter_by(
            creator_user_id=user.user_id,
            used=False
        ).count()
        user_unused_invites[user.user_id] = unused_count

    return render_template('admin/admin_manage_invites.html', 
                         users=users, 
                         user_unused_invites=user_unused_invites)


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
    return render_template('admin/admin_manage_filters.html', form=form, groups=groups)

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
            "nfo_content": game.nfo_content if game.nfo_content else 'none',
            "size": format_size(game.size),
            "date_identified": game.date_identified.strftime('%Y-%m-%d %H:%M:%S') if game.date_identified else 'Not available',
            "steam_url": game.steam_url if game.steam_url else 'Not available',
            "times_downloaded": game.times_downloaded,
            "updates": [{
                "id": update.id,
                "file_path": update.file_path,
                "times_downloaded": update.times_downloaded,
                "created_at": update.created_at.strftime('%Y-%m-%d %H:%M:%S')
            } for update in game.updates]
        }
        
        # URL Icons Mapping
        # Updated for FontAwesome v6
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
            # Add or update mappings as needed
        }


        # Augment game_data with URLs
        game_data['urls'] = [{
            "type": url.url_type,
            "url": url.url,
            "icon": url_icons.get(url.url_type, "fa-link")
        } for url in game.urls]
        
        settings = GlobalSettings.query.first()
        if not settings or not settings.discord_notify_new_games:
            print("Discord notifications for new games are disabled")
            return
        update_folder = settings.update_folder_name if settings and settings.update_folder_name else current_app.config['UPDATE_FOLDER_NAME']
        extras_folder = settings.extras_folder_name if settings and settings.extras_folder_name else current_app.config['EXTRAS_FOLDER_NAME']
        update_files = list_files(game.full_disk_path, update_folder)
        extras_files = list_files(game.full_disk_path, extras_folder)
        
        library_uuid = game.library_uuid
        
        return render_template('games/game_details.html', game=game_data, form=csrf_form, library_uuid=library_uuid, update_files=update_files, extras_files=extras_files)
    else:
        return jsonify({"error": "Game not found"}), 404




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
        return redirect(url_for('main.library'))



@bp.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    pass
    return render_template('admin/admin_dashboard.html')

@bp.route('/admin/discord_settings', methods=['GET', 'POST'])
@login_required
@admin_required
def discord_settings():
    settings = GlobalSettings.query.first()
    
    if request.method == 'POST':
        if not settings:
            settings = GlobalSettings()
            db.session.add(settings)
        
        settings.discord_webhook_url = request.form.get('discord_webhook_url', '')
        settings.discord_bot_name = request.form.get('discord_bot_name', '')
        settings.discord_bot_avatar_url = request.form.get('discord_bot_avatar_url', '')
        
        try:
            db.session.commit()
            flash('Discord settings updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating Discord settings: {str(e)}', 'error')
        
        return redirect(url_for('main.discord_settings'))

    # Get default values from config if no settings exist
    webhook_url = settings.discord_webhook_url if settings else Config.DISCORD_WEBHOOK_URL
    bot_name = settings.discord_bot_name if settings else Config.DISCORD_BOT_NAME
    bot_avatar_url = settings.discord_bot_avatar_url if settings else Config.DISCORD_BOT_AVATAR_URL

    return render_template('admin/admin_discord_settings.html',
                         webhook_url=webhook_url,
                         bot_name=bot_name,
                         bot_avatar_url=bot_avatar_url)

@bp.route('/admin/themes', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_themes():
    form = ThemeUploadForm()
    theme_manager = ThemeManager(current_app)
    

    # Ensure UPLOAD_FOLDER exists
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'themes')
    if not os.path.exists(upload_folder):
        try:
            # Safe check to avoid creating 'static' directly
            os.makedirs(upload_folder, exist_ok=True)
        except Exception as e:
            print(f"Error creating upload directory: {e}")
            flash("Error processing request. Please try again.", 'error')
            return redirect(url_for('main.manage_themes'))

    if form.validate_on_submit():
        theme_zip = form.theme_zip.data
        try:
            theme_data = theme_manager.upload_theme(theme_zip)
            if theme_data:
                flash(f"Theme '{theme_data['name']}' uploaded successfully!", 'success')
            else:
                flash("Theme upload failed. Please check the error messages.", 'error')
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash(f"An unexpected error occurred: {str(e)}", 'error')
        return redirect(url_for('main.manage_themes'))

    installed_themes = theme_manager.get_installed_themes()
    default_theme = theme_manager.get_default_theme()
    return render_template('admin/admin_manage_themes.html', form=form, themes=installed_themes, default_theme=default_theme)

@bp.route('/admin/themes/readme')
@login_required
@admin_required
def theme_readme():
    return render_template('admin/readme_theme.html')

@bp.route('/admin/themes/delete/<theme_name>', methods=['POST'])
@login_required
@admin_required
def delete_theme(theme_name):
    theme_manager = ThemeManager(current_app)
    try:
        theme_manager.delete_theme(theme_name)
        flash(f"Theme '{theme_name}' deleted successfully!", 'success')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", 'error')
    return redirect(url_for('main.manage_themes'))

@bp.context_processor
def inject_current_theme():
    if current_user.is_authenticated and current_user.preferences:
        current_theme = current_user.preferences.theme or 'default'
    else:
        current_theme = 'default'
    return dict(current_theme=current_theme)

# Remove the get_current_theme function as it's no longer needed

@bp.route('/delete_game/<string:game_uuid>', methods=['POST'])
@login_required
@admin_required
def delete_game_route(game_uuid):
    print(f"Route: /delete_game - {current_user.name} - {current_user.role} method: {request.method} UUID: {game_uuid}")
    
    if is_scan_job_running():
        print(f"Error: Attempt to delete game UUID: {game_uuid} while scan job is running")
        flash('Cannot delete the game while a scan job is running. Please try again later.', 'error')
        return redirect(url_for('main.library'))
    delete_game(game_uuid)
    return redirect(url_for('main.library'))

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
            delete_game(game.uuid)  # Assuming delete_game is adapted to work with UUIDs
        except FileNotFoundError as fnfe:
            # Handling "file not found" errors specifically
            print(f'File not found for game with UUID {game.uuid}: {fnfe}')
            flash(f'File not found for game with UUID {game.uuid}. Skipping...', 'info')
            continue  # Explicitly continue with the next game
        except Exception as e:
            # Specific handling for "access denied" or similar permission-related errors
            if "access denied" in str(e).lower():
                print(f'Access denied for game with UUID {game.uuid}: {e}')
                flash(f'Access denied for game with UUID {game.uuid}. Skipping...', 'warning')
            else:
                print(f'Error deleting game with UUID {game.uuid}: {e}')
                flash(f'Error deleting game with UUID {game.uuid}: {e}', 'error')
            continue  # Explicitly continue with the next game

    flash('All accessible games and their images have been deleted successfully.', 'success')
    return redirect(url_for('main.scan_management'))


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

    return redirect(url_for('main.libraries'))




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

@bp.route('/download_file/<file_location>/<file_size>/<game_uuid>/<file_name>', methods=['GET'])
@login_required
def download_file(file_location, file_size, game_uuid, file_name):
    print(f"Downloading file with location: {file_location}")
    if os.path.isfile(file_location):
        file_size_stripped = ''.join(filter(str.isdigit, file_size))
        file_size_bytes = int(file_size_stripped)*10000
    else:
        file_size_bytes = get_folder_size_in_bytes(file_location)
        
    # Check for any existing download request for the same file by the current user, regardless of status
    existing_request = DownloadRequest.query.filter_by(user_id=current_user.id, file_location=file_location).first()
    
    if existing_request:
        flash("You already have a download request for this file in your basket. Please check your downloads page.", "info")
        return redirect(url_for('main.downloads'))

    print(f"Creating a new download request for user {current_user.id} for file {file_location}")
    new_request = DownloadRequest(
        user_id=current_user.id,
        zip_file_path=file_location,
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
        games = games_query.limit(limit).all()
        game_details = []
        for game in games:
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

    return render_template('games/discover.html',
                           latest_games=latest_games,
                           most_downloaded_games=most_downloaded_games,
                           highest_rated_games=highest_rated_games,
                           libraries=libraries, loc=page_loc)



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
    
def get_library_count():
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
    return len(libraries)

def get_games_count():
    # Direct query to the Games model
    games_query = Game.query.all()
    games = [
        {
            'uuid': game.uuid,
            'name': game.name,
        } for game in games_query
    ]

    # Logging the count of games returned
    print(f"Returning {len(games)} games.")
    return len(games)

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



@bp.route('/help')
def helpfaq():
    print("Route: /help")
    return render_template('site/site_help.html')



@bp.route('/libraries')
@login_required
@admin_required
def libraries():
    libraries = Library.query.all()
    csrf_form = CsrfProtectForm()
    game_count = Game.query.count()  # Fetch the game count here
    return render_template('admin/admin_manage_libraries.html', libraries=libraries, csrf_form=csrf_form, game_count=game_count)

@bp.route('/library/add', methods=['GET', 'POST'])
@bp.route('/library/edit/<library_uuid>', methods=['GET', 'POST'])
@login_required
@admin_required
def add_edit_library(library_uuid=None):
    if library_uuid:
        library = Library.query.filter_by(uuid=library_uuid).first_or_404()
        form = LibraryForm(obj=library)
        page_title = "Edit Library"
        print(f"Editing library: {library.name}, Platform: {library.platform.name}")
    else:
        library = None
        form = LibraryForm()
        page_title = "Add Library"
        print("Adding new library")

    form.platform.choices = [(platform.name, platform.value) for platform in LibraryPlatform]
    print(f"Platform choices: {form.platform.choices}")
    
    if library:
        form.platform.data = library.platform.name  # Set the initial value for existing library
        print(f"Setting initial platform value: {form.platform.data}")

    if form.validate_on_submit():
        if library is None:
            library = Library(uuid=str(uuid4()))  # Generate a new UUID for new libraries

        library.name = form.name.data
        try:
            library.platform = LibraryPlatform[form.platform.data]
        except KeyError:
            flash(f'Invalid platform selected: {form.platform.data}', 'error')
            return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)

        file = form.image.data
        if file:
            # Validate file size (< 5 MB)
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            if file_length > 5 * 1024 * 1024:  # 5MB limit
                flash('File size is too large. Maximum allowed is 5 MB.', 'error')
                return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)

            # Reset file pointer after checking size
            file.seek(0)

            upload_folder = current_app.config['UPLOAD_FOLDER']
            print(f"Upload folder now: {upload_folder}")
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder, exist_ok=True)

            filename = secure_filename(file.filename)
            uuid_filename = str(uuid4()) + '.png'  # Always save as PNG
            image_folder = os.path.join(upload_folder, 'images')
            print(f"Image folder: {image_folder}")
            if not os.path.exists(image_folder):
                os.makedirs(image_folder, exist_ok=True)
            image_path = os.path.join(image_folder, uuid_filename)
            print(f"Image path: {image_path}")

            # Open, convert to PNG, and resize if necessary
            with PILImage.open(file) as img:
                img = img.convert('RGBA')
                if img.width > 1024 or img.height > 1024:
                    img.thumbnail((1024, 1024), PILImage.LANCZOS)
                img.save(image_path, 'PNG')

            image_url = url_for('static', filename=os.path.join('library/images/', uuid_filename))
            print(f"Image URL: {image_url}")
            library.image_url = image_url
        elif not library.image_url:
            library.image_url = url_for('static', filename='newstyle/default_library.jpg')

        if library not in db.session:
            db.session.add(library)
        try:
            db.session.commit()
            flash('Library saved successfully!', 'success')
            return redirect(url_for('main.libraries'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to save library. Please try again.', 'error')
            print(f"Error saving library: {e}")

    return render_template('admin/admin_manage_library_create.html', form=form, library=library, page_title=page_title)


@bp.route('/library')
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

    # Extract filters from request arguments
    page = request.args.get('page', 1, type=int)
    library_uuid = request.args.get('library_uuid')
    library_name = request.args.get('library_name')
    # Only override per_page, sort_by, and sort_order if the URL parameters are provided
    per_page = request.args.get('per_page', type=int) or per_page
    genre = request.args.get('genre')
    rating = request.args.get('rating', type=int)
    game_mode = request.args.get('game_mode')
    player_perspective = request.args.get('player_perspective')
    theme = request.args.get('theme')
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
        library = Library.query.filter_by(name=library_name).first()
        if library:
            print(f'Library found: {library}')
            filters['library_uuid'] = library.uuid
        else:
            flash('Library not found.', 'error')
            return redirect(url_for('main.library'))


    game_data, total, pages, current_page = get_games(page, per_page, sort_by=sort_by, sort_order=sort_order, **filters)
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

    # print(f"LIBRARY: context: {locals()}")  # Updated for debugging purposes

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
        library_uuid = library_uuid
    )


def get_games(page=1, per_page=20, sort_by='name', sort_order='asc', **filters):
    query = Game.query.options(joinedload(Game.genres))

    # Resolve library_name to library_uuid if necessary
    if 'library_name' in filters and filters['library_name']:
        library = Library.query.filter_by(name=filters['library_name']).first()
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



    # print(f"get_games: Filters: {filters}")
    
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

    # print(f"get_games: Sorting by {sort_by} {sort_order}")
    # Pagination
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    games = pagination.items

    game_data = []
    for game in games:
        cover_image = Image.query.filter_by(game_uuid=game.uuid, image_type='cover').first()
        cover_url = cover_image.url if cover_image else "newstyle/default_cover.jpg"
        genres = [genre.name for genre in game.genres]
        game_size_formatted = format_size(game.size)
        first_release_date_formatted = game.first_release_date.strftime('%Y-%m-%d') if game.first_release_date else 'Not available'


        game_data.append({
            'id': game.id,
            'uuid': game.uuid,
            'name': game.name,
            'cover_url': cover_url,
            'summary': game.summary,
            'url': game.url,
            'size': game_size_formatted,
            'genres': genres,
            'first_release_date': first_release_date_formatted
        })

    return game_data, pagination.total, pagination.pages, page

@bp.route('/admin/discord_help')
@login_required
@admin_required
def discord_help():
    return render_template('admin/discord_help.html')


def get_loc(page):
    
    with open(f'modules/static/localization/en/{page}.json', 'r', encoding='utf8') as f:
            loc_data = json.load(f)    
    return loc_data
    
@bp.add_app_template_global  
def verify_file(full_path):
    if os.path.exists(full_path) or os.access(full_path, os.R_OK):
        print(f"File Exists: {full_path}.")
        return True
    else:
        print(f"Cannot find theme specific file: {full_path}. Using default theme file.", 'warning')
        return False
     
def list_files(path, folder):
    content = glob(path + "\\" + folder + '/*');
    print(f"Listing content of directory {path} and folder {folder}.")
         
    files = {
        "path": path,
        "folder": folder,
        "files": [{
            'name': os.path.basename(f),
            'size': format_size(os.path.getsize(f)) if os.path.isfile(f) else format_size(get_folder_size_in_bytes(f)),
            'isfile': os.path.isfile(f),
        } for f in content]
    }
      
    print(f"File updates content {files}.")
    
    return files