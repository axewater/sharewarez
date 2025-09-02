# 🎮 SharewareZ v2.6.1

** ⚠️This is a BETA application⚠️ **

SharewareZ transforms any game folder into a searchable library with IGDB integration, adding cover images, screenshots, and metadata for enhanced filtering.
Invite your friends securely and share your favorite games!

## 📢 Important Notes

- 🔄 Updating from older versions: Automatic update supported - simply overwrite files and run 'pip install -r requirements.txt' again.
- ⚠️ For versions below 2.0: Database reset required
- Run `app.py --force-setup` to recreate database and run setup wizard
- ⚖️ SharewareZ promotes and encourages the legal use of software. We do not condone or support any unauthorized distribution or use of copyrighted material.
- 📝 You must install version >2.5.2 before August 2025 or lose the ability to connect to IGDB for any lookups.

## ✨ Core Features

### 📚 Game Library Management
- 🔍 Smart folder scanning & cataloging
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

### 👥 User Management
- 🛡️ Role-based access control
- 📨 Invitation system (admin-controlled)
- 🔑 Self-service password reset (requires SMTP)

## 🚀 Installation Guide

### 📋 Prerequisites

#### 🐧 Linux Requirements
- Python 3.11
- pip
- git
- Postgresql server

#### 🪟 Windows Requirements
- Python 3.11 ([Download Python for Windows](https://www.python.org/downloads/windows/))
- pip (comes with Python these days)
- git ([Download Git for Windows](https://gitforwindows.org/)))
- Microsoft Visual C++ 14.0+ ([Download Visual Studio Tools](https://visualstudio.microsoft.com/downloads/))
- Postgresql server  (https://www.postgresql.org/download/windows/)

### 💻 Setup Steps

#### 1️⃣ Clone Repository
```bash
git clone https://github.com/axewater/sharewarez/
cd sharewarez
```

#### 2️⃣ Virtual Environment Setup

##### 🐧 Linux
```bash
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

##### 🪟 Windows (Powershell)
```bash
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate
python -m pip install -r requirements.txt
```

> 💡 Note: Use `python3` if `python` command fails

#### 3️⃣ PostgreSQL Installation

##### 🐧 Linux
```bash
sudo apt install postgresql
psql -U postgres -h localhost
CREATE DATABASE sharewarez;
```

##### 🪟 Windows
- 📥 Download [PostgreSQL for Windows](https://www.postgresql.org/download/windows/)
- 🔧 Run installer & launch Stack Builder
- ➕ Select "Add a new server"
- 📊 Use pgAdmin or CLI:
  ```sql
  psql -U postgres
  CREATE DATABASE sharewarez;
  ```

### ⚙️ Configuration
1. Edit `config.py`
2. Configure:
   - 🔗 Database connection string
   - 📁 Games folder path

### 🐳 Docker Alternative
```bash
docker pull kapitanczarnobrod/sharewarez:latest
```

## 🔧 Additional Settings
- 🌐 Default port: `5006` (configurable in `app.py` or in docker-compose.yml for docker)
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

## 📝 Changelog
2.5.3 - Refreshed themes.zip with updated file
2.5.2 - IGDB.com API update compatibility implemented (deadline aug 2025)
