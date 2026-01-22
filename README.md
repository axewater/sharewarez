# 🎮 SharewareZ v2.9.7

SharewareZ transforms any game folder into a searchable library with IGDB integration, adding cover images, screenshots, and metadata for enhanced filtering.
Invite your friends securely and share your favorite games!

## 📢 Important Notes

- 🔄 Updating from older versions: Automatic update supported - simply overwrite files and run 'pip install -r requirements.txt' again.
- ⚠️ For versions below 2.0: Database reset required
- Run `./startweb.sh --force-setup` to recreate database and run setup wizard
- ⚖️ SharewareZ promotes and encourages the legal use of software. We do not condone or support any unauthorized distribution or use of copyrighted material.
- 📝 You must install version >2.5.2 before August 2025 or lose the ability to connect to IGDB for any lookups.

## ✨ Core Features

### 📚 Game Library Management
- 🔍 Smart folder scanning & cataloging with multi-threaded processing (4 threads by default)
- ⚡ Multi-threaded image downloading and processing for faster library building
- 🖼️ Steam-style popup with screenshot galleries
- 🏷️ Advanced filtering (genre, rating, gameplay modes)
- 📁 Support for 'updates' and 'extras' folders
- 🎯 Discovery page to find new gems:
  - 🆕 Latest additions
  - ⭐ Top downloads
  - ❤️ Most favorited
  - 🏆 Highly rated games
- 🚀 Ability to play ROM files directly in browser
- 💬 Discord webhook integration (bot posts in your channel when there is a new game)

### 💾 Download Features
- 📦 Streaming ZIP downloads for multi-file folders (no disk storage required)
- 📄 NFO file indexing with viewer
- ⚡ Multi-threaded download processing with configurable thread count

### 👥 User Management
- 🛡️ Role-based access control
- 📨 Invitation system (admin-controlled)
- 🔑 Self-service password reset (requires SMTP)

### ⚡ Performance Features
- 🚀 Multi-threaded game scanning (4 threads by default, configurable)
- 📥 Multi-threaded image downloading (8 threads by default, configurable)
- 🔄 Chunked streaming downloads for large files
- 🌐 ASGI-based web server with uvicorn and multiple workers

## 🚀 Installation Guide

## ⚡ Install Script Method (Linux Only)

**One-Command Installation:**
```bash
git clone --depth 1 https://github.com/axewater/sharewarez.git
cd sharewarez
# IMPORTANT: Make install script executable first
chmod +x install-linux.sh
./install-linux.sh
```

The auto-installer will:
- ✅ Detect your Linux distribution automatically
- ✅ Install all prerequisites (Python, PostgreSQL, Git)
- ✅ Set up database with secure credentials
- ✅ Configure the application automatically
- ✅ Generate secure encryption keys
- ✅ Start the application when ready

**Advanced Options:**
```bash
# Specify custom games directory
./install-linux.sh --games-dir /path/to/games

# Development setup with extra tools including unit testing
./install-linux.sh --dev

# Skip database setup (use existing)
./install-linux.sh --no-db

# Override existing installation
./install-linux.sh --force
```

---

## 🐧 Linux Manual Install

If you prefer manual setup or the auto-installer doesn't work:

**Step 1: Install Prerequisites**
```bash
# Update package list
sudo apt update

# Install Python 3.11+ and pip
sudo apt install python3 python3-pip python3-venv

# Install git
sudo apt install git

# Install PostgreSQL database server
sudo apt install postgresql postgresql-contrib

# Verify installations
python3 --version
python3 -m pip --version
git --version

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Step 2: Set up PostgreSQL**
```bash
# Switch to postgres user and create database
sudo -u postgres psql
```
```sql
-- In PostgreSQL shell, create database and user
CREATE DATABASE sharewarez;
CREATE USER sharewarezuser WITH ENCRYPTED PASSWORD 'your_password_here';
GRANT ALL PRIVILEGES ON DATABASE sharewarez TO sharewarezuser;
\q
```

**Step 3: Clone and Set up SharewareZ**
```bash
# Clone the repository
git clone --depth 1 https://github.com/axewater/sharewarez.git
cd sharewarez

# IMPORTANT: Make shell scripts executable first
chmod +x *.sh

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
python3 -m pip install -r requirements.txt
```

**Step 4: Configure Application**
```bash
# Copy configuration files
cp config.py.example config.py
cp .env.example .env

# Edit the .env file with your settings
nano .env
```

**Important**: Update these values in your `.env` file:
- `DATABASE_URL=postgresql://sharewarezuser:your_password_here@localhost:5432/sharewarez`
- `DATA_FOLDER_WAREZ=/path/to/your/games/folder`
- `SECRET_KEY=your_secure_random_key_here`

**Step 5: Start SharewareZ**
```bash
# IMPORTANT: Make all shell scripts executable first
chmod +x *.sh
./startweb.sh
```

**Step 6: Complete Setup**
1. Open your browser to `http://localhost:5006`
2. Complete the setup wizard and create your admin account

---

## 🪟 Windows Manual Install

**Step 1: Install Prerequisites**

1. **Install Python 3.11+**
   - Open PowerShell as Administrator, type `python` (opens Microsoft Store)
   - Install Python 3.11 or download from [python.org](https://www.python.org/downloads/windows/)
   - ✅ Check "Add Python to PATH" during installation

2. **Install Git**
   - Download from [Git for Windows](https://gitforwindows.org/) and install with default settings

3. **Install Visual C++ Build Tools**
   - Download [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/)
   - Install "C++ build tools" workload

4. **Install PostgreSQL**
   - Download from [PostgreSQL for Windows](https://www.postgresql.org/download/windows/)
   - Install with default settings and remember the `postgres` user password

**Step 2: Set up PostgreSQL**
Open pgAdmin (installed with PostgreSQL):
1. Connect to your PostgreSQL server
2. Right-click "Databases" → "Create" → "Database"
3. Name: `sharewarez` → Click "Save"

**Step 3: Clone and Set up SharewareZ**
Open PowerShell and run:
```powershell
# Clone the repository
git clone --depth 1 https://github.com/axewater/sharewarez.git
cd sharewarez

# Create and activate virtual environment
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt
```

**Step 4: Configure Application**
```powershell
# Copy configuration files and edit
copy config.py.example config.py
copy .env.example .env
notepad .env
```

**Important**: Update these values in your `.env` file:
- `DATABASE_URL=postgresql://postgres:your_postgres_password@localhost:5432/sharewarez`
- `DATA_FOLDER_WAREZ=C:\Path\To\Your\Games\Folder`
- `SECRET_KEY=your_secure_random_key_here`

**Step 5: Start SharewareZ**
```powershell
# Start the application
.\startweb_windows.cmd
```

**Step 6: Complete Setup**
1. Open your browser to `http://localhost:5006`
2. Complete the setup wizard and create your admin account

---

## 🐳 Docker Install

**Quick Docker Setup:**
```bash
# Clone the repository
git clone https://github.com/axewater/sharewarez.git
cd sharewarez

# Copy and configure environment file
cp .env.docker.example .env
# Edit .env file with your game directory path:
# DATA_FOLDER_WAREZ=/path/to/your/games

# Start with Docker Compose
docker-compose up -d
```

**What it includes:**
- ✅ Complete PostgreSQL database setup
- ✅ Automatic application configuration
- ✅ Persistent data storage
- ✅ Ready-to-use on port 5006

**Step-by-step:**
1. Clone repository and navigate to folder
2. Copy `.env.docker.example` to `.env`
3. Edit `.env` file - set `DATA_FOLDER_WAREZ` to your games directory
4. Run `docker-compose up -d`
5. Open browser to `http://localhost:5006`
6. Complete setup wizard and create admin account

**Management commands:**
```bash
# View logs
docker-compose logs -f

# Stop containers
docker-compose down

# Update to latest version
git pull && docker-compose down && docker-compose up -d --build

# Reset database (if needed)
docker-compose exec web /app/startweb-docker.sh --force-setup
```

---

## 🔧 Post-Installation

**Database Reset (if needed):**
- Linux: `./startweb.sh --force-setup`
- Windows: `.\startweb_windows.cmd --force-setup`

**Updating SharewareZ:**
1. Stop the application (Ctrl+C)
2. `git pull` → `pip install -r requirements.txt`
3. Restart with startup script

**Troubleshooting:**
- Port 5006 in use: Change port in startup script or set PORT environment variable
- Database errors: Check PostgreSQL is running and credentials are correct
- Linux permissions: Ensure read access to game directories

## 🔧 Additional Settings
- 🌐 Default port: `5006` (configurable via PORT environment variable)
- 👥 Go the admin dashboard for further configuration

## 🌐 Changing the Port Number

SharewareZ runs on port `5006` by default. To change this:

**For Linux/Windows installations:**
1. Edit your `.env` file
2. Add or modify: `PORT=8080` (replace 8080 with your desired port)
3. Restart SharewareZ

**For Docker installations:**
- Docker containers always use port `5006` internally
- The external port is mapped via docker-compose.yml (also defaults to 5006)
- To change external port, edit the `ports` section in docker-compose.yml

**Examples:**
```bash
# In .env file - run on port 8080
PORT=8080

# In .env file - run on port 3000
PORT=3000
```

## 🔧 Supported platforms to play in browser 
- Most 8, 16 and 32 bit retro consoles work, see webretro repo for more full list
- PSX, Sega MS, Sega 32x not working at the moment
- Sega Saturn working on single file games and some audio issues
- Files must be unzipped. ZIP, 7z and RAR are not (yet) supported. This is not a webretro issues, so it will be fixed in a future Sharewarez update.

## 💬 Support
- 📝 Open an issue on GitHub
- 💭 Join our Discord community https://discord.gg/WTwp236zU7

## 📝 3rd party code
- 💭 Thanks to BinBashBanana's webretro we can now run ROMs in the browser.
- 🌐 Check out his project here: https://github.com/BinBashBanana/webretro


## Changelog

  Version 2.9.6

  - 🎮 Play Status Feature: Per-user game completion tracking with status badges
  
  Version 2.9.3

  - 📝 Local Metadata: Added support for local metadata storage
  - 📊 Progress Indicators: Added image update progress indicator
  - 🔄 Auto Scan: Improved auto scan page layout with better scan spinner
  - 🔧 Settings: Updated default visibility settings for libraries on discovery page
  - ❤️ Bug Fixes: Fixed favorite hearts not showing on all pages, fixed library_uuid overwrite issue
  - 🔒 Security: CSRF token in URL removed

  Version 2.9.2

  - 🔧 Minor version update with infrastructure improvements

  Version 2.9.1

  - 🔍 Filter aware search on library page (search within selected library + filters)

  Version 2.9.0

  - 🎮 How Long To Beat Integration: Added HLTB (HowLongToBeat) integration for displaying game completion times
  - ⏱️ Scan Job Control: HLTB data collection configurable via scan jobs (adds to scan time when enabled)
  - 📊 Game Details Enhancement: Completion time estimates displayed on game detail pages

  Version 2.8.2

  - 🎬 Attract Mode: Full-featured screensaver mode with automatic trailer playback

  Version 2.8.1

  - 🎥 Random Trailers: New feature to browse and watch game trailers randomly
  - 🎛️ Trailer Controls: Filter options, autoplay controls, and auto-next functionality

  Version 2.8.0

  - 🔧 Port Standardization: Docker now uses port 5006 consistently (matches non-Docker installs)
  - 🗄️ PostgreSQL Update: Updated to secure PostgreSQL version in Docker Compose
  - 🧹 Code Cleanup: Removed legacy zip-related code (streaming downloads now standard)
  - 📝 Environment Updates: Improved .env.docker.example configuration

  Version 2.7.7

  - 🐳 Docker fixed and Updated to 277
  

  Version 2.7.6

  - 🪟 Windows Support: Updated Windows startup scripts for better compatibility
  - 🐧 Linux Installer: Enhanced auto-installer with sudo checks and interactive prompts
  - 🔒 Git Hooks: Added hooks to preserve executable permissions on .sh scripts
  - 📁 File Permissions: Comprehensive fix for shell script execute permissions
  - 📖 Documentation: Updated README with improved installation instructions

  Version 2.7.5

  - 🎨 CSS Architecture Improvements: Comprehensive CSS optimization with centralized color management system for better consistency and maintainability
  - ⚡ Startup Process Enhancement: Streamlined initialization routine with reduced duplicate initialization calls for faster startup times
  - 🛠️ Automated Installation: Added comprehensive auto-install script with distribution detection and dependency management

  Version 2.7.x

  - 🎨 Theme System Overhaul: Complete refactoring using macros for more efficient code, eliminated themes.zip dependency
  - ⚡ Streaming ZIP Downloads: Major implementation of asynchronous streaming downloads for better performance
  - 🔄 Download System Rewrite: All download systems redesigned with new download mechanism for updates and extras
  - 📊 Library UI Modernization: Pagination modernized, improved image upload support (.webp), better filtering with server-side persistence
  - 🎮 Game Management: Enhanced game details page UI, smooth animations for game removal, better popup menu functionality

  Version 2.6.x

  - 🚀 ASGI Implementation: Upgraded from Flask to ASGI (uvicorn) for production readiness and async support
  - 🔧 Major Code Refactoring:
    - Modularized routes into separate API modules (routes_apis/)
    - Consolidated CSRF handling across JavaScript files
    - Extracted JavaScript from templates for maintainability
  - 📈 Performance Improvements:
    - Scan speed dramatically improved (99% reduction in DB queries via caching)
    - Async image downloading with TURBO mode for parallel processing
    - Optimized database queries using SQLAlchemy 2.0 constructs
  - 🧪 Comprehensive Unit Testing: Added extensive test coverage across all modules
  - 🔒 Security Enhancements:
    - SQL injection fixes with multithreaded scanning
    - Enhanced input validation and CSRF protection
    - Secure file handling improvements
  - 📬 Discord Integration: Full Discord webhook notifications and manual notification system
  - 👥 User Management: Enhanced invite system with timezone-aware structure
  - ⚙️ Setup & Configuration: Improved setup wizard, better startup processes, enhanced SMTP handling

  Version 2.5.x

  - 🎯 IGDB API Updates: Support for new IGDB field names and API changes
  - 🎮 Platform Support: Enhanced ROM browser play support for multiple platforms (PSX, Sega systems)
  - 🔍 Game Identification: Custom IGDB ID support and improved game matching
  - 📱 UI Improvements: Better responsive design, enhanced game details display
  - 🗄️ Database Optimization: Schema updates and relationship improvements

  Key Infrastructure Changes

  - Database: Migrated to SQLAlchemy 2.0, timezone-aware datetime handling
  - Frontend: Bootstrap 5.3 adoption, jQuery modernization, improved DataTables integration
  - Backend: Flask app factory pattern, better blueprint organization
  - Development: Comprehensive testing framework, improved Docker support
  - Performance: Async processing, streaming capabilities, optimized scanning algorithms
