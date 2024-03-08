0.
For Windows :
Microsoft Visual C++ 14.0 or greater is required. Get it with "Microsoft C++ Build Tools": https://visualstudio.microsoft.com/visual-cpp-build-tools/


1.
setup your virtual environment :
python -m venv venv
python -m pip install -r requirements.txt
.\venv\Scripts\Activate 


2.
install postgresql
create database:
    psql -U postgres -h localhost
    CREATE DATABASE sharewarez;

3a.
Setup with mail features enabled :

create config.py (copy config.py.example), INITIAL_WHITELIST should contain admin email !
database URI should point to your new database
to get IGDB API keys, go here : https://api-docs.igdb.com/#getting-started


run app
register 1st user with email from config
restart app
1st user is now admin

---------------------------------------------------------------------------

3b.
Setup without mail (NO SMTP)

create config.py (copy config.py.example)
database URI should point to your new database
run setup.py
create admin user
run app.py

create any additional users in admin panel