# /modules/routes_admin_ext/whitelist.py
from flask import render_template, redirect, url_for, jsonify, request, flash, abort
from flask_login import login_required, current_user
from modules.models import Whitelist, User
from modules import db
from modules.forms import WhitelistForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, select
from . import admin2_bp
from modules.utils_logging import log_system_event
from modules.utils_auth import admin_required

@admin2_bp.route('/admin/whitelist', methods=['GET', 'POST'])
@login_required
@admin_required
def whitelist():
    form = WhitelistForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        
        # Additional validation
        if len(email) > 120:
            flash('Email address is too long (maximum 120 characters)', 'danger')
            return redirect(url_for('admin2.whitelist'))
        
        # Validate email format more strictly
        if not email or '@' not in email or email.count('@') != 1:
            flash('Invalid email format', 'danger')
            return redirect(url_for('admin2.whitelist'))
        try:
            new_whitelist = Whitelist(email=email)
            db.session.add(new_whitelist)
            db.session.commit()
            log_system_event(f"Admin {current_user.name} added email to whitelist: {email}", event_type='audit', event_level='information')
            flash('The email was successfully added to the whitelist!', 'success')
        except IntegrityError:
            db.session.rollback()
            log_system_event(f"Admin {current_user.name} attempted to add duplicate email to whitelist: {email}", event_type='audit', event_level='warning')
            flash('The email is already in the whitelist!', 'danger')
        except Exception as e:
            db.session.rollback()
            log_system_event(f"Error adding email to whitelist {email}: {str(e)}", event_type='error', event_level='error')
            flash('An error occurred while adding the email to the whitelist', 'danger')
        return redirect(url_for('admin2.whitelist'))

    # Get whitelist entries and check registration status efficiently
    whitelist_entries = db.session.execute(select(Whitelist)).scalars().all()
    
    # Get all registered emails in one query to avoid N+1 problem
    registered_emails = set()
    if whitelist_entries:
        whitelist_emails = [entry.email.lower() for entry in whitelist_entries]
        registered_users = db.session.execute(
            select(User.email).filter(func.lower(User.email).in_(whitelist_emails))
        ).scalars().all()
        registered_emails = {email.lower() for email in registered_users}
    
    # Set registration status for each entry
    for entry in whitelist_entries:
        entry.is_registered = entry.email.lower() in registered_emails

    return render_template('admin/admin_manage_whitelist.html', 
                         title='Whitelist', 
                         whitelist=whitelist_entries, 
                         form=form)

@admin2_bp.route('/admin/whitelist/<int:whitelist_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_whitelist(whitelist_id):
    # Validate whitelist_id
    if whitelist_id <= 0:
        return jsonify({'success': False, 'message': 'Invalid whitelist ID'}), 400
    
    whitelist_entry = db.session.get(Whitelist, whitelist_id)
    if not whitelist_entry:
        abort(404)
    
    try:
        db.session.delete(whitelist_entry)
        log_system_event(f"Admin {current_user.name} deleted whitelist entry: {whitelist_entry.email}", event_type='audit', event_level='information')
        db.session.commit()
        return jsonify({'success': True, 'message': 'Entry deleted successfully'})
    except Exception as e:
        db.session.rollback()
        log_system_event(f"Error deleting whitelist entry {whitelist_id}: {str(e)}", event_type='error', event_level='error')
        return jsonify({'success': False, 'message': 'An error occurred while deleting the entry'}), 500
