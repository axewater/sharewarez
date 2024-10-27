# 🎮 Welcome to SharewareZ v1.4.9.3 🚀

SharewareZ transforms any game folder into a dynamic, searchable library. With IGDB integration, it indexes games and adds cover images, screenshots, and metadata for easy filtering. Plus, you can invite friends to download games from your library.

**⚠️ THIS IS A BETA APPLICATION - USE AT YOUR OWN RISK ⚠️**
When updating from 1.2.1 run the update_game_sizes.py script

🚧 IF YOU HAVE VERSION BELOW 1.2.1, INSTALLED YOU WILL NEED TO RESET YOUR DATABASE OR TAKE CARE OF YOUR OWN MIGRATION 🚧
(run setup_nosmpty.py to recreate your db if needed)

***[SharewareZ promotes legal use of its application]***

## 🌟 Features Overview
1. **Game Library Management** 🎲
    - Multiple library support.
    - Automated scanning of folders to catalog games.
    - Library page includes Steam-style popup with screenshot slideshow.
    - Filtering options based on genre, rating, and gameplay modes
    - Discovery page showcasing latest additions, top downloads, and highly rated games.
    - Discord webhook for announcements.
2. **Download games** 💻
    - Auto-zip. Folders with multiple files are zipped on demand.
    - NFO files are indexed and viewable on games details page.
3. **User and Role management** 🔐
    - Role-based access control for admins and regular users.
    - User invite system. Optionally grant invites to users, by admin.

# 🛠️ Sharewarez App Setup Guide

Read these instructions carefully before diving into things :)
You can install SharewareZ manually, or use the Docker image.
The following instructions are for the manual installation.

## 📋 Prerequisites

Before you start, make sure you have the following prerequisites installed on your system:

- **Linux**: 🐧
    - Python 3.11
    - pip
    - git

- **Windows**: 🪟
    - Python 3.11
    - pip
    - git [Git for Windows (github.com)](https://github.com/git-for-windows)
    - Microsoft Visual C++ 14.0 or greater is required (VC_redist.x64.exe) [Download Visual Studio Tools (microsoft.com)](https://visualstudio.microsoft.com/downloads/)

## 🚀 1️⃣ Download SharewareZ files
First things first, git clone that treasure onto your system:
(open a command prompt)
```
git clone https://github.com/axewater/sharewarez/
cd sharewarez
```

## 🕶️ 1️⃣ Setup Your Virtual Environment
Let’s get a virtual environment up and running! 🏃‍♂️ This will keep the libraries used by the app all in 1 place💨

🐧For Linux: 
```
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```
📝Note: You might need to use `python3` instead of python in some cases.

🪟 For Windows: 
```
python -m venv venv
.\venv\Scripts\Activate
python -m pip install -r requirements.txt
```

 🤔Remember: If python doesn’t do the trick, try python3!

## 🗃️ 2. Install PostgreSQL
Time to set up the database where all your game data will live! 🎮📚

🐧For Linux:
```
sudo apt install postgresql
psql -U postgres -h localhost
CREATE DATABASE sharewarez;
```

🪟For Windows:

- Download PostgreSQL server for Windows [PostgreSQL: Windows installers](https://www.postgresql.org/download/windows/)
- Run the installer and launch `Stack Builder`
- Choose `Add a new server`
- use pgAdmin to connect to your PostgreSQL server.
- Right-click on `Databases` and select `New Database`
- Name it **sharewarez** and hit `Save` or `OK`

🔧 Alternatively, using command-line:
```
SQL
psql -U postgres
CREATE DATABASE sharewarez;
```
## 📧 3a. Setup with Mail Features Enabled
📬Why do I need to setup SMTP settings ?
✉️ Mail is required for user self-service. Registration, password resets and the invite system all work by sending 'secure links' to a user's email.

- **Create 'config.py'**: Copy `config.example` and rename it to `config.py`.
- **Set a Secret Key**: This key is used for securing session cookies, it's important you have your own unique key here. Just put 32 (for instance) random🎲 characters there.
- **Enter Database URI**: Fill in the DATABASE_URI with your database details.
- **Configure SMTP Settings**: Set up your mail server 📬details to enable online user registration, invites and pw resets. Usually your ISP will have an SMTP server you can use here.

🔑 Make sure to add the admin’s email to the `INITIAL_WHITELIST` for your admin account! This will be the only email address that can register the first account. The first account is automatically admin.

🔐 Get your IGDB API Keys from [IGDB API docs](https://api-docs.igdb.com/#getting-started). Follow the steps outlined there and put the keys in your `config.py`

🛠️ 3b. Setup without Mail (NO SMTP)
📭❌Single user system ? Whatever your reason, you can easily setup the application without SMTP. No mail? No problem!

- Create 'config.py': copy 'config.example' file supplied.
- Database URI: Point it to your `sharewarez` database.
- Run `setup_nosmtp.py` to create an admin user.
- Start the application by running `app.py`.

## ⚠️ Known Issues
- **Upgrading from older versions**: Unfortunately we do not support backward compatibility with older databases. Use `config_nosmtp.py` to recreate the database.
- **Server settings bug**: If you open server settings and change any settings, some settings may not apply the correct defaults resulting in settings like 'display logo' to disable themselves. Just go to settings and apply settings as needed.

### Other notes

- Use the admin panel to create any additional users as needed.
- The app runs on port `5001`, you can simply change this in `app.py`

### Docker image
```
docker pull kapitanczarnobrod/sharewarez:1.2.0:latest
```
---
Thank you for setting up the Sharewarez App. For further assistance, please open an issue on this repository or join my Discord.