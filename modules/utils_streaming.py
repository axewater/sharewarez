import os
from flask import Response, current_app, stream_with_context
from werkzeug.utils import secure_filename
from modules.utils_logging import log_system_event


def generate_file_chunks(file_path, chunk_size=2097152):
    """
    Generator that yields file chunks for streaming downloads.
    
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
        log_system_event(f"Starting file stream: {os.path.basename(file_path)} ({file_size:,} bytes, {chunk_size:,} byte chunks)", 
                        event_type='download', event_level='information')
        
        with open(file_path, 'rb') as file:
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                yield chunk
                
        log_system_event(f"Completed file stream: {os.path.basename(file_path)}", 
                        event_type='download', event_level='information')
                        
    except FileNotFoundError:
        log_system_event(f"File not found for streaming: {file_path[:100]}", 
                        event_type='download', event_level='error')
        raise
    except PermissionError:
        log_system_event(f"Permission denied for streaming: {file_path[:100]}", 
                        event_type='download', event_level='error')
        raise
    except Exception as e:
        log_system_event(f"I/O error during streaming: {str(e)}", 
                        event_type='download', event_level='error')
        raise


def create_streaming_response(file_path, filename):
    """
    Create a Flask Response object for streaming file downloads.
    
    Args:
        file_path (str): Absolute path to the file to stream
        filename (str): Filename to use for download (will be secured)
        
    Returns:
        Response: Flask response object with streaming content
        
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
            
        # Get file size for Content-Length header and chunk size from config
        file_size = os.path.getsize(file_path)
        chunk_size = current_app.config.get('STREAMING_CHUNK_SIZE', 2097152)  # 2MB default
        
        # Create streaming response with context preservation
        response = Response(
            stream_with_context(generate_file_chunks(file_path, chunk_size)),
            mimetype='application/zip',
            direct_passthrough=True
        )
        
        # Set download headers
        response.headers['Content-Disposition'] = f'attachment; filename="{secure_name}"'
        response.headers['Content-Length'] = str(file_size)
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Cache-Control'] = 'no-cache'
        
        return response
        
    except Exception as e:
        log_system_event(f"Failed to create streaming response: {str(e)}", 
                        event_type='download', event_level='error')
        raise