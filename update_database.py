import os
from sqlalchemy import create_engine, text
from config import Config

# Load database configuration from Config
database_uri = Config.SQLALCHEMY_DATABASE_URI

# Create SQLAlchemy engine
engine = create_engine(database_uri)

# SQL command to add the new column
add_column_sql = """
ALTER TABLE global_settings
ADD COLUMN IF NOT EXISTS enable_delete_game_on_disk BOOLEAN DEFAULT TRUE;
"""

try:
    # Execute the SQL command
    with engine.connect() as connection:
        connection.execute(text(add_column_sql))
        connection.commit()
    print("Column 'enable_delete_game_on_disk' added successfully to 'global_settings' table.")
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    # Close the database connection
    engine.dispose()
