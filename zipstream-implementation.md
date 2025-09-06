# Comprehensive Implementation Plan: Integrating zipstream-new into SharewareZ

## Overview
Replace the current synchronous zipfile-based ZIP creation with zipstream-new for streaming ZIP generation, focusing ONLY on multi-file games while preserving direct download functionality for single-file games.

### 1.1 Dependencies and Requirements
- **Add zipstream-new to requirements.txt**
  - Add `zipstream-new` to the dependencies list
  - Ensure compatibility with existing async infrastructure

### 1.2 Configuration Updates
- **Add zipstream configuration parameters to config.py.example**
  - `ZIPSTREAM_CHUNK_SIZE` (default: 65536 bytes for memory efficiency)
  - `ZIPSTREAM_COMPRESSION_LEVEL` (default: 0 for ZIP_STORED compatibility)
  - `ZIPSTREAM_ENABLE_ZIP64` (default: True for large game support)


### 2.1 New Streaming Module (`modules/utils_zipstream.py`)
- **Create async ZIP streaming generator**
  - `async_generate_zipstream_chunks()`: Core streaming function
  - Memory-efficient chunk processing (64KB chunks)
  - Support for folder exclusions (updates/extras directories)
  - Comprehensive error handling and logging

- **Integration functions**
  - `should_use_zipstream()`: Decision logic for when to use streaming vs direct download
  - `get_zipstream_info()`: Generate streaming metadata for ASGI handler
  - `estimate_zip_size()`: Calculate approximate final ZIP size

### 2.2 Enhanced Async Streaming Module
- **Extend `modules/async_streaming.py`**
  - Add `async_generate_zipstream_response()` function
  - Support for both file streaming and ZIP streaming
  - Unified interface for ASGI handler

### 3.1 Utils Download Module Updates (`modules/utils_download.py`)
- **Replace `zip_game()` function**
  - Preserve single-file direct download logic (lines 42-46)
  - Replace ZIP creation with streaming preparation for multi-file games
  - Update status to 'streaming_ready' instead of 'available' for streamed ZIPs
  - Maintain all security validations and path checking

- **Replace `zip_folder()` function**  
  - Similar streaming preparation for update/extra file downloads
  - Preserve direct file download for single files
  - Update database records appropriately

- **Add new helper functions**
  - `prepare_streaming_download()`: Set up streaming metadata
  - `is_streaming_download()`: Check if download uses streaming
  - Maintain backward compatibility with existing `update_download_request()`

### 3.2 Database Schema Considerations
- **No schema changes required**
- **Status field usage**:
  - 'streaming_ready': ZIP will be streamed on-demand
  - 'available': Direct file download (existing behavior)
  - Maintain existing status values for backward compatibility

### 4.1 ASGI Handler Updates (`asgi.py`)
- **Extend `_handle_zip_download()` method**
  - Check download request status ('streaming_ready' vs 'available')
  - Route to appropriate streaming method
  - Maintain existing security validations

- **Add streaming response handling**
  - Integrate zipstream-new generator with existing async infrastructure
  - Memory-efficient chunk processing
  - Proper HTTP headers for streamed content
  - Error handling and recovery

### 4.2 Headers and Response Management
- **Dynamic Content-Length handling**
  - Omit Content-Length for streamed ZIPs (unknown size)
  - Use Transfer-Encoding: chunked
  - Maintain Content-Length for direct file downloads

### 5.1 Chunk Size Management
- **Small memory footprint**: 64KB chunks for ZIP generation
- **Configurable chunk sizes** based on system resources


### 5.2 Resource Management
- **Async context managers** for file handles
- **Proper cleanup** of temporary resources
- **Connection timeout handling** for long-running streams
- **Graceful error recovery** without memory leaks

### Configuration Documentation
- **Update config.py.example with new settings**
- **Document memory optimization recommendations**