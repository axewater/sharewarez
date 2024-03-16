import os, socket, time
from datetime import datetime
from uuid import uuid4
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session  # Updated import here
from werkzeug.security import generate_password_hash
from urllib.parse import urlparse

# Editable database URI
#DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://sharewarez:!Piratingin2024!@localhost/sharewarez')
from config import Config
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



def check_postgres_port_open(host, port, retries=5, delay=2):
    """
    Checks if the PostgreSQL port is open by attempting to create a socket connection.
    If the connection attempt fails, it waits for 'delay' seconds and retries.
    
    :param host: The hostname or IP address of the PostgreSQL server.
    :param port: The port number of the PostgreSQL server.
    :param retries: Maximum number of retries.
    :param delay: Delay in seconds between retries.
    :return: True if the port is open, False otherwise.
    """
    for attempt in range(retries):
        try:
            with socket.create_connection((host, port), timeout=10):
                print(f"Connection to PostgreSQL on port {port} successful.")
                return True
        except (socket.timeout, ConnectionRefusedError):
            print(f"Connection to PostgreSQL on port {port} failed. Attempt {attempt + 1} of {retries}.")
            time.sleep(delay)
    return False

def create_admin_user():
    parsed_url = urlparse(DATABASE_URI)
    check_postgres_port_open(parsed_url.hostname, 5432, 60, 2);

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

    # Check if the admin user already exists
    existing_admin_user = session.query(User).filter_by(role="admin").first()
    if existing_admin_user:
        print("Admin user already exists. No action taken.")
        return  # Stop the function if an admin user already exists

    username = os.getenv('APP_USERNAME', 'admin')
    password = os.getenv('APP_PASSWORD', 'admin')
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
    print(DATABASE_URI)
    create_admin_user()
