# 🎮 SharewareZ v2.7.3

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
- 📦 Auto-zip functionality for multi-file folders
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

Choose your preferred installation method:

---

## 🐧 Linux Installation

### Step 1: Install Prerequisites
```bash
# Update package list
sudo apt update

# Install Python 3.11+, pip, git, and PostgreSQL
sudo apt install python3 python3-pip python3-venv git postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Step 2: Set up PostgreSQL
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

### Step 3: Clone and Set up SharewareZ
```bash
# Clone the repository
git clone --depth 1 https://github.com/axewater/sharewarez.git
cd sharewarez

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
python3 -m pip install -r requirements.txt
```

### Step 4: Configure Application
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

### Step 5: Start SharewareZ
```bash
# Make startup script executable
chmod +x startweb.sh

# Start the application
./startweb.sh
```

### Step 6: Complete Setup
1. Open your browser to `http://localhost:5006`
2. Complete the setup wizard
3. Create your admin account
4. Configure your game libraries

---

## 🪟 Windows Installation

### Step 1: Install Prerequisites

1. **Install Python 3.11+**
   - Open PowerShell as Administrator
   - Type `python` - this will open Microsoft Store
   - Install Python 3.11 or download from [python.org](https://www.python.org/downloads/windows/)
   - Make sure to check "Add Python to PATH" during installation

2. **Install Git**
   - Download from [Git for Windows](https://gitforwindows.org/)
   - Install with default settings

3. **Install Visual C++ Build Tools**
   - Download [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/)
   - Install "C++ build tools" workload

4. **Install PostgreSQL**
   - Download from [PostgreSQL for Windows](https://www.postgresql.org/download/windows/)
   - Install with default settings
   - Remember the password you set for the `postgres` user

### Step 2: Set up PostgreSQL
1. Open pgAdmin (installed with PostgreSQL)
2. Connect to your PostgreSQL server
3. Right-click "Databases" → "Create" → "Database"
4. Name: `sharewarez`
5. Click "Save"

**Alternative - Command Line:**
```cmd
# Open Command Prompt and run:
psql -U postgres
```
```sql
CREATE DATABASE sharewarez;
\q
```

### Step 3: Clone and Set up SharewareZ
Open PowerShell and run:
```powershell
# Clone the repository
git clone --depth 1 https://github.com/axewater/sharewarez.git
cd sharewarez

# Create virtual environment
python -m venv venv

# Activate virtual environment
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt
```

### Step 4: Configure Application
```powershell
# Copy configuration files
copy config.py.example config.py
copy .env.example .env

# Edit .env file
notepad .env
```

**Important**: Update these values in your `.env` file:
- `DATABASE_URL=postgresql://postgres:your_postgres_password@localhost:5432/sharewarez`
- `DATA_FOLDER_WAREZ=C:\Path\To\Your\Games\Folder`
- `SECRET_KEY=your_secure_random_key_here`

### Step 5: Start SharewareZ
```powershell
# Start the application
.\startweb_windows.cmd
```

### Step 6: Complete Setup
1. Open your browser to `http://localhost:5006`
2. Complete the setup wizard
3. Create your admin account
4. Configure your game libraries

---

## 🔧 Common Post-Installation Tasks

### Database Reset (if needed)
**Linux:**
```bash
./startweb.sh --force-setup
```

**Windows:**
```powershell
.\startweb_windows.cmd --force-setup
```

### Updating SharewareZ
1. Stop the application (Ctrl+C)
2. Pull latest changes: `git pull`
3. Update dependencies: `pip install -r requirements.txt`
4. Restart: `./startweb.sh` (Linux) or `.\startweb_windows.cmd` (Windows)

### Troubleshooting
- **Port 5006 already in use**: Change port in startup script
- **Database connection errors**: Check PostgreSQL is running and credentials are correct
- **Permission errors on Linux**: Ensure your user has read access to game directories

### 🐳 Docker Installation (Recommended for Production)

#### Prerequisites
- Docker and Docker Compose installed
- At least 2GB RAM and 10GB disk space

#### Quick Setup
1. **Clone the repository**
   ```bash
   git clone --depth 1 https://github.com/axewater/sharewarez.git
   cd sharewarez
   ```

2. **Configure environment**
   ```bash
   cp .env.docker.example .env
   # Edit .env and set your paths and passwords
   ```

3. **Create required directories**
   ```bash
   mkdir -p db_data
   mkdir -p uploads
   # Set DATA_FOLDER_WAREZ to your games directory path in .env
   ```

4. **Start the services**
   ```bash
   docker-compose up -d
   ```

5. **Access SharewareZ**
   - Open browser to `http://localhost:5006`
   - Complete the setup wizard

#### Docker Commands
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f app

# Reset database (force setup)
docker-compose exec app /app/startweb-docker.sh --force-setup

# Stop services
docker-compose down

# Update to latest version
docker-compose pull && docker-compose up -d
```

#### Docker Configuration Notes
- Games directory is mounted read-only to `/storage`
- Upload directory is mounted for persistent cover images
- PostgreSQL data is stored in named volume `db_data`
- Default port is 5006 (configurable in docker-compose.yml)

## 🔧 Additional Settings
- 🌐 Default port: `5006` (configurable in `startweb.sh` for normal operation or docker-compose.yml for docker)
- 👥 Go the admin dashboard for further configuration

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
