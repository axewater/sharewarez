# 🎮 SharewareZ v2.0 beta

> **⚠️ BETA APPLICATION - USE AT YOUR OWN RISK**

SharewareZ transforms game folders into dynamic, searchable libraries with IGDB integration, adding cover images, screenshots, and metadata for enhanced filtering. Share your library with friends and enable downloads!

## 📢 Important Notes

- 🔄 Updating from older versions: Automatic update supported - simply overwrite files
- ⚠️ For versions below 1.2.1: Database reset required
  - Run `app.py --force-setup` to recreate database
- ⚖️ SharewareZ promotes legal usage only

## ✨ Core Features

### 📚 Game Library Management
- 🔍 Smart folder scanning & cataloging
- 📁 Support for 'updates' and 'extras' folders
- 🖼️ Steam-style popup with screenshot galleries
- 🏷️ Advanced filtering (genre, rating, gameplay modes)
- 🎯 Discovery page features:
  - 🆕 Latest additions
  - ⭐ Top downloads
  - ❤️ Most favorited
  - 🏆 Highly rated games
- 💬 Discord webhook integration

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

#### 🪟 Windows Requirements
- Python 3.11
- pip
- git ([Download Git for Windows](https://github.com/git-for-windows))
- Microsoft Visual C++ 14.0+ ([Download Visual Studio Tools](https://visualstudio.microsoft.com/downloads/))

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

##### 🪟 Windows
```bash
python -m venv venv
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
- 🌐 Default port: `5001` (configurable in `app.py`)
- 👥 User creation via admin panel

## 💬 Support
- 📝 Open an issue on GitHub
- 💭 Join our Discord community