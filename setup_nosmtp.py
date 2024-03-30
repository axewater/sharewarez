# This script creates a user without configuring SMTP

import os, sys
from datetime import datetime
from uuid import uuid4
from sqlalchemy import create_engine, text, Column, Integer, String, Boolean, DateTime
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session  # Updated import here
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash
from config import Config
from getpass import getpass

DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI

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



def create_admin_user(database_uri):
    check_and_create_database(database_uri)

    engine = create_engine(DATABASE_URI)
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

    # Prompt for admin credentials
    username = input("Enter admin username: ")
    password = input("Enter admin password: ")
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
    DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI
    create_admin_user(DATABASE_URI)
