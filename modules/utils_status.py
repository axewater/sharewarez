import psutil
import platform
import socket
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from modules.models import User, SystemEvents, GlobalSettings
from modules.utils_system_stats import format_bytes
from modules import app_start_time
from config import Config

def get_system_info():
    """Get basic system information."""
    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
    except Exception as e:
        hostname = 'Unavailable'
        ip_address = 'Unavailable'
        print(f"Error retrieving IP address: {e}")
    
    return {
        'Operating System': platform.system(),
        'Operating System Version': platform.version(),
        'Python Version': platform.python_version(),
        'Hostname': hostname,
        'IP Address': ip_address,
        'Current Time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def get_config_values():
    """Get safe configuration values."""
    whitelist = {
        'BASE_FOLDER_WINDOWS': None,
        'BASE_FOLDER_POSIX': None,
        'DATA_FOLDER_WAREZ': None,
        'IMAGE_SAVE_PATH': None,
        'UPLOAD_FOLDER': None
    }

    safe_config_values = {}
    for item, _ in whitelist.items():
        if hasattr(Config, item):
            path = getattr(Config, item)
            if path:
                safe_config_values[item] = {
                    'path': path,
                    'read': os.access(path, os.R_OK) if os.path.exists(path) else False,
                    'write': os.access(path, os.W_OK) if os.path.exists(path) else False,
                    'exists': os.path.exists(path)
                }
    
    return safe_config_values

def get_active_users():
    """Get count of users active in the last 24 hours."""
    return User.query.filter(
        User.lastlogin >= (datetime.now(timezone.utc) - timedelta(hours=24))
    ).count()

def get_log_info():
    """Get log statistics."""
    return {
        'count': SystemEvents.query.count(),
        'latest': SystemEvents.query.order_by(SystemEvents.timestamp.desc()).first()
    }

def check_server_settings():
    """Check if server settings are properly configured."""
    settings_record = GlobalSettings.query.first()
    if not settings_record or not settings_record.settings:
        return False, "Server settings not configured."
    
    enable_server_status = settings_record.settings.get('enableServerStatusFeature', False)
    if not enable_server_status:
        return False, "Server Status feature is disabled."
    
    return True, None
