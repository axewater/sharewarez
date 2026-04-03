import re
import os
from typing import Optional

def sanitize_filename(filename: str, max_length: Optional[int] = 200) -> str:
    """
    Sanitize a filename by removing/replacing invalid characters and enforcing length limits.
    
    Args:
        filename: The original filename to sanitize
        max_length: Maximum length for the filename (default 200)
        
    Returns:
        A sanitized filename safe for all major operating systems
    """
    # Remove or replace invalid characters
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    
    # Remove any non-alphanumeric characters except ._-
    filename = re.sub(r'[^\w\-_.]', '', filename)
    
    # Remove Windows reserved characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # Ensure it doesn't start with a dot
    filename = filename.lstrip('.')
    
    # Remove any duplicate underscores or dots
    filename = re.sub(r'_{2,}', '_', filename)
    filename = re.sub(r'\.{2,}', '.', filename)
    
    # Truncate if too long, preserving extension
    if max_length and len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        ext_length = len(ext)
        name = name[:(max_length - ext_length)]
        filename = name + ext
    
    # If filename is empty after sanitization, provide a default
    if not filename:
        filename = "unnamed_file"
    
    return filename
