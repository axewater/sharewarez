import uuid
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, abort
from flask_login import current_user, login_user, logout_user, login_required
from config import Config
from modules import db
from modules.models import User, InviteToken, GlobalSettings, Whitelist
from modules.forms import LoginForm, RegistrationForm, ResetPasswordRequestForm, InviteForm, CsrfProtectForm, UserPasswordForm
from modules.utils_auth import _authenticate_and_redirect
from modules.utils_smtp import send_email, send_password_reset_email, send_invite_email
from modules.utils_processors import get_global_settings
from modules.utils_logging import log_system_event
from modules import cache
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from uuid import uuid4
from sqlalchemy.exc import IntegrityError


login_bp = Blueprint('login', __name__)
s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

def is_smtp_configured():
    """Check if SMTP settings are properly configured."""
    settings = db.session.execute(select(GlobalSettings)).scalar_one_or_none()
    if not settings:
        return False
    return bool(settings.smtp_server and 
                settings.smtp_port and 
                settings.smtp_username and 
                settings.smtp_password)

@login_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()

@login_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('discover.discover'))


    print("Route: /login")
    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = db.session.execute(select(User).filter_by(name=username)).scalar_one_or_none()

        if user:
            if not user.is_email_verified:
                flash('Your account is not activated, check your email.', 'warning')
                log_system_event(f"User {username} attempted to log in with an unverified account.", event_type='login', event_level='warning')
                return redirect(url_for('login.login'))

            if not user.state:
                flash('Your account has been banned.', 'error')
                log_system_event(f"User {username} attempted to log in with a banned account.", event_type='login', event_level='warning')
                print(f"Error: Attempted login to disabled account - User: {username}")
                return redirect(url_for('login.login'))

            log_system_event(f"User {username} logged in successfully.", event_type='login', event_level='information')
            return _authenticate_and_redirect(username, password)
        else:
            flash('Invalid username or password. USERNAMES ARE CASE SENSITIVE!', 'error')
            log_system_event(f"User {username} attempted to log in with invalid credentials.", event_type='login', event_level='warning')
            return redirect(url_for('login.login'))

    return render_template('login/login.html', form=form)


@login_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('login.login'))
    print("Route: /register")

    # Attempt to get the invite token from the query parameters
    invite_token_from_url = request.args.get('token')
    print(f"Invite token from URL: {invite_token_from_url}")
    invite = None
    if invite_token_from_url:
        invite = db.session.execute(select(InviteToken).filter_by(token=invite_token_from_url, used=False)).scalar_one_or_none()
        print(f"Invite found: {invite}")
        if invite and invite.expires_at >= datetime.now(timezone.utc):
            # The invite is valid; skip the whitelist check later
            pass
        else:
            invite = None  # Invalidate
            flash('The invite is invalid or has expired.', 'warning')
            return redirect(url_for('login.register'))
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            email_address = form.email.data.lower()
            existing_user_email = db.session.execute(select(User).filter(func.lower(User.email) == email_address)).scalar_one_or_none()
            if existing_user_email:
                print(f"/register: Email already in use - {email_address}")
                flash('This email is already in use. Please use a different email or log in.')
                return redirect(url_for('login.register'))
                    # Proceed with the whitelist check only if no valid invite token is provided
            if not invite:
                whitelist = db.session.execute(select(Whitelist).filter(func.lower(Whitelist.email) == email_address)).scalar_one_or_none()
                if not whitelist:
                    flash('Your email is not whitelisted.')
                    return redirect(url_for('login.register'))

            existing_user = db.session.execute(select(User).filter_by(name=form.username.data)).scalar_one_or_none()
            if existing_user is not None:
                print(f"/register: User already exists - {form.username.data}")
                flash('User already exists. Please Log in.')
                return redirect(url_for('login.register'))

            user_uuid = str(uuid4())
            existing_uuid = db.session.execute(select(User).filter_by(user_id=user_uuid)).scalar_one_or_none()
            if existing_uuid is not None:
                print("/register: UUID collision detected.")
                flash('An error occurred while registering. Please try again.')
                return redirect(url_for('login.register'))

            user = User(
                user_id=user_uuid,
                name=form.username.data,
                email=form.email.data.lower(),
                role='user',
                is_email_verified=False,
                email_verification_token=s.dumps(form.email.data, salt='email-confirm'),
                token_creation_time=datetime.now(timezone.utc),
                created=datetime.now(timezone.utc)
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            
            log_system_event(f"New user registered: {user.name}", event_type='audit', event_level='information')
            
            if invite:
                invite.used = True
                invite.used_by = user.user_id

            # Verification email
            verification_token = user.email_verification_token
            confirm_url = url_for('login.confirm_email', token=verification_token, _external=True)
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


@login_bp.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=900)  # 15 minutes
    except SignatureExpired:
        return render_template('login/confirmation_expired.html'), 400
    except BadSignature:
        return render_template('login/confirmation_invalid.html'), 400

    user = db.session.execute(select(User).filter_by(email=email)).scalar_one_or_none() or abort(404)
    if user.is_email_verified:
        return render_template('login/registration_already_confirmed.html')
    else:
        user.is_email_verified = True
        db.session.add(user)
        db.session.commit()
        return render_template('login/confirmation_success.html')


@login_bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('login.login'))
    print(f'pwr Reset Password Request')
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        print(f'pwr form data: {form.data}')
        user = db.session.execute(select(User).filter_by(email=form.email.data.lower())).scalar_one_or_none()
        print(f'pwr user: {user}')
        if user:
            # Generate a unique token
            token = s.dumps(user.email, salt='password-reset-salt')
            user.password_reset_token = token
            user.token_creation_time = datetime.now(timezone.utc)
            
            log_system_event(f"Password reset requested for user: {user.email}", event_type='password_reset', event_level='information')
            
            db.session.commit()

            # Send reset email
            print('Calling send password reset email function...')
            send_password_reset_email(user.email, token)
            flash('Check your email for instructions to reset your password.')
            return redirect(url_for('login.login'))
        else:
            flash('Email address not found.')
            return redirect(url_for('login.reset_password_request'))

    return render_template('login/reset_password_request.html', title='Reset Password', form=form)

@login_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('login.login'))

    user = db.session.execute(select(User).filter_by(password_reset_token=token)).scalar_one_or_none()
    if not user or user.token_creation_time + timedelta(minutes=15) < datetime.now(timezone.utc):
        flash('The password reset link is invalid or has expired.')
        return redirect(url_for('login.login'))

    form = UserPasswordForm()

    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.password_reset_token = None
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login.login'))

    return render_template('login/reset_password.html', form=form, token=token)


@login_bp.route('/user/invites', methods=['GET', 'POST'])
@login_required
def invites():
    settings = db.session.execute(select(GlobalSettings)).scalar_one_or_none()
    site_url = settings.site_url if settings else 'http://127.0.0.1'
    smtp_enabled = is_smtp_configured()
    if site_url == 'http://127.0.0.1'and current_user.role == 'admin':
        flash('Please configure the site URL in the admin settings.', 'danger')
    form = InviteForm()
    if form.validate_on_submit():
        email = request.form.get('email')
        # Ensure the user has invites left to send
        current_invites = db.session.scalar(select(func.count(InviteToken.id)).filter_by(creator_user_id=current_user.user_id, used=False))
        if current_user.invite_quota > current_invites:
            token = str(uuid.uuid4())
            invite_token = InviteToken(
                token=token, 
                creator_user_id=current_user.user_id,
                recipient_email=email
            )
            db.session.add(invite_token)
            db.session.commit()

            settings = db.session.execute(select(GlobalSettings)).scalar_one_or_none()
            site_url = settings.site_url if settings else 'http://127.0.0.1'
            
            # Build the invite URL using the configured site URL
            invite_url = f"{site_url}/register?token={token}"

            send_invite_email(email, invite_url)

            flash('Invite sent successfully. The invite expires after 48 hours.', 'success')
        else:
            flash('You have reached your invite limit.', 'danger')
        return redirect(url_for('login.invites'))

    invites = db.session.execute(select(InviteToken).filter_by(creator_user_id=current_user.user_id, used=False)).scalars().all()
    current_invites_count = len(invites)
    remaining_invites = max(0, current_user.invite_quota - current_invites_count)

    return render_template('/login/user_invites.html', 
                         form=form, 
                         invites=invites, 
                         invite_quota=current_user.invite_quota, 
                         site_url=site_url, 
                         smtp_enabled=smtp_enabled,
                         current_invites_count=current_invites_count, 
                         remaining_invites=remaining_invites, 
                         current_datetime=datetime.now(timezone.utc))

@login_bp.route('/delete_invite/<token>', methods=['POST'])
@login_required
def delete_invite(token):
    try:
        invite = db.session.execute(select(InviteToken).filter_by(token=token, creator_user_id=current_user.user_id)).scalar_one_or_none()
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
