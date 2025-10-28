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
        -- Ensure global_settings table exists before altering it
        CREATE TABLE IF NOT EXISTS global_settings (
            id SERIAL PRIMARY KEY,
            settings TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            discord_webhook_url VARCHAR(512),
            smtp_server VARCHAR(255),
            smtp_port INTEGER,
            smtp_username VARCHAR(255),
            smtp_password VARCHAR(255),
            smtp_use_tls BOOLEAN DEFAULT TRUE,
            smtp_default_sender VARCHAR(255),
            smtp_last_tested TIMESTAMP,
            smtp_enabled BOOLEAN DEFAULT FALSE,
            discord_bot_name VARCHAR(100),
            discord_bot_avatar_url VARCHAR(512),
            enable_delete_game_on_disk BOOLEAN DEFAULT TRUE,
            igdb_client_id VARCHAR(255),
            igdb_client_secret VARCHAR(255),
            igdb_last_tested TIMESTAMP
        );
        
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

        -- Ensure scan_jobs table exists before altering it
        CREATE TABLE IF NOT EXISTS scan_jobs (
            id SERIAL PRIMARY KEY,
            status VARCHAR(20),
            error_message TEXT,
            is_enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        ALTER TABLE scan_jobs
        ADD COLUMN IF NOT EXISTS removed_count INTEGER DEFAULT 0;

        -- Ensure images table exists before altering it
        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            game_uuid VARCHAR(36),
            image_type VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
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

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS discord_notify_manual_trigger BOOLEAN DEFAULT FALSE;

        -- Add setup state tracking columns to global_settings table
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS setup_in_progress BOOLEAN DEFAULT FALSE;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS setup_current_step INTEGER DEFAULT 1;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS setup_completed BOOLEAN DEFAULT FALSE;

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

        -- Add force_updates_extras setting to scan_jobs table for enhanced scan functionality
        ALTER TABLE scan_jobs
        ADD COLUMN IF NOT EXISTS setting_force_updates_extras BOOLEAN DEFAULT FALSE;

        -- Add 'Cancelled' value to the status_enum for scan_jobs
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'Cancelled' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'status_enum')) THEN
                ALTER TYPE status_enum ADD VALUE 'Cancelled';
            END IF;
        END $$;

        -- Add unique index to prevent duplicate cover images (but allow multiple screenshots)
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = 'unique_game_cover_image' AND n.nspname = 'public'
            ) THEN
                CREATE UNIQUE INDEX unique_game_cover_image 
                ON images (game_uuid) 
                WHERE image_type = 'cover';
            END IF;
        END $$;

        -- Rename columns in filters table from old release group terminology to scanning filter terminology
        DO $$
        BEGIN
            -- Rename rlsgroup to filter_pattern if the old column exists
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='filters' AND column_name='rlsgroup'
            ) THEN
                ALTER TABLE filters RENAME COLUMN rlsgroup TO filter_pattern;
                RAISE NOTICE 'Renamed column rlsgroup to filter_pattern in filters table';
            END IF;

            -- Rename rlsgroupcs to case_sensitive if the old column exists
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='filters' AND column_name='rlsgroupcs'
            ) THEN
                ALTER TABLE filters RENAME COLUMN rlsgroupcs TO case_sensitive;
                RAISE NOTICE 'Renamed column rlsgroupcs to case_sensitive in filters table';
            END IF;
        END $$;

        -- Add attract mode settings to global_settings table
        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS attract_mode_enabled BOOLEAN DEFAULT FALSE;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS attract_mode_idle_timeout INTEGER DEFAULT 60;

        ALTER TABLE global_settings
        ADD COLUMN IF NOT EXISTS attract_mode_settings TEXT;

        -- Create user_attract_mode_settings table if it doesn't exist
        CREATE TABLE IF NOT EXISTS user_attract_mode_settings (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(36) UNIQUE NOT NULL,
            has_customized BOOLEAN DEFAULT FALSE,
            filter_settings TEXT,
            autoplay_settings TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        """
        print("Upgrading database to the latest schema")
        try:
            # Execute the SQL commands in a transaction
            with self.engine.begin() as connection:
                # Parse SQL into proper statements, respecting DO $$ ... END $$ blocks
                statements = self._parse_sql_statements(add_columns_sql)
                for statement in statements:
                    if statement.strip():
                        try:
                            connection.execute(text(statement))
                        except Exception as stmt_error:
                            print(f"Warning: Failed to execute statement: {statement[:100]}...")
                            print(f"Error: {stmt_error}")
                            # Continue with other statements instead of failing completely
                            continue

            # Clean up duplicate discovery sections
            self.cleanup_duplicate_discovery_sections()

            print("Database schema update completed successfully.")
        except Exception as e:
            print(f"An error occurred during schema update: {e}")
            # Don't raise the exception - let the application continue
            print("Application will continue with existing schema...")
        finally:
            # Close the database connection
            self.engine.dispose()

    def cleanup_duplicate_discovery_sections(self):
        """
        Clean up duplicate discovery sections created by conflicting initialization code.
        Removes outdated sections with wrong identifiers (latest, random, popular).
        """
        cleanup_sql = """
        -- Delete outdated discovery sections with wrong identifiers
        DELETE FROM discovery_sections
        WHERE identifier IN ('latest', 'random', 'popular');

        -- Log what was done
        DO $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            IF deleted_count > 0 THEN
                RAISE NOTICE 'Removed % outdated discovery sections', deleted_count;
            END IF;
        END $$;
        """

        print("Cleaning up duplicate discovery sections...")
        try:
            with self.engine.begin() as connection:
                connection.execute(text(cleanup_sql))
                print("Discovery sections cleanup completed successfully.")
        except Exception as e:
            print(f"Warning: Discovery sections cleanup failed: {e}")
            print("Application will continue...")

    def _parse_sql_statements(self, sql_text):
        """
        Parse SQL text into individual statements, properly handling PostgreSQL 
        dollar-quoted blocks like DO $$ ... END $$;
        """
        statements = []
        current_statement = ""
        in_dollar_quote = False
        dollar_tag = ""
        
        lines = sql_text.split('\n')
        
        for line in lines:
            stripped_line = line.strip()
            
            # Skip empty lines and comments
            if not stripped_line or stripped_line.startswith('--'):
                current_statement += line + '\n'
                continue
                
            # Check for start of dollar-quoted block
            if not in_dollar_quote:
                # Look for DO $$ or DO $tag$
                if 'DO $' in stripped_line.upper():
                    # Extract the dollar tag (e.g., $$ or $tag$)
                    import re
                    match = re.search(r'DO\s+(\$[^$]*\$)', stripped_line.upper())
                    if match:
                        dollar_tag = match.group(1)
                        in_dollar_quote = True
                        
            current_statement += line + '\n'
            
            # Check for end of dollar-quoted block
            if in_dollar_quote:
                if dollar_tag in stripped_line and stripped_line.endswith(';'):
                    in_dollar_quote = False
                    dollar_tag = ""
                    # End of DO block, add as complete statement
                    statements.append(current_statement.strip())
                    current_statement = ""
            else:
                # Regular statement ending with semicolon
                if stripped_line.endswith(';'):
                    statements.append(current_statement.strip())
                    current_statement = ""
        
        # Add any remaining statement
        if current_statement.strip():
            statements.append(current_statement.strip())
            
        return [stmt for stmt in statements if stmt.strip()]

# Example of how to use the class
# db_manager = DatabaseManager()
# db_manager.add_column_if_not_exists()
