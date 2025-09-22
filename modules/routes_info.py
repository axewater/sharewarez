from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from modules.utils_auth import admin_required
from modules.utils_processors import get_global_settings
from modules.utils_system_stats import format_bytes, get_cpu_usage, get_memory_usage, get_disk_usage, get_process_count, get_open_files, get_warez_folder_usage
from modules.utils_uptime import get_formatted_system_uptime, get_formatted_app_uptime
from modules.utils_status import get_system_info, get_config_values, get_active_users, get_log_info, check_server_settings, get_database_info
from modules import app_version, app_start_time
from modules import db, cache
from datetime import datetime, timedelta
from sqlalchemy import func
from modules.utils_logging import log_system_event
import platform, socket

info_bp = Blueprint('info', __name__)

@info_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()


@info_bp.route('/admin/server_status_page')
@login_required
@admin_required
def admin_server_status():
    # Check server settings
    settings_valid, error_message = check_server_settings()
    if not settings_valid:
        flash(error_message, 'warning')
        return redirect(url_for('site.admin_dashboard'))

    try:
        # Get all required statistics
        cpu_usage = get_cpu_usage()
        process_count = get_process_count()
        open_files = get_open_files()
        memory_usage = get_memory_usage()
        disk_usage = get_disk_usage()
        warez_usage = get_warez_folder_usage()
        system_info = get_system_info()
        config_values = get_config_values()
        active_users = get_active_users()
        log_info = get_log_info()
        database_info = get_database_info()
        
        # Format usage statistics
        for usage in [memory_usage, disk_usage, warez_usage]:
            if usage:
                for key in ['total', 'used', 'available', 'free']:
                    if key in usage:
                        usage[f'{key}_formatted'] = format_bytes(usage[key])

        # Add uptime information to system_info
        system_info['System Uptime'] = get_formatted_system_uptime()
        system_info['Application Uptime'] = get_formatted_app_uptime(app_start_time)

        # Log the access
        log_system_event("Admin accessed server status page", event_type='audit', event_level='information')

    except Exception as e:
        flash(f'Error accessing server settings: {str(e)}', 'error')
        return redirect(url_for('site.admin_dashboard'))

    return render_template(
        'admin/admin_server_status.html',
        config_values=config_values,
        system_info=system_info,
        app_version=app_version,
        process_count=process_count,
        open_files=open_files,
        cpu_usage=cpu_usage,
        memory_usage=memory_usage,
        disk_usage=disk_usage,
        warez_usage=warez_usage,
        log_count=log_info['count'],
        active_users=active_users,
        latest_log=log_info['latest'],
        database_info=database_info
    )


@info_bp.route('/admin/new_server_info')
@login_required
@admin_required
def new_server_info():
    """New server info page - same functionality as original but for new settings section."""
    # Check server settings
    settings_valid, error_message = check_server_settings()
    if not settings_valid:
        flash(error_message, 'warning')
        return redirect(url_for('site.admin_dashboard'))

    try:
        # Get all required statistics
        cpu_usage = get_cpu_usage()
        process_count = get_process_count()
        open_files = get_open_files()
        memory_usage = get_memory_usage()
        disk_usage = get_disk_usage()
        warez_usage = get_warez_folder_usage()

        # Get system and configuration info
        system_info = get_system_info()
        config_values = get_config_values()
        active_users = get_active_users()
        log_info = get_log_info()
        database_info = get_database_info()

        log_system_event("Admin accessed new server info page", event_type='audit', event_level='information')

    except Exception as e:
        flash(f'Error accessing server settings: {str(e)}', 'error')
        return redirect(url_for('site.admin_dashboard'))

    return render_template(
        'admin/new_server_info.html',
        config_values=config_values,
        system_info=system_info,
        app_version=app_version,
        process_count=process_count,
        open_files=open_files,
        cpu_usage=cpu_usage,
        memory_usage=memory_usage,
        disk_usage=disk_usage,
        warez_usage=warez_usage,
        log_count=log_info['count'],
        active_users=active_users,
        latest_log=log_info['latest'],
        database_info=database_info
    )
