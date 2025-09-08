"""
Async file streaming module for non-blocking file downloads.
Replaces the synchronous streaming system with async I/O using aiofiles.
"""

import os
import mimetypes
import aiofiles
from werkzeug.utils import secure_filename
from modules.utils_logging import log_system_event
from modules.utils_zipstream import async_generate_zipstream_chunks


def get_content_type_for_file(file_path, filename):
    """
    Determine the appropriate content-type for a file based on its extension.
    
    Args:
        file_path (str): Path to the file
        filename (str): Name of the file
        
    Returns:
        str: MIME type string
    """
    # ROM file extension mappings for common emulator formats
    rom_mime_types = {
        # Nintendo formats
        '.nes': 'application/octet-stream',
        '.nez': 'application/octet-stream', 
        '.smc': 'application/octet-stream',
        '.sfc': 'application/octet-stream',
        '.n64': 'application/octet-stream',
        '.z64': 'application/octet-stream',
        '.v64': 'application/octet-stream',
        '.gb': 'application/octet-stream',
        '.gbc': 'application/octet-stream',
        '.gba': 'application/octet-stream',
        '.nds': 'application/octet-stream',
        '.3ds': 'application/octet-stream',
        
        # Sega formats  
        '.smd': 'application/octet-stream',
        '.gen': 'application/octet-stream',
        '.32x': 'application/octet-stream',
        '.sms': 'application/octet-stream',
        '.gg': 'application/octet-stream',
        '.sg': 'application/octet-stream',
        '.bin': 'application/octet-stream',
        '.cue': 'text/plain',
        '.iso': 'application/octet-stream',
        
        # PlayStation formats
        '.psx': 'application/octet-stream',
        '.pbp': 'application/octet-stream',
        '.chd': 'application/octet-stream',
        
        # Atari formats
        '.a26': 'application/octet-stream',
        '.a52': 'application/octet-stream', 
        '.a78': 'application/octet-stream',
        '.lnx': 'application/octet-stream',
        '.j64': 'application/octet-stream',
        
        # Other formats
        '.rom': 'application/octet-stream',
        '.ws': 'application/octet-stream',
        '.wsc': 'application/octet-stream',
        '.col': 'application/octet-stream',
        '.vec': 'application/octet-stream',
        
        # Archive formats
        '.zip': 'application/zip',
        '.7z': 'application/x-7z-compressed',
        '.rar': 'application/vnd.rar',
    }
    
    # Get file extension
    _, ext = os.path.splitext(filename.lower())
    
    # Check ROM-specific mappings first
    if ext in rom_mime_types:
        return rom_mime_types[ext]
    
    # Fall back to system MIME type detection
    mime_type, _ = mimetypes.guess_type(filename)
    
    # Default to binary stream if we can't determine the type
    return mime_type if mime_type else 'application/octet-stream'


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
        
        # Determine correct content-type based on file extension
        content_type = get_content_type_for_file(file_path, filename)
        
        # Create headers for download
        headers = {
            'content-type': content_type,
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


def async_generate_zipstream_response(source_path, filename, chunk_size=65536, 
                                      compression_level=0, enable_zip64=True):
    """
    Create an async streaming response for ZIP downloads using zipstream-new.
    This function returns an async generator and headers for ASGI usage.
    
    Args:
        source_path (str): Absolute path to the source file or directory to ZIP
        filename (str): Filename to use for download (will be secured)
        chunk_size (int): Size of each chunk in bytes (default 64KB)
        compression_level (int): ZIP compression level (0=stored, 9=maximum)
        enable_zip64 (bool): Enable ZIP64 extensions for large files
        
    Returns:
        tuple: (async_generator, headers_dict)
        
    Raises:
        FileNotFoundError: If source path doesn't exist
        PermissionError: If source path cannot be read
        IOError: If other I/O errors occur
    """
    try:
        # Secure the filename to prevent directory traversal
        secure_name = secure_filename(filename)
        if not secure_name:
            secure_name = "download.zip"
        
        print(f"Starting async zipstream: {os.path.basename(source_path)} -> {secure_name}")
        
        # Create headers for download (no Content-Length for streaming)
        headers = {
            'content-type': 'application/zip',
            'content-disposition': f'attachment; filename="{secure_name}"',
            'transfer-encoding': 'chunked',
            'cache-control': 'no-cache'
        }
        
        # Return the async generator and headers
        async_generator = async_generate_zipstream_chunks(
            source_path, 
            chunk_size=chunk_size,
            compression_level=compression_level,
            enable_zip64=enable_zip64
        )
        return async_generator, headers
        
    except Exception as e:
        print(f"Failed to create async zipstream response: {str(e)}")
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


def get_zipstream_download_info(source_path, filename):
    """
    Create a download info dict for zipstream downloads.
    This tells the ASGI handler to create a ZIP stream asynchronously.
    
    Args:
        source_path (str): Absolute path to the source file or directory to ZIP
        filename (str): Filename to use for download
        
    Returns:
        dict: Download info for ASGI handler
    """
    return {
        'async_zipstream': True,
        'source_path': source_path,
        'filename': filename,
        'streaming': True
    }