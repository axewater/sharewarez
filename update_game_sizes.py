# this is a migration script for users coming from version 1.2.1
# use at your own risk as I did not get a chance to fully test this (my data was already updated)

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from modules.models import Game
from modules.functions import get_folder_size_in_bytes
from config import Config

def update_game_sizes():
    # Create database engine and session
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Fetch all games from the database
        games = session.query(Game).all()
        total_games = len(games)
        updated_count = 0

        print(f"Found {total_games} games in the database.")

        for index, game in enumerate(games, 1):
            print(f"Processing game {index}/{total_games}: {game.name}")

            if game.full_disk_path and os.path.exists(game.full_disk_path):
                new_size = get_folder_size_in_bytes(game.full_disk_path)
                
                if game.size != new_size:
                    game.size = new_size
                    updated_count += 1
                    print(f"Updated size for {game.name}: {new_size} bytes")
                else:
                    print(f"Size unchanged for {game.name}")
            else:
                print(f"Warning: Path not found for {game.name}: {game.full_disk_path}")

        # Commit the changes to the database
        session.commit()
        print(f"Update complete. {updated_count} games were updated.")

    except Exception as e:
        print(f"An error occurred: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    update_game_sizes()
