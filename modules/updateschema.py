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
        # First, remove the invited_by column and its foreign key constraint
        remove_invited_by_sql = """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'users_invited_by_fkey'
            ) THEN
                ALTER TABLE users DROP CONSTRAINT users_invited_by_fkey;
            END IF;
            
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'invited_by'
            ) THEN
                ALTER TABLE users DROP COLUMN invited_by;
            END IF;
        END $$;
        """

        # SQL commands to add new columns and tables
        add_columns_sql = """
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS enable_delete_game_on_disk BOOLEAN DEFAULT TRUE;

        ALTER TABLE invite_tokens
        ADD COLUMN IF NOT EXISTS used_by VARCHAR(36);

        ALTER TABLE invite_tokens
        ADD COLUMN IF NOT EXISTS used_at TIMESTAMP;

        ALTER TABLE user_preferences
        ADD COLUMN IF NOT EXISTS theme VARCHAR(50) DEFAULT 'default';

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS update_folder_name VARCHAR(255) DEFAULT 'updates';

        CREATE TABLE IF NOT EXISTS game_updates (
            id SERIAL PRIMARY KEY,
            uuid VARCHAR(36) UNIQUE NOT NULL,
            game_uuid VARCHAR(36) NOT NULL,
            times_downloaded INTEGER DEFAULT 0,
            nfo_content TEXT,
            file_path VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (game_uuid) REFERENCES games(uuid) ON DELETE CASCADE
        );

        -- Add uuid column to game_updates table if it doesn't exist
        ALTER TABLE game_updates
        ADD COLUMN IF NOT EXISTS uuid VARCHAR(36) UNIQUE NOT NULL DEFAULT 1111-1111-1111-1111;
        
        """
        print("Upgrading database to the latest schema")
        try:
            # Execute the SQL commands
            with self.engine.connect() as connection:
                connection.execute(text(add_columns_sql))
                connection.commit()
            print("Columns and tables successfully added to the database.")
        except Exception as e:
            print(f"An error occurred: {e}")
            raise  # Re-raise the exception to propagate it
        finally:
            # Close the database connection
            self.engine.dispose()

# Example of how to use the class
# db_manager = DatabaseManager()
# db_manager.add_column_if_not_exists()
