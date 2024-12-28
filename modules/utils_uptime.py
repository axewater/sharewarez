import platform
import time
from datetime import datetime

def get_system_uptime():
    """Get system uptime in a cross-platform way"""
    try:
        if platform.system() == 'Windows':
            # Windows uptime calculation using GetTickCount64
            from ctypes import windll
            return windll.kernel32.GetTickCount64() / 1000.0
        else:
            # Unix-like systems uptime calculation using /proc/uptime
            with open('/proc/uptime', 'r') as f:
                return float(f.readline().split()[0])
    except Exception as e:
        print(f"Error getting system uptime: {e}")
        return None

def format_uptime(seconds):
    """Convert seconds into human readable uptime string"""
    if seconds is None:
        return "Unavailable"
    
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days} {'day' if days == 1 else 'days'}")
    if hours > 0:
        parts.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
    if minutes > 0:
        parts.append(f"{minutes} {'minute' if minutes == 1 else 'minutes'}")
    
    return ", ".join(parts) if parts else "Less than 1 minute"

def get_formatted_system_uptime():
    """Get system uptime in human readable format"""
    uptime_seconds = get_system_uptime()
    return format_uptime(uptime_seconds)

def get_formatted_app_uptime(app_start_time):
    """Get application uptime in human readable format"""
    if not isinstance(app_start_time, datetime):
        return "Unavailable"
    
    uptime_seconds = (datetime.now() - app_start_time).total_seconds()
    return format_uptime(uptime_seconds)
