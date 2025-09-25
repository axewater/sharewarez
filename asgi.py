"""
ASGI config for SharewareZ production deployment.
This file wraps the Flask app to be compatible with ASGI servers like uvicorn
and provides async file streaming for downloads.
"""

import sys
import os
import re
import json
import uuid
from urllib.parse import unquote
from asgiref.wsgi import WsgiToAsgi

from modules import create_app, db
from modules.models import User, DownloadRequest, Game
from modules.async_streaming import create_async_streaming_response, async_generate_zipstream_response
from modules.utils_security import is_safe_path, get_allowed_base_directories
from modules.utils_logging import log_system_event
from sqlalchemy import select


# Proper ASGI application with lifespan protocol support
class LazyASGIApp:
    def __init__(self):
        self._app = None
        self._flask_app = None
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            # Handle ASGI lifespan protocol
            await self._handle_lifespan(receive, send)
        elif scope["type"] == "http":
            # Handle HTTP requests - check for download routes first
            path = scope["path"]
            
            # Check if this is a download route
            if (path.startswith('/download_zip/') or 
                path.startswith('/api/downloadrom/')):
                await self._handle_download(scope, receive, send)
                return
            
            # For all other routes, use Flask
            if self._app is None:
                # Create Flask app only on first HTTP request, not during module import
                # Database initialization is handled by InitializationManager before workers start
                self._flask_app = create_app()

                # Wrap with ASGI adapter
                self._app = WsgiToAsgi(self._flask_app)
            
            await self._app(scope, receive, send)
    
    async def _handle_download(self, scope, receive, send):
        """Handle download routes with async file streaming"""
        path = scope["path"]
        method = scope["method"]
        
        # Only handle GET requests
        if method != "GET":
            await self._send_error(send, 405, "Method Not Allowed")
            return
        
        try:
            # Initialize Flask app if needed for database access
            if self._flask_app is None:
                # Database initialization is handled by InitializationManager
                self._flask_app = create_app()
            
            # Handle different download types
            if path.startswith('/download_zip/'):
                await self._handle_zip_download(scope, receive, send, path)
            elif path.startswith('/api/downloadrom/'):
                await self._handle_rom_download(scope, receive, send, path)
                
        except Exception as e:
            # Use print instead of log_system_event to avoid context issues
            print(f"Error in async download handler: {str(e)}")
            
            # Try to send error response, but handle case where response already started
            try:
                await self._send_error(send, 500, "Internal Server Error")
            except Exception as error_e:
                print(f"Could not send error response (response may have already started): {str(error_e)}")
                # Try to close connection gracefully
                try:
                    await send({
                        "type": "http.response.body",
                        "body": b"",
                        "more_body": False
                    })
                except Exception:
                    # Connection handling failed, nothing more we can do
                    pass
    
    async def _handle_zip_download(self, scope, receive, send, path):
        """Handle ZIP file downloads"""
        # Extract download_id from path
        download_id_match = re.match(r'/download_zip/(\d+)', path)
        if not download_id_match:
            await self._send_error(send, 400, "Invalid download ID")
            return
        
        download_id = int(download_id_match.group(1))
        
        # Get user from session
        user_id = await self._get_user_from_session(scope)
        if not user_id:
            await self._send_error(send, 401, "Unauthorized")
            return
        
        with self._flask_app.app_context():
            # Get download request
            download_request = db.session.execute(
                select(DownloadRequest).filter_by(id=download_id, user_id=user_id)
            ).scalars().first()
            
            if not download_request:
                await self._send_error(send, 404, "Download not found")
                return
            
            if download_request.status != 'available':
                await self._send_error(send, 400, "Download not ready")
                return
            
            file_path = download_request.zip_file_path
            
            # Check if this is a streaming download (source path is a directory)
            if os.path.isdir(file_path):
                await self._handle_streaming_download(send, download_request, file_path)
                return
            
            # Security validation for direct game files
            allowed_bases = get_allowed_base_directories(self._flask_app)
            if not allowed_bases:
                await self._send_error(send, 500, "Server configuration error")
                return

            is_safe, error_message = is_safe_path(file_path, allowed_bases)
            if not is_safe:
                log_system_event(f"Security violation - game file outside allowed directories: {file_path[:100]}",
                               event_type='security', event_level='warning')
                await self._send_error(send, 403, "Access denied")
                return
            
            if not os.path.exists(file_path):
                await self._send_error(send, 404, "File not found")
                return
            
            # Stream the file
            filename = os.path.basename(file_path)
            log_system_event(f"Async file download: {filename}", event_type='download', event_level='information')
            await self._stream_file(send, file_path, filename)
    
    async def _handle_rom_download(self, scope, receive, send, path):
        """Handle ROM file downloads for emulator"""
        # Extract game UUID from path
        rom_match = re.match(r'/api/downloadrom/([a-f0-9-]+)', path)
        if not rom_match:
            await self._send_error(send, 400, "Invalid game UUID")
            return
        
        game_uuid = rom_match.group(1)
        
        # Validate UUID format
        try:
            uuid.UUID(game_uuid)
        except ValueError:
            log_system_event(f"Invalid UUID format attempted for ROM download: {game_uuid}", 
                           event_type='security', event_level='warning')
            await self._send_error(send, 400, "Invalid game identifier")
            return
        
        # Get user from session
        user_id = await self._get_user_from_session(scope)
        if not user_id:
            await self._send_error(send, 401, "Unauthorized")
            return
        
        with self._flask_app.app_context():
            # Get game
            game = db.session.execute(select(Game).filter_by(uuid=game_uuid)).scalars().first()
            
            if not game:
                log_system_event(f"ROM download attempt for non-existent game UUID: {game_uuid}", 
                               event_type='security', event_level='warning')
                await self._send_error(send, 404, "Game not found")
                return
            
            # Check if file exists
            if not os.path.exists(game.full_disk_path):
                log_system_event(f"ROM download attempt for missing file: {game.name} at {game.full_disk_path}", 
                               event_type='security', event_level='warning')
                await self._send_error(send, 404, "ROM file not found on disk")
                return
            
            # Validate path is within allowed directories
            allowed_bases = get_allowed_base_directories(self._flask_app)
            is_safe, error_message = is_safe_path(game.full_disk_path, allowed_bases)
            
            if not is_safe:
                log_system_event(f"Path traversal attempt blocked for ROM download: {game.full_disk_path} - {error_message}", 
                               event_type='security', event_level='warning')
                await self._send_error(send, 403, "Access denied")
                return
            
            # Check if it's a folder (not supported by WebRetro)
            if os.path.isdir(game.full_disk_path):
                await self._send_error(send, 400, "This game is a folder and cannot be played directly")
                return
            
            # Stream the file
            filename = os.path.basename(game.full_disk_path)
            log_system_event(f"ROM file downloaded for WebRetro: {game.name}", 
                           event_type='download', event_level='information')
            await self._stream_file(send, game.full_disk_path, filename)
    
    async def _get_user_from_session(self, scope):
        """Extract user ID from Flask session cookie"""
        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode("utf-8")
        
        if not cookie_header:
            return None
        
        # Parse cookies to find session cookie
        cookies = {}
        for cookie in cookie_header.split(';'):
            if '=' in cookie:
                name, value = cookie.strip().split('=', 1)
                cookies[name] = value
        
        session_cookie = cookies.get('session')
        if not session_cookie:
            return None
        
        try:
            # Decode Flask session using Flask's session interface
            with self._flask_app.app_context():
                from flask.sessions import SecureCookieSessionInterface
                from urllib.parse import unquote
                
                # Create a session interface to decode the cookie
                session_interface = SecureCookieSessionInterface()
                
                # Create a fake request context to use Flask's session decoding
                from flask import Request
                from werkzeug.datastructures import EnvironHeaders
                
                # Create minimal WSGI environ for the request
                environ = {
                    'REQUEST_METHOD': 'GET',
                    'PATH_INFO': '/',
                    'SERVER_NAME': 'localhost',
                    'SERVER_PORT': '5000',
                    'HTTP_COOKIE': cookie_header,
                    'wsgi.url_scheme': 'http'
                }
                
                # Create request object
                request = Request(environ)
                
                # Decode session using Flask's interface
                session_data = session_interface.open_session(self._flask_app, request)
                
                if session_data:
                    # Extract user_id from session data (Flask-Login stores it as '_user_id')
                    user_id = session_data.get('_user_id')
                    
                    if user_id:
                        return int(user_id)
                    
                return None
                
        except Exception as e:
            log_system_event(f"Error parsing Flask session cookie: {str(e)}", 
                           event_type='security', event_level='warning')
            return None
    
    async def _stream_file(self, send, file_path, filename):
        """Stream a file asynchronously"""
        try:
            async_generator, headers = await create_async_streaming_response(file_path, filename)
            
            # Send HTTP response start
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(k.encode(), v.encode()) for k, v in headers.items()]
            })
            
            # Stream file chunks
            async for chunk in async_generator:
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True
                })
            
            # End response
            await send({
                "type": "http.response.body",
                "body": b"",
                "more_body": False
            })
            
        except Exception as e:
            log_system_event(f"Error streaming file {filename}: {str(e)}", 
                           event_type='download', event_level='error')
            # If we haven't started the response yet, send an error
            await self._send_error(send, 500, "Error streaming file")
    
    async def _handle_streaming_download(self, send, download_request, source_path):
        """Handle zipstream downloads for multi-file games"""
        try:
            # Validate source path is within allowed directories
            allowed_bases = get_allowed_base_directories(self._flask_app)
            if not allowed_bases:
                await self._send_error(send, 500, "Server configuration error")
                return
                
            is_safe, error_message = is_safe_path(source_path, allowed_bases)
            if not is_safe:
                # Use print instead of log_system_event to avoid context issues
                print(f"Security violation - streaming source outside allowed directories: {source_path[:100]}")
                await self._send_error(send, 403, "Access denied")
                return
            
            if not os.path.exists(source_path):
                await self._send_error(send, 404, "Source path not found")
                return
            
            # Get configuration parameters
            chunk_size = self._flask_app.config.get('ZIPSTREAM_CHUNK_SIZE', 65536)
            compression_level = self._flask_app.config.get('ZIPSTREAM_COMPRESSION_LEVEL', 0)
            enable_zip64 = self._flask_app.config.get('ZIPSTREAM_ENABLE_ZIP64', True)
            
            # Generate filename from the original file/folder name
            if download_request.file_location:
                base_name = os.path.basename(download_request.file_location)
                filename = f"{base_name}.zip" if not base_name.lower().endswith('.zip') else base_name
            else:
                # Fallback to game name if file_location is not available
                game = download_request.game
                filename = f"{game.name}.zip" if game else "download.zip"
            
            print(f"Starting zipstream download: {filename}")
            
            # Create zipstream response
            async_generator, headers = async_generate_zipstream_response(
                source_path, filename, chunk_size, compression_level, enable_zip64
            )
            
            # Send HTTP response start
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(k.encode(), v.encode()) for k, v in headers.items()]
            })
            
            # Stream ZIP chunks
            async for chunk in async_generator:
                await send({
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True
                })
            
            # End response
            await send({
                "type": "http.response.body",
                "body": b"",
                "more_body": False
            })
            
            print(f"Completed zipstream download: {filename}")
            
        except Exception as e:
            # Use print and handle potential undefined filename
            error_filename = locals().get('filename', 'unknown')
            print(f"Error streaming ZIP {error_filename}: {str(e)}")
            
            # Check if response has started - if so, we can only close the connection
            # Cannot send error response after http.response.start has been sent
            try:
                # If we haven't sent the response start yet, send an error
                await self._send_error(send, 500, "Error streaming ZIP file")
            except Exception:
                # Response already started, just close the connection gracefully
                try:
                    await send({
                        "type": "http.response.body",
                        "body": b"",
                        "more_body": False
                    })
                except Exception:
                    # Connection already closed, nothing more we can do
                    pass
    
    async def _send_error(self, send, status_code, message):
        """Send an HTTP error response"""
        response_body = json.dumps({"error": message}).encode()
        
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(response_body)).encode())
            ]
        })
        
        await send({
            "type": "http.response.body",
            "body": response_body,
            "more_body": False
        })
    
    async def _handle_lifespan(self, receive, send):
        """Handle ASGI lifespan events (startup/shutdown)"""
        message = await receive()
        
        if message["type"] == "lifespan.startup":
            # Application is starting up
            try:
                # Register graceful shutdown handlers
                from modules.utils_shutdown import register_shutdown_handlers
                register_shutdown_handlers()
                await send({"type": "lifespan.startup.complete"})
            except Exception as e:
                print(f"Startup failed: {e}")
                await send({"type": "lifespan.startup.failed", "message": "Startup failed"})
        
        elif message["type"] == "lifespan.shutdown":
            # Application is shutting down
            try:
                # Request graceful shutdown
                from modules.utils_shutdown import request_shutdown
                request_shutdown()
                print("🛑 ASGI lifespan shutdown initiated")
                await send({"type": "lifespan.shutdown.complete"})
            except Exception as e:
                print(f"Shutdown failed: {e}")
                await send({"type": "lifespan.shutdown.failed", "message": "Shutdown failed"})

# Create lazy ASGI app (won't call create_app() until first HTTP request)
asgi_app = LazyASGIApp()