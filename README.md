# 🎮 SharewareZ v2.7.2

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

### 📋 Prerequisites

#### 🐧 Linux Requirements
- Python 3.11
- pip
- git
- Postgresql server

#### 🪟 Windows Requirements
- Python 3.11 - Install by typing python in powershell, it will open the Window Store, or you cand download manually here: ([Download Python for Windows](https://www.python.org/downloads/windows/))
- pip (comes with Python these days)
- git ([Download Git for Windows](https://gitforwindows.org/)))
- Microsoft Visual C++ 14.0+ ([Download Visual Studio Tools](https://visualstudio.microsoft.com/downloads/))
- Postgresql server  (https://www.postgresql.org/download/windows/)

### 💻 Setup Steps

#### 1️⃣ Clone Repository
```bash
git clone --depth 1 https://github.com/axewater/sharewarez.git
cd sharewarez
```

#### 2️⃣ Virtual Environment Setup

##### 🐧 Linux
```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
```

##### 🪟 Windows (Powershell)
```bash
python3 -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate
python3 -m pip install -r requirements.txt
```

> 💡 Note: Use `python` if `python3` command fails

#### 3️⃣ PostgreSQL Installation

##### 🐧 Linux
```bash
sudo apt install postgresql
psql -U postgres -h localhost
CREATE DATABASE sharewarez;
```

##### 🪟 Windows
- 📥 Download [PostgreSQL for Windows](https://www.postgresql.org/download/windows/)
- 🔧 Run installer & launch PGADMIN
- ➕ Select "Add a new server"
- 📊 Use pgAdmin or CLI:
  ```sql
  psql -U postgres
  CREATE DATABASE sharewarez;
  ```

### ⚙️ Configuration (Windows)
1. Create config.py by copying the example
   Copy config.py.example config.py
2. Create .env by copying .env.example
   copy .env.example .env
3. Edit the .env and setup your database connection string and paths (leave the defaults unless you have a different setup)

### ⚙️ Configuration (Linux)
1. Create config.py by copying the example
   cp config.py.example config.py
2. Create .env by copying .env.example
   cp .env.example .env
3. Edit the .env and setup your database connection string and paths (leave the defaults unless you have a different setup)

### 🚀 Running the Application
### Linux

```bash
chmod +x startweb.sh
./startweb.sh
```
### Windows 

```powershell
./startweb_windows.cmd
```

- Runs with uvicorn and 4 workers for optimal performance
- Automatically handles database migrations and initialization
- Starts on port 5006 by default

#### Database Reset/Setup
```bash
./startweb.sh --force-setup
```
- Resets database and forces setup wizard
- Use when upgrading from older versions or troubleshooting
- After running, use `./startweb.sh` to start the application

### 🐳 Docker Alternative NOT FUNCTIONAL AT THIS TIME - SORRY, COMING SOON
```bash
docker pull kapitanczarnobrod/sharewarez:latest
```

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
