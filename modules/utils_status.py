import psutil
import platform
import socket
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from modules.models import User, SystemEvents, GlobalSettings
from modules import db
from modules.utils_system_stats import format_bytes
from modules import app_start_time
from config import Config
from urllib.parse import urlparse

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
    return db.session.execute(select(func.count(User.id)).filter(
        User.lastlogin >= (datetime.now(timezone.utc) - timedelta(hours=24))
    )).scalar()

def get_log_info():
    """Get log statistics."""
    return {
        'count': db.session.execute(select(func.count(SystemEvents.id))).scalar(),
        'latest': db.session.execute(select(SystemEvents).order_by(SystemEvents.timestamp.desc())).scalars().first()
    }

def get_database_info():
    """Get database connection information."""
    try:
        # Get the current database URI
        db_uri = db.engine.url
        
        # Parse the database URI to extract components
        parsed = urlparse(str(db_uri))
        
        # Extract database name from path (remove leading slash)
        db_name = parsed.path.lstrip('/')
        
        # Get database host and port
        host = parsed.hostname or 'localhost'
        port = parsed.port or 5432
        
        # Get database engine type
        engine_type = db_uri.drivername
        
        return {
            'database_name': db_name,
            'host': host,
            'port': port,
            'engine': engine_type,
            'connection_info': f"{engine_type}://{host}:{port}/{db_name}"
        }
    except Exception as e:
        return {
            'database_name': 'Error retrieving database info',
            'host': 'Unknown',
            'port': 'Unknown', 
            'engine': 'Unknown',
            'connection_info': f'Error: {str(e)}'
        }

def check_server_settings():
    """Check if server settings are properly configured."""
    settings_record = db.session.execute(select(GlobalSettings)).scalars().first()
    if not settings_record or not settings_record.settings:
        return False, "Server settings not configured."
    
    enable_server_status = settings_record.settings.get('enableServerStatusFeature', False)
    if not enable_server_status:
        return False, "Server Status feature is disabled."
    
    return True, None
