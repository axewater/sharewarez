import psutil
import platform
import socket
from datetime import datetime, timedelta
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
        'BASE_FOLDER_WINDOWS',
        'BASE_FOLDER_POSIX',
        'DATA_FOLDER_WAREZ',
        'IMAGE_SAVE_PATH',
        'SQLALCHEMY_DATABASE_URI',
        'SQLALCHEMY_TRACK_MODIFICATIONS',
        'UPLOAD_FOLDER'
    }

    safe_config_values = {}
    for item in dir(Config):
        if not item.startswith("__") and item in whitelist:
            safe_config_values[item] = getattr(Config, item)
    
    return safe_config_values

def get_active_users():
    """Get count of users active in the last 24 hours."""
    return User.query.filter(
        User.lastlogin >= (datetime.utcnow() - timedelta(hours=24))
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
