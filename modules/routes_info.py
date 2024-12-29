from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from modules.utils_auth import admin_required
from modules.utils_uptime import get_formatted_system_uptime, get_formatted_app_uptime
from modules.utils_processors import get_global_settings
from modules.models import GlobalSettings
from datetime import datetime
import socket, platform
from modules import app_start_time, app_version, cache
from config import Config

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

        from modules.utils_system_stats import get_cpu_usage, get_memory_usage, get_disk_usage, format_bytes
        
        # Get system resource statistics
        cpu_usage = get_cpu_usage()
        memory_usage = get_memory_usage()
        disk_usage = get_disk_usage()
        
        # Format memory and disk usage for display
        if memory_usage:
            memory_usage['total_formatted'] = format_bytes(memory_usage['total'])
            memory_usage['used_formatted'] = format_bytes(memory_usage['used'])
            memory_usage['available_formatted'] = format_bytes(memory_usage['available'])
        
        if disk_usage:
            disk_usage['total_formatted'] = format_bytes(disk_usage['total'])
            disk_usage['used_formatted'] = format_bytes(disk_usage['used'])
            disk_usage['free_formatted'] = format_bytes(disk_usage['free'])
            
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
        cpu_usage=cpu_usage,
        memory_usage=memory_usage,
        disk_usage=disk_usage
    )