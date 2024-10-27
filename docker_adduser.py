import os, sys, socket, time
from datetime import datetime
from uuid import uuid4
from sqlalchemy import create_engine, text, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from werkzeug.security import generate_password_hash
from urllib.parse import urlparse
from config import Config
from sqlalchemy.orm.exc import NoResultFound
from flask import Flask

from modules.models import User, db

# Load environment variables
SHAREWAREZ_USERNAME = os.getenv('SHAREWAREZ_USERNAME', 'admin')
SHAREWAREZ_PASSWORD = os.getenv('SHAREWAREZ_PASSWORD', 'admindocker')

# Setup Database URI from config
config = Config()
DATABASE_URI = config.SQLALCHEMY_DATABASE_URI

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

def check_postgres_port_open(host, port, retries=5, delay=2):
    for attempt in range(retries):
        try:
            with socket.create_connection((host, port), timeout=10):
                print(f"Connection to PostgreSQL on port {port} successful.")
                return True
        except (socket.timeout, ConnectionRefusedError):
            print(f"Connection attempt {attempt + 1} of {retries}. Retrying in {delay} seconds...")
            time.sleep(delay)
    print("Failed to connect to PostgreSQL after multiple attempts.")
    return False

def create_admin_user(database_uri):
    parsed_uri = urlparse(database_uri)
    # Ensure the database server is accessible
    if not check_postgres_port_open(parsed_uri.hostname, parsed_uri.port or 5432):
        print("Exiting due to database connectivity issues.")
        return

    engine = create_engine(database_uri)
    Base.metadata.bind = engine
    DBSession = sessionmaker(bind=engine)
    session = scoped_session(DBSession)

    # Create tables if they don't exist
    Base.metadata.create_all(engine)

    # Check if the admin user already exists
    existing_user = session.query(User).filter_by(name=SHAREWAREZ_USERNAME).first()
    if existing_user:
        print("Admin user already exists. No action taken.")
        return

    # Create and insert the admin user
    hashed_password = generate_password_hash(SHAREWAREZ_PASSWORD)
    admin_user = User(
        name=SHAREWAREZ_USERNAME,
        email="admin@sharewarez.com",  # Assuming a placeholder email
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
    create_admin_user(DATABASE_URI)
