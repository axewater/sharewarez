# This script creates a user without configuring SMTP

import os, sys
from datetime import datetime
from uuid import uuid4
from sqlalchemy import create_engine, text, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from sqlalchemy.orm.exc import NoResultFound
from flask import Flask
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash
from config import Config
from getpass import getpass

from modules.models import User, db

DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app


parsed_uri = urlparse(DATABASE_URI)

print("Database URI components:")
print(f"Scheme: {parsed_uri.scheme}")
print(f"Username: {parsed_uri.username}")
# can be used for debugging purposes. 
# print(f"Password: {parsed_uri.password}")  
# # Be cautious with printing passwords
print(f"Hostname: {parsed_uri.hostname}")
print(f"Port: {parsed_uri.port}")
print(f"Database Name: {parsed_uri.path[1:]}")  # Removing the leading '/' from the path

redacted_uri = f"{parsed_uri.scheme}://{parsed_uri.username}:*****@{parsed_uri.hostname}:{parsed_uri.port}/{parsed_uri.path[1:]}"
print(f"Redacted URI: {redacted_uri}")


Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(64), nullable=False)
    state = Column(Boolean, default=True)
    about = Column(String(256), unique=True, nullable=True)
    created = Column(DateTime, default=datetime.utcnow)
    lastlogin = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    avatarpath = Column(String(256), default='newstyle/avatar_default.jpg')
    is_email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(256), nullable=True)
    password_reset_token = Column(String(256), nullable=True)
    token_creation_time = Column(DateTime, nullable=True)
    invite_quota = Column(Integer, default=100)

def check_and_create_database(database_uri):
    parsed_uri = urlparse(database_uri)
    db_name = parsed_uri.path[1:]  # Extract database name
    superuser_uri = f"{parsed_uri.scheme}://{parsed_uri.username}:{parsed_uri.password}@{parsed_uri.hostname}:{parsed_uri.port}/postgres"

    engine = create_engine(superuser_uri, isolation_level="AUTOCOMMIT")
    try:
        db_check_uri = f"{parsed_uri.scheme}://{parsed_uri.username}:{parsed_uri.password}@{parsed_uri.hostname}:{parsed_uri.port}/{db_name}"
        if not database_exists(db_check_uri):
            create_database(db_check_uri)
            print(f"Database '{db_name}' created successfully.")
        else:
            user_choice = input(f"Database '{db_name}' already exists. Do you want to delete and start over? (y/n): ")
            if user_choice.lower() == 'y':
                with engine.connect() as conn:
                    # Ensure all connections are terminated
                    conn.execute(text(f"""
                        SELECT pg_terminate_backend(pg_stat_activity.pid)
                        FROM pg_stat_activity
                        WHERE pg_stat_activity.datname = '{db_name}';
                    """))
                    # Drop the database
                    conn.execute(text(f"DROP DATABASE {db_name}"))
                    print(f"Database '{db_name}' dropped.")
                    create_database(db_check_uri)
                    print(f"Database '{db_name}' created successfully.")
            else:
                print("Continuing without modifying the database.")
    except Exception as e:
        print(f"Failed to check or create the database. Error details: {e}")
        sys.exit(1)






def create_admin_user(database_uri, app):
    with app.app_context():
        check_and_create_database(database_uri)
    
        engine = create_engine(database_uri)
        Base.metadata.bind = engine
        DBSession = sessionmaker(bind=engine)
        session = scoped_session(DBSession)

        # Create tables if they don't exist
        Base.metadata.create_all(engine)


        try:
            # Check if can connect to database
            engine.connect()
        except Exception as e:
            print("Database connection failed. Edit the database URI in setup.py.")
            print("Error details:", e)
            return
        print("Database connection successful.")
        # Check if the admin user already exists
        username = input("Enter admin username: ")
        try:
            existing_user = session.query(User).filter_by(name=username).one()
            # If the following line is executed, it means the user was found, so we print a message and return.
            print(f"User '{username}' already exists. No action taken.")
            return
        except NoResultFound:
            # If no result found, it means the user does not exist, and we can proceed to create a new one.
            pass

        # Prompt for admin credentials
        password = getpass("Enter admin password: ")  # Securely capture password without echoing
        hashed_password = generate_password_hash(password)

        # Create and insert the admin user
        admin_user = User(
            name=username,
            email="nosmtp@setup.now",
            password_hash=hashed_password,
            role="admin",
            state=True,
            is_email_verified=True,
            about="Auto-generated admin account"
        )
        session.add(admin_user)

        try:
            session.commit()
            print("Admin user created successfully.")
        except Exception as e:
            session.rollback()
            print("Failed to create admin user. Error details:", e)
        finally:
            session.remove()


if __name__ == '__main__':
    app = create_app()
    DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI
    create_admin_user(DATABASE_URI, app)
