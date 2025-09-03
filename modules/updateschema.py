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

        # SQL commands to add new columns and tables
        add_columns_sql = f"""       
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS site_url VARCHAR(255) DEFAULT 'http://127.0.0.1:5006';

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

        -- Create allowed_file_types table if it doesn't exist
        CREATE TABLE IF NOT EXISTS allowed_file_types (
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

        -- Create system_events table if it doesn't exist
        CREATE TABLE IF NOT EXISTS system_events (
            id SERIAL PRIMARY KEY,
            event_type VARCHAR(32) DEFAULT 'log',
            event_text VARCHAR(256) NOT NULL,
            event_level VARCHAR(32) DEFAULT 'information',
            audit_user INTEGER REFERENCES users(id),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        ALTER TABLE scan_jobs
        ADD COLUMN IF NOT EXISTS removed_count INTEGER DEFAULT 0;

        -- Add new columns to images table for optimized image downloading
        ALTER TABLE images
        ADD COLUMN IF NOT EXISTS igdb_image_id VARCHAR(255);

        ALTER TABLE images
        ADD COLUMN IF NOT EXISTS download_url VARCHAR(500);

        ALTER TABLE images
        ADD COLUMN IF NOT EXISTS is_downloaded BOOLEAN DEFAULT FALSE;

        -- Add image download settings to global_settings table
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS use_turbo_image_downloads BOOLEAN DEFAULT TRUE;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS turbo_download_threads INTEGER DEFAULT 8;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS turbo_download_batch_size INTEGER DEFAULT 200;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS scan_thread_count INTEGER DEFAULT 1;

        -- Add setting_download_missing_images column to scan_jobs table
        ALTER TABLE scan_jobs
        ADD COLUMN IF NOT EXISTS setting_download_missing_images BOOLEAN DEFAULT FALSE;

        -- Change error_message column from varchar(512) to text for longer error messages
        ALTER TABLE scan_jobs
        ALTER COLUMN error_message TYPE TEXT;

        -- Add progress tracking columns to scan_jobs table for scan optimization
        ALTER TABLE scan_jobs
        ADD COLUMN IF NOT EXISTS current_processing VARCHAR(255);

        ALTER TABLE scan_jobs
        ADD COLUMN IF NOT EXISTS last_progress_update TIMESTAMP;
        
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
