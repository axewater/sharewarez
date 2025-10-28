# File: /modules/utils_hltb.py
# This file contains functions for interacting with HowLongToBeat API

import time
import threading
from datetime import datetime, timezone
from flask import current_app
from modules import db
from modules.models import GlobalSettings, Game
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from config import Config

try:
    from howlongtobeatpy import HowLongToBeat
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    HLTB_AVAILABLE = True
except ImportError:
    HLTB_AVAILABLE = False
    print("Warning: howlongtobeatpy library not installed. HLTB integration disabled.")


class HLTBRateLimiter:
    """
    Rate limiter for HowLongToBeat API operations.
    Ensures respectful usage of HLTB servers with configurable delay between requests.
    """
    def __init__(self, delay_seconds=2.0):
        self.delay_seconds = delay_seconds
        self.last_request_time = 0
        self.lock = threading.Lock()

    def acquire(self):
        """Acquire permission to make an HLTB API request."""
        with self.lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time

            if time_since_last_request < self.delay_seconds:
                sleep_time = self.delay_seconds - time_since_last_request
                time.sleep(sleep_time)

            self.last_request_time = time.time()

    def update_delay(self, new_delay):
        """Update the rate limit delay."""
        with self.lock:
            self.delay_seconds = new_delay


# Global rate limiter instance
_rate_limiter = None

def get_rate_limiter():
    """Get or create the global HLTB rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        # Get delay from settings - use direct session to avoid app context issues
        try:
            settings = db.session.execute(select(GlobalSettings)).scalars().first()
            delay = settings.hltb_rate_limit_delay if settings else 2.0
        except:
            # Fallback to direct engine connection
            engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()
            try:
                settings = session.execute(select(GlobalSettings)).scalars().first()
                delay = settings.hltb_rate_limit_delay if settings else 2.0
            except:
                delay = 2.0
            finally:
                session.close()
                engine.dispose()

        _rate_limiter = HLTBRateLimiter(delay_seconds=delay)
    return _rate_limiter


async def fetch_hltb_data(game_name):
    """
    Search HowLongToBeat for a game by name.

    Parameters:
    game_name (str): The name of the game to search for.

    Returns:
    dict: HLTB data or None if not found. Format:
        {
            'hltb_id': int,
            'game_name': str,
            'main_story': float,
            'main_extra': float,
            'completionist': float,
            'all_styles': float
        }
    """
    if not HLTB_AVAILABLE:
        print("HLTB library not available")
        return None

    if not game_name:
        print("No game name provided for HLTB search")
        return None

    # Create a new database session for this thread
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Check if HLTB integration is enabled
        settings = session.execute(select(GlobalSettings)).scalars().first()
        if not settings or not settings.enable_hltb_integration:
            return None

        # Respect rate limiting
        rate_limiter = get_rate_limiter()
        rate_limiter.acquire()

        # Search HLTB
        results = await HowLongToBeat().async_search(game_name)

        if not results or len(results) == 0:
            print(f"No HLTB results found for '{game_name}'")
            return None

        # Take the first (best) match
        best_match = results[0]

        # Extract data
        hltb_data = {
            'hltb_id': best_match.game_id,
            'game_name': best_match.game_name,
            'main_story': best_match.main_story if best_match.main_story > 0 else None,
            'main_extra': best_match.main_extra if best_match.main_extra > 0 else None,
            'completionist': best_match.completionist if best_match.completionist > 0 else None,
            'all_styles': best_match.all_styles if best_match.all_styles > 0 else None
        }

        print(f"HLTB data found for '{game_name}': {hltb_data}")
        return hltb_data

    except Exception as e:
        print(f"Error fetching HLTB data for '{game_name}': {e}")
        return None
    finally:
        session.close()
        engine.dispose()


def store_hltb_data(game_uuid, hltb_data):
    """
    Store HLTB data in the database for a game.

    Parameters:
    game_uuid (str): The UUID of the game.
    hltb_data (dict): HLTB data from fetch_hltb_data().

    Returns:
    bool: True if successful, False otherwise.
    """
    if not hltb_data:
        return False

    # Create a new database session for this thread
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        game = session.execute(
            select(Game).where(Game.uuid == game_uuid)
        ).scalars().first()

        if not game:
            print(f"Game not found with UUID: {game_uuid}")
            return False

        # Update HLTB fields
        game.hltb_id = hltb_data.get('hltb_id')
        game.hltb_main_story = hltb_data.get('main_story')
        game.hltb_main_extra = hltb_data.get('main_extra')
        game.hltb_completionist = hltb_data.get('completionist')
        game.hltb_all_styles = hltb_data.get('all_styles')
        game.hltb_last_updated = datetime.now(timezone.utc)

        session.commit()
        print(f"HLTB data stored for game '{game.name}' (UUID: {game_uuid})")
        return True

    except Exception as e:
        print(f"Error storing HLTB data for game {game_uuid}: {e}")
        session.rollback()
        return False
    finally:
        session.close()
        engine.dispose()


async def update_game_hltb(game_uuid, game_name=None):
    """
    Fetch and store HLTB data for a game in one operation.

    Parameters:
    game_uuid (str): The UUID of the game.
    game_name (str, optional): The name of the game. If not provided, will be fetched from DB.

    Returns:
    bool: True if successful, False otherwise.
    """
    # Create a new database session for this thread
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Get game name if not provided
        if not game_name:
            game = session.execute(
                select(Game).where(Game.uuid == game_uuid)
            ).scalars().first()

            if not game:
                print(f"Game not found with UUID: {game_uuid}")
                return False

            game_name = game.name

        # Fetch HLTB data
        hltb_data = await fetch_hltb_data(game_name)

        if not hltb_data:
            return False

        # Store in database
        return store_hltb_data(game_uuid, hltb_data)

    except Exception as e:
        print(f"Error updating HLTB for game {game_uuid}: {e}")
        return False
    finally:
        session.close()
        engine.dispose()


def get_games_without_hltb(limit=None):
    """
    Get games that don't have HLTB data yet.

    Parameters:
    limit (int, optional): Maximum number of games to return.

    Returns:
    list: List of Game objects without HLTB data.
    """
    # Try to use Flask app context first (for API calls)
    try:
        games = db.session.execute(select(Game).where(Game.hltb_id.is_(None)).limit(limit) if limit else select(Game).where(Game.hltb_id.is_(None))).scalars().all()
        return games
    except:
        # Fallback to direct session (for standalone scripts)
        engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        try:
            query = select(Game).where(Game.hltb_id.is_(None))
            if limit:
                query = query.limit(limit)
            games = session.execute(query).scalars().all()
            return games
        except Exception as e:
            print(f"Error fetching games without HLTB data: {e}")
            return []
        finally:
            session.close()
            engine.dispose()


def get_hltb_stats():
    """
    Get statistics about HLTB data coverage.

    Returns:
    dict: Statistics including total games, games with HLTB data, percentage coverage.
    """
    # Try to use Flask app context first (for API calls)
    try:
        total_games = db.session.execute(select(db.func.count(Game.id))).scalar()
        games_with_hltb = db.session.execute(select(db.func.count(Game.id)).where(Game.hltb_id.isnot(None))).scalar()
        coverage_percentage = (games_with_hltb / total_games * 100) if total_games > 0 else 0

        return {
            'total_games': total_games,
            'games_with_hltb': games_with_hltb,
            'games_without_hltb': total_games - games_with_hltb,
            'coverage_percentage': round(coverage_percentage, 2)
        }
    except:
        # Fallback to direct session (for standalone scripts)
        engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        try:
            total_games = session.execute(select(db.func.count(Game.id))).scalar()
            games_with_hltb = session.execute(select(db.func.count(Game.id)).where(Game.hltb_id.isnot(None))).scalar()
            coverage_percentage = (games_with_hltb / total_games * 100) if total_games > 0 else 0

            return {
                'total_games': total_games,
                'games_with_hltb': games_with_hltb,
                'games_without_hltb': total_games - games_with_hltb,
                'coverage_percentage': round(coverage_percentage, 2)
            }
        except Exception as e:
            print(f"Error calculating HLTB stats: {e}")
            return {
                'total_games': 0,
                'games_with_hltb': 0,
                'games_without_hltb': 0,
                'coverage_percentage': 0
            }
        finally:
            session.close()
            engine.dispose()


# Helper function to run async code in a separate thread (ASGI-safe)
def _run_async_in_thread(coro):
    """
    Run an async coroutine in a separate thread with its own event loop.
    This is safe to call from ASGI/Flask contexts.
    """
    def _run():
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result()


# Synchronous wrappers for use in non-async contexts
def update_game_hltb_sync(game_uuid, game_name=None):
    """
    Synchronous wrapper for update_game_hltb.
    Fetches and stores HLTB data for a game.

    Parameters:
    game_uuid (str): The UUID of the game.
    game_name (str, optional): The name of the game.

    Returns:
    bool: True if successful, False otherwise.
    """
    if not HLTB_AVAILABLE:
        return False

    try:
        # Run async code in a separate thread to avoid event loop conflicts
        return _run_async_in_thread(update_game_hltb(game_uuid, game_name))

    except Exception as e:
        print(f"Error in sync HLTB update for game {game_uuid}: {e}")
        return False


def fetch_hltb_data_sync(game_name):
    """
    Synchronous wrapper for fetch_hltb_data.
    Searches HowLongToBeat for a game by name.

    Parameters:
    game_name (str): The name of the game to search for.

    Returns:
    dict: HLTB data or None if not found.
    """
    if not HLTB_AVAILABLE:
        return None

    try:
        # Run async code in a separate thread to avoid event loop conflicts
        return _run_async_in_thread(fetch_hltb_data(game_name))

    except Exception as e:
        print(f"Error in sync HLTB fetch for '{game_name}': {e}")
        return None
