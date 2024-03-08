# Sharewarez App Setup Guide

Welcome to the setup guide for Sharewarez App. Follow these instructions to get your development environment ready.

## Prerequisites

Before you start, make sure you have the following prerequisites installed on your system:

- **Windows**: Microsoft Visual C++ 14.0 or greater is required. Download it via [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).

## 1. Setup Your Virtual Environment

First, create and activate a virtual environment for your project:

```
python -m venv venv
python -m pip install -r requirements.txt
.\venv\Scripts\Activate
```

## 2. Install PostgreSQL

Next, install PostgreSQL and create a database named `sharewarez`:

```
psql -U postgres -h localhost
CREATE DATABASE sharewarez;
```

## 3a. Setup with Mail Features Enabled

To set up the app with mail features:

1. **Create `config.py`**: Copy `config.py.example`. Ensure `INITIAL_WHITELIST` contains the admin's email.
2. **Database URI**: Should point to your newly created database.
3. **IGDB API Keys**: Obtain your keys from [IGDB API Docs](https://api-docs.igdb.com/#getting-started).

### Running the App

- Run the app and register the first user with the email mentioned in `config.py`.
- Restart the app. The first user is now an admin.

## 3b. Setup without Mail (NO SMTP)

For a setup without mail:

1. **Create `config.py`**: Copy `config.py.example`.
2. **Database URI**: Should point to your newly created database.

### Initial Configuration

- Run `setup.py` to create an admin user.
- Start the application by running `app.py`.

### Creating Additional Users

- Use the admin panel to create any additional users as needed.

---

Thank you for setting up the Sharewarez App. For further assistance, please open an issue on this repository.

