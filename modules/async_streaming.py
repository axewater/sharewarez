"""
Async file streaming module for non-blocking file downloads.
Replaces the synchronous streaming system with async I/O using aiofiles.
"""

import os
import aiofiles
from werkzeug.utils import secure_filename
from modules.utils_logging import log_system_event


async def async_generate_file_chunks(file_path, chunk_size=2097152):
    """
    Async generator that yields file chunks for streaming downloads.
    
    Args:
        file_path (str): Absolute path to the file to stream
        chunk_size (int): Size of each chunk in bytes (default 2MB)
        
    Yields:
        bytes: File chunks of specified size
        
    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file cannot be read
        IOError: If other I/O errors occur during reading
    """
    
    try:
        file_size = os.path.getsize(file_path)
        log_system_event(f"Starting async file stream: {os.path.basename(file_path)} ({file_size:,} bytes, {chunk_size:,} byte chunks)", 
                        event_type='download', event_level='information')
        
        async with aiofiles.open(file_path, 'rb') as file:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                yield chunk
                
        log_system_event(f"Completed async file stream: {os.path.basename(file_path)}", 
                        event_type='download', event_level='information')
                        
    except FileNotFoundError:
        log_system_event(f"File not found for async streaming: {file_path[:100]}", 
                        event_type='download', event_level='error')
        raise
    except PermissionError:
        log_system_event(f"Permission denied for async streaming: {file_path[:100]}", 
                        event_type='download', event_level='error')
        raise
    except Exception as e:
        log_system_event(f"I/O error during async streaming: {str(e)}", 
                        event_type='download', event_level='error')
        raise


async def create_async_streaming_response(file_path, filename, chunk_size=2097152):
    """
    Create an async streaming response for file downloads.
    This function returns an async generator and headers for ASGI usage.
    
    Args:
        file_path (str): Absolute path to the file to stream
        filename (str): Filename to use for download (will be secured)
        chunk_size (int): Size of each chunk in bytes (default 2MB)
        
    Returns:
        tuple: (async_generator, headers_dict)
        
    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file cannot be read
        IOError: If other I/O errors occur
    """
    try:
        # Secure the filename to prevent directory traversal
        secure_name = secure_filename(filename)
        if not secure_name:
            secure_name = "download.zip"
            
        # Get file size for Content-Length header
        file_size = os.path.getsize(file_path)
        
        # Create headers for download
        headers = {
            'content-type': 'application/zip',
            'content-disposition': f'attachment; filename="{secure_name}"',
            'content-length': str(file_size),
            'cache-control': 'no-cache'
        }
        
        # Return the async generator and headers
        async_generator = async_generate_file_chunks(file_path, chunk_size)
        return async_generator, headers
        
    except Exception as e:
        log_system_event(f"Failed to create async streaming response: {str(e)}", 
                        event_type='download', event_level='error')
        raise


def get_download_info(file_path, filename):
    """
    Create a download info dict for Flask routes to return.
    This tells the ASGI handler to stream the file asynchronously.
    
    Args:
        file_path (str): Absolute path to the file to stream
        filename (str): Filename to use for download
        
    Returns:
        dict: Download info for ASGI handler
    """
    return {
        'async_download': True,
        'file_path': file_path,
        'filename': filename,
        'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
    }