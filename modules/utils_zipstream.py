"""
Zipstream integration module for streaming ZIP file generation.
Provides memory-efficient streaming ZIP creation for multi-file games.
"""

import os
import asyncio
from typing import AsyncGenerator, Tuple, Optional, Dict, Any
import zipstream
from modules.utils_security import is_safe_path
from modules.utils_logging import log_system_event


async def async_generate_zipstream_chunks(
    source_path: str, 
    chunk_size: int = 65536,
    compression_level: int = 0,
    enable_zip64: bool = True,
    excluded_folders: Optional[list] = None
) -> AsyncGenerator[bytes, None]:
    """
    Async generator that creates ZIP chunks using zipstream-new for memory-efficient streaming.
    
    Args:
        source_path: Path to the source file or directory to compress
        chunk_size: Size of each chunk in bytes (default 64KB)
        compression_level: ZIP compression level (0=stored, 9=maximum)
        enable_zip64: Enable ZIP64 extensions for large files
        excluded_folders: List of folder names to exclude (e.g., ['updates', 'extras'])
        
    Yields:
        bytes: ZIP file chunks
        
    Raises:
        FileNotFoundError: If source path doesn't exist
        PermissionError: If source path cannot be read
        IOError: If other I/O errors occur during processing
    """
    
    if excluded_folders is None:
        excluded_folders = ['updates', 'extras']
    
    try:
        # Verify source path exists
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source path does not exist: {source_path}")
        
        # Initialize zipstream with proper API and ZIP64 support
        from zipfile import ZIP_STORED, ZIP_DEFLATED
        compression_method = ZIP_DEFLATED if compression_level > 0 else ZIP_STORED
        zs = zipstream.ZipFile(mode='w', compression=compression_method, allowZip64=enable_zip64)
        
        # Add files to ZIP stream
        if os.path.isfile(source_path):
            # Single file
            file_name = os.path.basename(source_path)
            zs.write(source_path, arcname=file_name)
        else:
            # Directory - walk and add files while excluding certain folders
            for root, dirs, files in os.walk(source_path):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d.lower() not in [f.lower() for f in excluded_folders]]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    # Create relative path for archive
                    rel_path = os.path.relpath(file_path, source_path)
                    zs.write(file_path, arcname=rel_path)
        
        # Generate chunks asynchronously
        for chunk in zs:
            if chunk:
                yield chunk
                # Allow other coroutines to run
                await asyncio.sleep(0)
                
    except Exception as e:
        log_system_event(f"Error in zipstream generation for {source_path}: {str(e)}")
        raise


def should_use_zipstream(source_path: str) -> bool:
    """
    Determine if zipstream should be used for the given source path.
    
    Args:
        source_path: Path to check
        
    Returns:
        bool: True if zipstream should be used, False for direct download
    """
    
    if not os.path.exists(source_path):
        return False
    
    # Use direct download for single files
    if os.path.isfile(source_path):
        return False
    
    # Use zipstream for directories (multi-file games)
    if os.path.isdir(source_path):
        return True
    
    return False


def get_zipstream_info(source_path: str, download_filename: str) -> Dict[str, Any]:
    """
    Generate metadata for zipstream downloads.
    
    Args:
        source_path: Path to the source files
        download_filename: Desired filename for the download
        
    Returns:
        dict: Metadata dictionary for the streaming download
    """
    
    return {
        'source_path': source_path,
        'download_filename': download_filename,
        'content_type': 'application/zip',
        'streaming': True,
        'estimated_size': estimate_zip_size(source_path)
    }


def estimate_zip_size(source_path: str) -> Optional[int]:
    """
    Estimate the final ZIP file size based on source content.
    This is a rough estimation for progress indicators.
    
    Args:
        source_path: Path to calculate size for
        
    Returns:
        int: Estimated size in bytes, or None if cannot estimate
    """
    
    try:
        if os.path.isfile(source_path):
            # For single files, ZIP overhead is minimal
            return int(os.path.getsize(source_path) * 1.05)  # 5% overhead estimate
        
        elif os.path.isdir(source_path):
            total_size = 0
            file_count = 0
            
            for root, dirs, files in os.walk(source_path):
                # Skip excluded folders
                dirs[:] = [d for d in dirs if d.lower() not in ['updates', 'extras']]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                        file_count += 1
                    except (OSError, IOError):
                        # Skip files we can't read
                        continue
            
            if file_count == 0:
                return None
            
            # Estimate ZIP overhead based on file count and directory structure
            # Stored compression (level 0) adds minimal overhead
            overhead = file_count * 100  # ~100 bytes per file for headers
            return total_size + overhead
    
    except Exception as e:
        log_system_event(f"Error estimating ZIP size for {source_path}: {str(e)}")
        return None


async def validate_zipstream_path(source_path: str, allowed_bases: list) -> Tuple[bool, str]:
    """
    Validate that the source path is safe for zipstream processing.
    
    Args:
        source_path: Path to validate
        allowed_bases: List of allowed base directories
        
    Returns:
        tuple: (is_valid, error_message)
    """
    
    try:
        # Use existing security validation
        is_safe, error_message = is_safe_path(source_path, allowed_bases)
        if not is_safe:
            return False, error_message
        
        # Additional checks for zipstream
        if not os.path.exists(source_path):
            return False, "Source path does not exist"
        
        # Check if we have read permissions
        if not os.access(source_path, os.R_OK):
            return False, "Insufficient permissions to read source path"
        
        return True, ""
        
    except Exception as e:
        return False, f"Path validation error: {str(e)}"


def is_streaming_download(download_info: dict) -> bool:
    """
    Check if a download uses streaming based on its metadata.
    
    Args:
        download_info: Download metadata dictionary
        
    Returns:
        bool: True if this is a streaming download
    """
    
    return download_info.get('streaming', False)