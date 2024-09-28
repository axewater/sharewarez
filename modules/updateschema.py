import os
from sqlalchemy import create_engine, text
from config import Config

class DatabaseManager:
    def __init__(self):
        # Load the database configuration from Config
        self.database_uri = Config.SQLALCHEMY_DATABASE_URI
        # Create a SQLAlchemy engine
        self.engine = create_engine(self.database_uri)

    def add_column_if_not_exists(self):
        # SQL commands to add new columns
        add_columns_sql = """
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS enable_delete_game_on_disk BOOLEAN DEFAULT TRUE;

        ALTER TABLE invite_tokens
        ADD COLUMN IF NOT EXISTS used_by VARCHAR(36);

        ALTER TABLE invite_tokens
        ADD COLUMN IF NOT EXISTS used_at TIMESTAMP;

        ALTER TABLE user_preferences
        ADD COLUMN IF NOT EXISTS theme VARCHAR(50) DEFAULT 'default';
        """
        print("Upgrading database to the latest schema")
        try:
            # Execute the SQL commands
            with self.engine.connect() as connection:
                connection.execute(text(add_columns_sql))
                connection.commit()
            print("Columns successfully added to the tables.")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            # Close the database connection
            self.engine.dispose()

# Example of how to use the class
# db_manager = DatabaseManager()
# db_manager.add_column_if_not_exists()
