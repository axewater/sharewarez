from flask import Blueprint, render_template, flash, redirect, url_for, request, session
from flask_login import current_user
from modules import db
from modules.forms import SetupForm, IGDBSetupForm
from modules.models import User, GlobalSettings
from uuid import uuid4
from datetime import datetime

setup_bp = Blueprint('setup', __name__)

@setup_bp.context_processor
def inject_current_theme():
    if current_user.is_authenticated and current_user.preferences:
        current_theme = current_user.preferences.theme or 'default'
    else:
        current_theme = 'default'
    return dict(current_theme=current_theme)

@setup_bp.route('/setup', methods=['GET'])
def setup():    
    # Clear any existing session data when starting setup
    session.clear()
    session['setup_step'] = 1

    if User.query.first():
        flash('Setup has already been completed.', 'warning')
        return redirect(url_for('main.login'))

    form = SetupForm()
    return render_template('setup/setup.html', form=form)

@setup_bp.route('/setup/submit', methods=['POST'])
def setup_submit():
    if User.query.first():
        flash('Setup has already been completed.', 'warning')
        return redirect(url_for('main.login'))

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
            created=datetime.utcnow()
        )
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            session['setup_step'] = 2  # Move to SMTP setup
            flash('Admin account created successfully! Please configure your SMTP settings.', 'success')
            return redirect(url_for('setup.setup_smtp'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error during setup: {str(e)}', 'error')
            return redirect(url_for('setup.setup'))
    else:
        print(f"Form contents: {form.data}")
        print(f"Form validation failed: {form.errors}")
        return render_template('setup/setup.html', form=form)

@setup_bp.route('/setup/smtp', methods=['GET', 'POST'])
def setup_smtp():
    # Ensure we're in the correct setup step
    setup_step = session.get('setup_step')
    
    if setup_step is None:
        flash('Setup already completed.', 'warning')
        return redirect(url_for('main.login'))
    
    if setup_step != 2:
        flash('Please complete the admin account setup first.', 'warning')
        return redirect(url_for('setup.setup'))

    if request.method == 'POST':
        # Check if skip button was clicked
        if 'skip_smtp' in request.form:
            session['setup_step'] = 3  # Move to IGDB setup even when skipping
            flash('SMTP setup skipped. Please configure your IGDB settings.', 'info')
            return redirect(url_for('setup.setup_igdb'))

        settings = GlobalSettings.query.first()
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
            session['setup_step'] = 3  # Move to IGDB setup
            flash('SMTP settings saved successfully! Please configure your IGDB settings.', 'success')
            return redirect(url_for('setup.setup_igdb'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving SMTP settings: {str(e)}', 'error')

    return render_template('setup/setup_smtp.html')

@setup_bp.route('/setup/igdb', methods=['GET', 'POST'])
def setup_igdb():
    if not session.get('setup_step') == 3:
        flash('Please complete the SMTP setup first.', 'warning')
        return redirect(url_for('setup.setup'))

    form = IGDBSetupForm()
    if form.validate_on_submit():
        settings = GlobalSettings.query.first()
        if not settings:
            settings = GlobalSettings()
            db.session.add(settings)
        
        settings.igdb_client_id = form.igdb_client_id.data
        settings.igdb_client_secret = form.igdb_client_secret.data
        
        try:
            db.session.commit()
            session.pop('setup_step', None)  # Clear setup progress
            flash('Setup completed successfully! Please create your first game library.', 'success')
            return redirect(url_for('library.libraries'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving IGDB settings: {str(e)}', 'error')

    return render_template('setup/setup_igdb.html', form=form)
