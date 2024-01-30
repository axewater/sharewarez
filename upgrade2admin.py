# upgrade_to_admin_standalone.py

import os
from sqlalchemy import create_engine, inspect, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True)
    email = Column(String(120), unique=True)
    password_hash = Column(String(128))
    role = Column(String(64))
    state = Column(Boolean)
    about = Column(String(64), unique=True)
    created = Column(DateTime)
    lastlogin = Column(DateTime)
    user_id = Column(String(36), unique=True)
    avatarpath = Column(String(256))
    is_email_verified = Column(Boolean)
    email_verification_token = Column(String(256))
    password_reset_token = Column(String(256))
    token_creation_time = Column(DateTime)

DATABASE_URI = 'sqlite:///app.db'

engine = create_engine(DATABASE_URI)
Base.metadata.bind = engine

Session = sessionmaker(bind=engine)
session = Session()
print("Database successfully loaded.")

try:
    # Inspect the database and list all tables
    inspector = inspect(engine)
    print("Tables in the database:", inspector.get_table_names())

    user = session.query(User).first()
    if user:
        print(f"User found: '{user.name}' with current role '{user.role}'.")
        confirmation = input("Do you want to upgrade this user to site administrator? (yes/no): ").strip().lower()
        if confirmation == 'yes':
            user.role = 'admin'
            session.commit()
            print(f"User '{user.name}' has been upgraded to admin.")
        else:
            print("Operation canceled. No changes made.")
    else:
        print("No user found in the database.")

except SQLAlchemyError as e:
    print(f"An error occurred: {e}")
    session.rollback()
finally:
    session.close()

if __name__ == '__main__':
    pass
