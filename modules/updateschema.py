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
        add_columns_sql = f"""
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS enable_delete_game_on_disk BOOLEAN DEFAULT TRUE;
        
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS site_url VARCHAR(255) DEFAULT 'http://127.0.0.1:5001';

        ALTER TABLE invite_tokens
        ADD COLUMN IF NOT EXISTS used_by VARCHAR(36);

        ALTER TABLE invite_tokens
        ADD COLUMN IF NOT EXISTS used_at TIMESTAMP;

        ALTER TABLE invite_tokens
        ADD COLUMN IF NOT EXISTS recipient_email VARCHAR(120);

        ALTER TABLE user_preferences
        ADD COLUMN IF NOT EXISTS theme VARCHAR(50) DEFAULT 'default';
        
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS enable_main_game_updates BOOLEAN DEFAULT TRUE;
        
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS enable_game_updates BOOLEAN DEFAULT TRUE;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS update_folder_name VARCHAR(255) DEFAULT 'updates';
        
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS enable_game_extras BOOLEAN DEFAULT TRUE;
        
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS extras_folder_name VARCHAR(255) DEFAULT 'extras';

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS discord_notify_new_games BOOLEAN DEFAULT FALSE;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS discord_notify_game_updates BOOLEAN DEFAULT FALSE;
        
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS discord_notify_game_extras BOOLEAN DEFAULT FALSE;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS discord_notify_downloads BOOLEAN DEFAULT FALSE;
        
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS discord_webhook_url VARCHAR(255);
            
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS smtp_server VARCHAR(255);

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS smtp_port INTEGER;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS smtp_username VARCHAR(255);

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS smtp_password VARCHAR(255);

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS smtp_use_tls BOOLEAN DEFAULT TRUE;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS smtp_default_sender VARCHAR(255);

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS smtp_last_tested TIMESTAMP;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS smtp_enabled BOOLEAN DEFAULT FALSE;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS discord_bot_name VARCHAR(255);
        
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS discord_bot_avatar_url VARCHAR(255);

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS igdb_client_id VARCHAR(255);

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS igdb_client_secret VARCHAR(255);

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS igdb_last_tested TIMESTAMP;

        ALTER TABLE libraries
        ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;

        ALTER TABLE download_requests
        ADD COLUMN IF NOT EXISTS file_location VARCHAR(255);
        
        ALTER TABLE games
        ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP;

        -- Create allowed_file_types table if it doesn't exist
        CREATE TABLE IF NOT EXISTS allowed_file_types (
            id SERIAL PRIMARY KEY,
            value VARCHAR(10) UNIQUE NOT NULL
        );

        -- Create ignored_file_types table if it doesn't exist
        CREATE TABLE IF NOT EXISTS ignored_file_types (
            id SERIAL PRIMARY KEY,
            value VARCHAR(10) UNIQUE NOT NULL
        );

        -- Create user_favorites table if it doesn't exist
        CREATE TABLE IF NOT EXISTS user_favorites (
            user_id INTEGER REFERENCES users(id),
            game_uuid VARCHAR(36) REFERENCES games(uuid),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, game_uuid)
        );

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

        CREATE TABLE IF NOT EXISTS game_extras (
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
            
            # Initialize default values for allowed file types
            try:
                with self.engine.connect() as connection:
                    # Check if allowed_file_types table is empty
                    result = connection.execute(text("SELECT COUNT(*) FROM allowed_file_types")).scalar()
                    if result == 0:
                        # Insert default allowed file types from Config
                        for file_type in Config.ALLOWED_FILE_TYPES:
                            connection.execute(
                                text("INSERT INTO allowed_file_types (value) VALUES (:value) ON CONFLICT DO NOTHING"),
                                {"value": file_type}
                            )
                    
                    connection.commit()
                print("Default file types initialized successfully.")
            except Exception as e:
                print(f"An error occurred while initializing default file types: {e}")
                raise
        except Exception as e:
            print(f"An error occurred: {e}")
            raise  # Re-raise the exception to propagate it
        finally:
            # Close the database connection
            self.engine.dispose()

# Example of how to use the class
# db_manager = DatabaseManager()
# db_manager.add_column_if_not_exists()
