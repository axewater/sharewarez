# Sharewarez App Setup Guide

Welcome to the setup guide for Sharewarez App. Follow read these instructions carefully before diving into things :)
You can install SharewareZ manually, or use the Docker image. The following instructions are for the manual installation.

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

1. **Create `config.py`**: 
- Copy `config.py.example`: Start by making a copy of `config.py.example` and rename it to `config.py`. This file will serve as the basis for your application's configuration. (sidenote: You can also use a .env file for some of the settings if you prefer)

- Set a Secret Key: Generate a secret key that is random and long. This key is crucial for securely signing your app's sessions and cookies. Use a combination of letters, numbers, and symbols to make it as secure as possible.

- Enter Database URI: Specify the URI of your database in the `DATABASE_URI` setting. This URI should include the username, password, host, and database name you just created.

- Configure SMTP Settings: To enable email sending capabilities for user registration and notifications, configure the SMTP settings as follows:
    - `MAIL_SERVER`: The address of your mail server.
    - `MAIL_PORT`: The port your mail server uses for outgoing mail.
    - `MAIL_USE_TLS`: Set to True or False depending on your server's requirements.
    - `MAIL_USERNAME`: Your mail server username.
    - `MAIL_PASSWORD`: Your mail server password.

- Ensure `INITIAL_WHITELIST` Contains the Admin's Email: Add the admin's email address to the `INITIAL_WHITELIST` in your configuration. This step is crucial for granting initial access and administrative privileges.

- Obtain IGDB API Keys:
        Visit the IGDB API Docs and follow the instructions to obtain your IGDB Client ID and Client Secret. These keys are necessary for making requests to the IGDB API.
        Enter the `IGDB Client ID` and `Client Secret` into your `config.py`.

- Setup `Base Folder` Access Restriction: Configure your web server to restrict access to the base folder of your application. This measure is important for security, ensuring that sensitive files and directories are not accessible from the web.

2. **Database URI**: Should point to your newly created database.
3. **IGDB API Keys**: Obtain your keys from [IGDB API Docs](https://api-docs.igdb.com/#getting-started).

### Running the App

- Run the app and register the first user with the email mentioned in `config.py`.
```
python app.py

or on some systems:
python3 app.py
```
- Restart the app. The first user is now an admin.

## 3b. Setup without Mail (NO SMTP)

For a setup without mail:

1. **Create `config.py`**: Copy `config.py.example`.
2. **Database URI**: Should point to your newly created database.

### Initial Configuration

- Run `setup.py` to create an admin user.
- Start the application by running `app.py`.

### Other notes

- Use the admin panel to create any additional users as needed.
- The app runs on port 5001, you can simply change this in app.py

---

Thank you for setting up the Sharewarez App. For further assistance, please open an issue on this repository.

