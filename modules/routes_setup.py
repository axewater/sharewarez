from flask import Blueprint, render_template, flash, redirect, url_for, request, session
from flask_login import current_user
from modules import db
from sqlalchemy import select
from modules.forms import SetupForm, IGDBSetupForm
from modules.models import User, GlobalSettings
from modules.utils_setup import is_setup_required, set_setup_step, mark_setup_complete, get_current_setup_step
from uuid import uuid4
from datetime import datetime, timezone
from modules.utils_logging import log_system_event

setup_bp = Blueprint('setup', __name__)

@setup_bp.route('/setup', methods=['GET'])
def setup():    
    # Check if setup is required
    if not is_setup_required():
        flash('Setup has already been completed.', 'warning')
        return redirect(url_for('login.login'))

    # Set setup step to 1 (admin account creation)
    set_setup_step(1)

    form = SetupForm()
    return render_template('setup/setup.html', form=form, is_setup_mode=True)

@setup_bp.route('/setup/submit', methods=['POST'])
def setup_submit():
    if not is_setup_required():
        flash('Setup has already been completed.', 'warning')
        return redirect(url_for('login.login'))

    form = SetupForm()
    if form.validate_on_submit():
        print(f"Form CSRF token: {form.csrf_token.data}")
        print(f"Form validation succeeded")
        
        user = User(
            name=form.username.data,
            email=form.email.data.lower(),
            role='admin',
            is_email_verified=True,
            user_id=str(uuid4()),
            invite_quota=10,
            created=datetime.now(timezone.utc)
        )
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            set_setup_step(2)  # Move to SMTP setup
            log_system_event("Admin account created during setup", event_type='setup', event_level='information')
            flash('Admin account created successfully! Please configure your SMTP settings.', 'success')
            return redirect(url_for('setup.setup_smtp'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error during setup: {str(e)}', 'error')
            return redirect(url_for('setup.setup'))
    else:
        print(f"Form contents: {form.data}")
        print(f"Form validation failed: {form.errors}")
        return render_template('setup/setup.html', form=form, is_setup_mode=True)

@setup_bp.route('/setup/smtp', methods=['GET', 'POST'])
def setup_smtp():
    # Ensure we're in the correct setup step
    current_step = get_current_setup_step()
    
    if current_step is None:
        flash('Setup already completed.', 'warning')
        return redirect(url_for('login.login'))
    
    if current_step != 2:
        flash('Please complete the admin account setup first.', 'warning')
        return redirect(url_for('setup.setup'))

    if request.method == 'POST':
        # Check if skip button was clicked
        if 'skip_smtp' in request.form:
            set_setup_step(3)  # Move to IGDB setup even when skipping
            flash('SMTP setup skipped. Please configure your IGDB settings.', 'info')
            return redirect(url_for('setup.setup_igdb'))

        settings = db.session.execute(select(GlobalSettings)).scalars().first()
        if not settings:
            settings = GlobalSettings()
            db.session.add(settings)

        settings.smtp_server = request.form.get('smtp_server')
        settings.smtp_port = int(request.form.get('smtp_port', 587))
        settings.smtp_username = request.form.get('smtp_username')
        settings.smtp_password = request.form.get('smtp_password')
        settings.smtp_use_tls = request.form.get('smtp_use_tls') == 'true'
        settings.smtp_default_sender = request.form.get('smtp_default_sender')
        settings.smtp_enabled = request.form.get('smtp_enabled') == 'true'

        try:
            db.session.commit()
            set_setup_step(3)  # Move to IGDB setup
            log_system_event("SMTP settings configured during setup", event_type='setup', event_level='information')
            flash('SMTP settings saved successfully! Please configure your IGDB settings.', 'success')
            return redirect(url_for('setup.setup_igdb'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving SMTP settings: {str(e)}', 'error')

    return render_template('setup/setup_smtp.html', is_setup_mode=True)

@setup_bp.route('/setup/igdb', methods=['GET', 'POST'])
def setup_igdb():
    current_step = get_current_setup_step()
    
    if current_step != 3:
        flash('Please complete the SMTP setup first.', 'warning')
        return redirect(url_for('setup.setup'))

    form = IGDBSetupForm()
    if form.validate_on_submit():
        settings = db.session.execute(select(GlobalSettings)).scalars().first()
        if not settings:
            settings = GlobalSettings()
            db.session.add(settings)
        
        settings.igdb_client_id = form.igdb_client_id.data
        settings.igdb_client_secret = form.igdb_client_secret.data
        
        try:
            db.session.commit()
            mark_setup_complete()  # Mark setup as fully completed
            log_system_event("IGDB settings configured - Setup completed", event_type='setup', event_level='information')
            flash('Setup completed successfully! Please create your first game library.', 'success')
            from modules.init_data import initialize_library_folders, insert_default_scanning_filters, initialize_default_settings, initialize_allowed_file_types, initialize_discovery_sections

            initialize_library_folders()
            initialize_discovery_sections()
            insert_default_scanning_filters()
            initialize_default_settings()
            initialize_allowed_file_types()
            return redirect(url_for('library.libraries'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving IGDB settings: {str(e)}', 'error')

    return render_template('setup/setup_igdb.html', form=form, is_setup_mode=True)
