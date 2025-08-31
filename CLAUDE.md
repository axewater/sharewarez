## Project Overview

SharewareZ v2.5.4 is a Flask-based web application that transforms game folders into a searchable library with IGDB integration. It provides cover images, screenshots, metadata filtering, and user management for sharing game collections.


### Virtual Environment
always activate the venv when performing any kind of code testing.

```bash
source venv/bin/activate

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
- Use `--force-setup` flag to reset database and run setup wizard (claude is never allowed to run this, ask the user)
- Schema updates handled automatically via `updateschema.py`
- Foreign key relationships with cascade deletion

### Authentication
- Flask-Login for session management
- Admin-only areas protected with `@admin_required` decorator
- CSRF protection enabled globally

### API Integration
- IGDB API for game metadata
- Discord webhook integration for notifications
- RESTful API endpoints for frontend

### Background Processing
- Threading for long-running scan operations
- Queue management for image downloads
- Status tracking for scan jobs


IMPORTANT: When creating unit tests, we always work against the actual Postgresql TEST DB, we DO NOT work with any fake sqlite (in memory) db's. The URI to the DB is in the .env and config.py. variable name is TEST_DATABASE_URL