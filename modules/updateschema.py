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
        # SQL command to add a new column
        add_column_sql = """
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS enable_delete_game_on_disk BOOLEAN DEFAULT TRUE;
        """
        print("Upgrading database to the latest schema")
        try:
            # Execute the SQL command
            with self.engine.connect() as connection:
                connection.execute(text(add_column_sql))
                connection.commit()
            print("Column 'enable_delete_game_on_disk' successfully added to the 'global_settings' table.")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            # Close the database connection
            self.engine.dispose()

# Example of how to use the class
# db_manager = DatabaseManager()
# db_manager.add_column_if_not_exists()
