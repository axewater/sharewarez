# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SharewareZ v2.5.4 is a Flask-based web application that transforms game folders into a searchable library with IGDB integration. It provides cover images, screenshots, metadata filtering, and user management for sharing game collections.

## Development Commands

### Running the Application
```bash
# Development mode
python3 app.py

# Using shell script (Linux) - Development
./startweb.sh

# Using shell script (Linux) - Production with uvicorn
PRODUCTION=true ./startweb.sh

# Production with uvicorn directly
uvicorn app:app --host 0.0.0.0 --port 5006 --workers 4

# Force setup wizard (resets database)
python3 app.py --force-setup
```

### Virtual Environment
```bash
# Linux
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt

# Windows
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate
python -m pip install -r requirements.txt
```

### Docker
```bash
# Using docker-compose
docker-compose up

# Pull official image
docker pull kapitanczarnobrod/sharewarez:latest
```

## Architecture

### Application Structure
- **Entry Point**: `app.py` - Creates Flask app and handles CLI arguments
- **Factory Pattern**: `modules/__init__.py` - Contains `create_app()` factory function
- **Configuration**: `config.py` - Database URI, folder paths, API endpoints
- **Database**: PostgreSQL with SQLAlchemy ORM

### Key Modules
- **Routes**: Blueprint-based routing across multiple modules
  - `routes.py` - Main routes
  - `routes_admin.py` - Admin dashboard
  - `routes_library.py` - Game library management
  - `routes_games.py` - Game details and management
  - `routes_discover.py` - Discovery features
  - `routes_downloads.py` - Download functionality
  - `routes_login.py` - Authentication
  - `routes_setup.py` - Initial setup wizard
- **Models**: `models.py` - SQLAlchemy database models
- **Utils**: Multiple utility modules for specific functionality
  - `utils_game_core.py` - Core game operations
  - `utils_scanning.py` - Folder scanning and cataloging
  - `utils_igdb_api.py` - IGDB API integration
  - `utils_download.py` - Download handling
  - `utils_auth.py` - Authentication utilities

### Database
- **Primary Database**: PostgreSQL
- **ORM**: SQLAlchemy with Flask-SQLAlchemy
- **Migrations**: `updateschema.py` - Database schema updates
- **Default Port**: 5432

### Core Features Architecture
- **Game Library**: Folder scanning, metadata extraction, IGDB integration
- **User Management**: Flask-Login with role-based access control
- **Image Processing**: PIL for cover art and screenshots
- **Caching**: Flask-Caching for performance
- **Background Tasks**: Threading for scan operations
- **Downloads**: Auto-zip functionality for multi-file folders

## Configuration

### Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `DATA_FOLDER_WAREZ` - Path to games folder
- `SECRET_KEY` - Flask secret key
- `IGDB_API_ENDPOINT` - IGDB API endpoint

### Default Settings
- **Port**: 5006 (configurable in app.py)
- **Debug Mode**: False
- **Database**: `postgresql://postgres:postgres@localhost:5432/sharewarez`
- **Production Server**: uvicorn with 4 workers
- **Development Server**: Flask built-in server

### File Paths
- **Upload Folder**: `modules/static/library`
- **Images**: `modules/static/library/images`
- **ZIP Downloads**: `modules/static/library/zips`
- **Templates**: `modules/templates/`

## Development Notes

### Database Operations
- Use `--force-setup` flag to reset database and run setup wizard
- Schema updates handled automatically via `updateschema.py`
- Foreign key relationships with cascade deletion

### Authentication
- Flask-Login for session management
- Admin-only areas protected with `@admin_required` decorator
- CSRF protection enabled globally

### Image Processing
- PIL/Pillow for image manipulation
- Automatic thumbnail generation
- Support for cover art and screenshot galleries

### API Integration
- IGDB API for game metadata (deadline August 2025 for v2.5.2+)
- Discord webhook integration for notifications
- RESTful API endpoints for frontend

### Background Processing
- Threading for long-running scan operations
- Queue management for image downloads
- Status tracking for scan jobs

### Security Considerations
- CSRF protection on all forms
- SQL injection protection via SQLAlchemy ORM
- File upload security with secure_filename()
- Password hashing with argon2-cffi

## Testing and Quality

The codebase does not include specific testing frameworks or linting configurations. When adding tests or quality checks, investigate the existing structure first.