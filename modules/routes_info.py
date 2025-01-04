from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from modules.utils_auth import admin_required
from modules.utils_processors import get_global_settings
from modules.utils_system_stats import format_bytes, get_cpu_usage, get_memory_usage, get_disk_usage, get_process_count, get_open_files, get_warez_folder_usage
from modules.utils_uptime import get_formatted_system_uptime, get_formatted_app_uptime
from modules import app_version, app_start_time
from config import Config
from modules.utils_igdb_api import make_igdb_api_request
from modules.models import GlobalSettings, SystemEvents, User
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


@info_bp.context_processor
def inject_current_theme():
    if current_user.is_authenticated and current_user.preferences:
        current_theme = current_user.preferences.theme or 'default'
    else:
        current_theme = 'default'
    return dict(current_theme=current_theme)

@info_bp.route('/admin/server_status_page')
@login_required
@admin_required
def admin_server_status():
    try:
        settings_record = GlobalSettings.query.first()
        if not settings_record or not settings_record.settings:
            flash('Server settings not configured.', 'warning')
            return redirect(url_for('site.admin_dashboard'))

        log_system_event("Admin accessed server status page", event_type='audit', event_level='information')
        
        # Get system resource statistics
        cpu_usage = get_cpu_usage()
        process_count = get_process_count()
        open_files = get_open_files()
        memory_usage = get_memory_usage()
        disk_usage = get_disk_usage()
        warez_usage = get_warez_folder_usage()
        
        if memory_usage:
            memory_usage['total_formatted'] = format_bytes(memory_usage['total'])
            memory_usage['used_formatted'] = format_bytes(memory_usage['used'])
            memory_usage['available_formatted'] = format_bytes(memory_usage['available'])
        
        if disk_usage:
            disk_usage['total_formatted'] = format_bytes(disk_usage['total'])
            disk_usage['used_formatted'] = format_bytes(disk_usage['used'])
            disk_usage['free_formatted'] = format_bytes(disk_usage['free'])
        
        if warez_usage:
            warez_usage['total_formatted'] = format_bytes(warez_usage['total'])
            warez_usage['used_formatted'] = format_bytes(warez_usage['used'])
            warez_usage['free_formatted'] = format_bytes(warez_usage['free'])
            
        # Get log statistics
        log_count = SystemEvents.query.count()
        latest_log = SystemEvents.query.order_by(SystemEvents.timestamp.desc()).first()
            
        enable_server_status = settings_record.settings.get('enableServerStatusFeature', False)
        if not enable_server_status:
            flash('Server Status feature is disabled.', 'warning')
            return redirect(url_for('site.admin_dashboard'))
            
    except Exception as e:
        flash(f'Error accessing server settings: {str(e)}', 'error')
        return redirect(url_for('site.admin_dashboard'))

    try:
        uptime = datetime.now() - app_start_time
    except Exception as e:
        uptime = 'Unavailable'
        print(f"Error calculating uptime: {e}")

    # Calculate active users (users who logged in within the last 24 hours)
    active_users = User.query.filter(
        User.lastlogin >= (datetime.utcnow() - timedelta(hours=24))
    ).count()
    
    # Define whitelist of configuration keys to display
    whitelist = {
        'BASE_FOLDER_WINDOWS',
        'BASE_FOLDER_POSIX',
        'DATA_FOLDER_WAREZ',
        'IMAGE_SAVE_PATH',
        'SQLALCHEMY_DATABASE_URI',
        'SQLALCHEMY_TRACK_MODIFICATIONS',
        'UPLOAD_FOLDER'
    }

    # Filter config values based on whitelist
    safe_config_values = {}
    for item in dir(Config):
        if not item.startswith("__") and item in whitelist:
            safe_config_values[item] = getattr(Config, item)
    
    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
    except Exception as e:
        hostname = 'Unavailable'
        ip_address = 'Unavailable'
        print(f"Error retrieving IP address: {e}")
    
    
    system_info = {
        'OS': platform.system(),
        'OS Version': platform.version(),
        'Python Version': platform.python_version(),
        'Hostname': hostname,
        'IP Address': ip_address,
        'Flask Port': request.environ.get('SERVER_PORT'),
        'System Uptime': get_formatted_system_uptime(),
        'Application Uptime': get_formatted_app_uptime(app_start_time),
        'Current Time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return render_template(
        'admin/admin_server_status.html', 
        config_values=safe_config_values, 
        system_info=system_info, 
        app_version=app_version,
        process_count=process_count,
        open_files=open_files,
        cpu_usage=cpu_usage,
        memory_usage=memory_usage,
        disk_usage=disk_usage,
        warez_usage=warez_usage,
        log_count=log_count,
        active_users=active_users,
        latest_log=latest_log
    )
