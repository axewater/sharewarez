"""Security utilities for path validation and other security functions."""

from pathlib import Path
from flask import current_app


def is_safe_path(user_path, allowed_bases):
    """Securely validate that a user-provided path is within allowed directories."""
    if not user_path or not isinstance(user_path, str):
        return False, "Invalid path format"
    
    # Strip and normalize the path
    user_path = user_path.strip()
    if not user_path:
        return False, "Empty path"
    
    # Basic input validation before path resolution (fixes CodeQL alert)
    # Check for null bytes which can be used for path traversal attacks
    if '\x00' in user_path:
        return False, "Invalid path format"
    
    # Check for extremely long paths that could cause DoS
    if len(user_path) > 4096:
        return False, "Path too long"
    
    try:
        # Use pathlib for safer path operations
        user_path_obj = Path(user_path).resolve(strict=False)
        
        # Check against each allowed base directory
        for base in allowed_bases:
            if not base:
                continue
            
            try:
                base_path_obj = Path(base).resolve(strict=False)
                
                # Check if user path is within the allowed base directory
                try:
                    user_path_obj.relative_to(base_path_obj)
                    return True, None
                except ValueError:
                    continue  # Path is not under this base, try next one
                    
            except (OSError, ValueError) as e:
                current_app.logger.warning(f"Invalid base path {sanitize_path_for_logging(base)}: {e}")
                continue
        
        return False, "Access denied - path outside allowed directories"
        
    except (OSError, ValueError) as e:
        current_app.logger.warning(f"Path validation error for {sanitize_path_for_logging(user_path)}: {e}")
        return False, "Invalid path format"


def get_allowed_base_directories(app):
    """Get allowed base directories from app configuration."""
    allowed_bases = []
    config_keys = ['BASE_FOLDER_WINDOWS', 'BASE_FOLDER_POSIX', 'DATA_FOLDER_WAREZ']
    for key in config_keys:
        base_path = app.config.get(key)
        if base_path:
            allowed_bases.append(base_path)
    return allowed_bases


def sanitize_path_for_logging(path, max_length=100):
    """Sanitize path for safe logging by truncating and masking sensitive parts."""
    if not path or not isinstance(path, str):
        return "[INVALID_PATH]"
    
    # Truncate very long paths
    if len(path) > max_length:
        # Keep first 30 chars, middle truncation indicator, and last 30 chars
        truncated = f"{path[:30]}...{path[-(max_length-33):]}"
    else:
        truncated = path
    
    # Replace potentially sensitive directory names with placeholders
    import re
    # Mask common sensitive patterns
    sanitized = re.sub(r'[Uu]sers?/[^/]+', 'Users/[USER]', truncated)
    sanitized = re.sub(r'[Hh]ome/[^/]+', 'home/[USER]', sanitized)
    sanitized = re.sub(r'\\\\[Uu]sers\\\\[^\\\\]+', r'\\Users\\[USER]', sanitized)
    
    return sanitized