import psutil
import os
from config import Config

def get_cpu_usage():
    """Get CPU usage percentage"""
    try:
        return psutil.cpu_percent(interval=1)
    except Exception as e:
        print(f"Error getting CPU usage: {e}")
        return None

def get_memory_usage():
    """Get memory usage statistics"""
    try:
        memory = psutil.virtual_memory()
        return {
            'total': memory.total,
            'available': memory.available,
            'used': memory.used,
            'percent': memory.percent
        }
    except Exception as e:
        print(f"Error getting memory usage: {e}")
        return None

def get_disk_usage():
    """Get disk usage for the application's base folder"""
    try:
        base_path = Config.BASE_FOLDER_WINDOWS if os.name == 'nt' else Config.BASE_FOLDER_POSIX
        if not os.path.exists(base_path):
            return None
        
        disk_usage = psutil.disk_usage(base_path)
        return {
            'total': disk_usage.total,
            'used': disk_usage.used,
            'free': disk_usage.free,
            'percent': disk_usage.percent
        }
    except Exception as e:
        print(f"Error getting disk usage: {e}")
        return None

def format_bytes(bytes_value):
    """Convert bytes to human readable format"""
    if bytes_value is None:
        return "N/A"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.2f} PB"
