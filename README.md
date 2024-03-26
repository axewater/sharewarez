# 🎮 Welcome to SharewareZ v1.0.4 🚀
SharewareZ transforms any game folder into a dynamic, searchable library. With IGDB integration, it indexes games and adds cover images, screenshots, and metadata for easy filtering. Plus, you can invite friends to download games from your library.

**⚠️ THIS IS A BETA APPLICATION - USE AT YOUR OWN RISK ⚠️**

🚧 IF YOU HAVE V1.0.0 INSTALLED YOU WILL NEED TO RESET YOUR DATABASE OR TAKE CARE OF YOUR OWN MIGRATION 🚧

***[SharewareZ promotes legal use of its application]***

## 🌟 Features Overview
1. **User Authentication** 🔐
    - Secure sign-up and sign-in processes with email verification.
    - Password recovery system.
    - Role-based access control for admins and regular users.
2. **User Profile** 👤
    - Customizable user profiles with editable information.
    - Support for avatar uploads.
3. **Game Management** 🎲
    - Automated scanning of specified folders to catalog games.
    - Integration with IGDB to fetch comprehensive game details.
    - Full CRUD (Create, Read, Update, Delete) capabilities for managing your game library.
4. **Library Browsing & Discoverability** 🔍
    - A dynamic discovery page showcasing latest additions, top downloads, and highly rated games.
    - Advanced filtering options based on genre, rating, and gameplay mode to fine-tune your search.
    - Detailed game summaries, including genre, themes, supported platforms, and more.
    - Downloadable game files, neatly packaged as zipped archives.
5. **System Management & Administration** 🛠️
    - User account and role management.
    - Whitelist access management.
    - Monitoring & management of library scan jobs.
    - Dashboard for insights into server and application settings.
6. **Download Management** 📥
    - Oversight of user download activities.
    - Capabilities to clear pending downloads.
7. **Security Features** 🔒
    - Implementation of industry-standard security practices.
    - Cross-Site Request Forgery (CSRF) protection.
    - Strict file upload validation to prevent security risks.
    - Defense against SQL injection through parameterized queries.
    - Secure password hashing and token-based email verification.

## ⚠️ Known Issues
**Manual Folder Addition Screen**: Currently, the manual folder addition functionality is experiencing issues. We're actively working on a fix and appreciate your patience.

# 🛠️ Sharewarez App Setup Guide

Welcome to the setup guide for Sharewarez App. Follow these instructions carefully before diving into things :)
You can install SharewareZ manually, or use the Docker image. The following instructions are for the manual installation.

## 📋 Prerequisites

Before you start, make sure you have the following prerequisites installed on your system:

- **Linux**: 🐧
    - Python 3.11
    - pip

- **Windows**: 🪟
    - Python 3.11
    - pip
    - Microsoft Visual C++ 14.0 or greater is required. Microsoft C++ Build Tools.

## 🚀 1️⃣ Setup Your Virtual Environment
First things first, let’s get that virtual environment up and running! 🏃‍♂️💨

For Linux:
```
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

🐧 Note: You might need to use python3 instead of python in some cases.

For Windows:
```
python -m venv venv
.\venv\Scripts\Activate
python -m pip install -r requirements.txt
```

🪟 Remember: If python doesn’t do the trick, try python3!

🗃️ 2. Install PostgreSQL
Time to set up the database where all your game data will live! 🎮📚

For Linux:
```
sudo apt install postgresql
psql -U postgres -h localhost
CREATE DATABASE sharewarez;
```

For Windows:

Head over to the official PostgreSQL website and download the installer.
Run the installer and launch Stack Builder.
Choose to “Add a new server.”
After adding the server:

Fire up pgAdmin and connect to your PostgreSQL server.
Right-click on “Databases” and select “New Database.”
Name it sharewarez and hit “Save” or “OK.”
🔧 Alternatively, for command-line enthusiasts:
```SQL

psql -U postgres
CREATE DATABASE sharewarez;
```

📧 3a. Setup with Mail Features Enabled
Let’s enable those mail features to keep everyone connected! 📬✉️

Create config.py: Copy config.py.example and rename it to config.py.
Set a Secret Key: Whip up a secret key that’s as random as a dice roll. 🎲
Enter Database URI: Fill in the DATABASE_URI with your database details.
Configure SMTP Settings: Set up your mail server details so you can send out those important emails!
🔑 Make sure to add the admin’s email to the INITIAL_WHITELIST for those admin superpowers!

🔐 Grab your IGDB API Keys from the IGDB API Docs to connect with the gaming universe!

🛠️ 3b. Setup without Mail (NO SMTP)
Prefer to go postal-free? No problem! 📭❌

Create config.py: copy config.py.example.
Database URI: Point it to your shiny new `sharewarez` database.
👩‍💻 Run setup.py to create an admin user and kickstart the app with app.py.

- Run `setup.py` to create an admin user.
- Start the application by running `app.py`.

### Other notes

- Use the admin panel to create any additional users as needed.
- The app runs on port 5001, you can simply change this in app.py

### Docker image
```
docker pull kapitanczarnobrod/sharewarez:1.0.4
```

**Make sure to setup the correct paths to your warez folder (Windows and Linux)**

---

Thank you for setting up the Sharewarez App. For further assistance, please open an issue on this repository.
