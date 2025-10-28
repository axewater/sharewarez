#!/usr/bin/env python3
"""
SharewareZ Game Path Update Script

This script helps update game paths in the database after extracting archives or reorganizing files.
It preserves all metadata (favorites, ratings, downloads, etc.) while fixing broken paths.

Usage:
    python update_game_paths.py                    # Interactive mode
    python update_game_paths.py --dry-run          # Preview changes without applying
    python update_game_paths.py --auto             # Auto-fix obvious matches
    python update_game_paths.py --library "PC"     # Filter by library name
"""

import os
import sys
import argparse
from difflib import SequenceMatcher
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from config import Config
from modules.models import Game, Library

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def similarity_ratio(str1, str2):
    """Calculate similarity ratio between two strings (0-1)"""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def find_similar_paths(original_path, threshold=0.6):
    """
    Find similar paths in the parent directory of the original path.
    Returns list of (path, similarity_score) tuples.
    """
    if not original_path or not os.path.exists(os.path.dirname(original_path)):
        return []

    parent_dir = os.path.dirname(original_path)
    original_name = os.path.basename(original_path)

    similar_paths = []

    try:
        for item in os.listdir(parent_dir):
            item_path = os.path.join(parent_dir, item)

            # Skip if it's the same path or doesn't exist
            if item_path == original_path or not os.path.exists(item_path):
                continue

            # Calculate similarity
            similarity = similarity_ratio(original_name, item)

            # Check for common extraction patterns
            # e.g., "game.rar" -> "game" or "game_extracted"
            if similarity >= threshold:
                similar_paths.append((item_path, similarity))

            # Also check if the item contains the original name (case insensitive)
            elif original_name.lower() in item.lower() or item.lower() in original_name.lower():
                similar_paths.append((item_path, 0.5 + similarity * 0.5))

    except (PermissionError, OSError) as e:
        print(f"{Colors.WARNING}Warning: Cannot access directory {parent_dir}: {e}{Colors.ENDC}")
        return []

    # Sort by similarity (highest first)
    similar_paths.sort(key=lambda x: x[1], reverse=True)

    return similar_paths

def check_single_file_in_folder(folder_path):
    """
    Check if a folder contains exactly one file (common after extraction).
    Returns the file path if found, None otherwise.
    """
    if not os.path.isdir(folder_path):
        return None

    try:
        items = os.listdir(folder_path)
        files = [item for item in items if os.path.isfile(os.path.join(folder_path, item))]

        if len(files) == 1:
            return os.path.join(folder_path, files[0])
    except (PermissionError, OSError):
        pass

    return None

def validate_game_paths(session, library_filter=None):
    """
    Validate all game paths and return lists of valid and invalid games.
    """
    query = select(Game)

    if library_filter:
        library = session.execute(
            select(Library).where(Library.name.ilike(f"%{library_filter}%"))
        ).scalar_one_or_none()

        if not library:
            print(f"{Colors.FAIL}Error: No library found matching '{library_filter}'{Colors.ENDC}")
            return [], []

        query = query.where(Game.library_uuid == library.uuid)
        print(f"{Colors.OKBLUE}Filtering by library: {library.name}{Colors.ENDC}\n")

    games = session.execute(query).scalars().all()

    valid_games = []
    invalid_games = []

    for game in games:
        if game.full_disk_path and os.path.exists(game.full_disk_path):
            valid_games.append(game)
        else:
            invalid_games.append(game)

    return valid_games, invalid_games

def suggest_path_fix(game):
    """
    Suggest a new path for a game with a broken path.
    Returns (suggested_path, confidence_score) or (None, 0) if no suggestion.
    """
    if not game.full_disk_path:
        return None, 0

    # Find similar paths
    similar_paths = find_similar_paths(game.full_disk_path, threshold=0.6)

    if not similar_paths:
        return None, 0

    # Return the most similar path
    suggested_path, confidence = similar_paths[0]

    return suggested_path, confidence

def update_game_path(session, game, new_path, dry_run=False):
    """
    Update a game's path in the database.
    Returns True if successful, False otherwise.
    """
    if dry_run:
        print(f"{Colors.OKCYAN}[DRY RUN] Would update path for '{game.name}'{Colors.ENDC}")
        print(f"  Old: {game.full_disk_path}")
        print(f"  New: {new_path}")
        return True

    try:
        old_path = game.full_disk_path
        game.full_disk_path = new_path
        session.commit()

        print(f"{Colors.OKGREEN}✓ Updated '{game.name}'{Colors.ENDC}")
        print(f"  Old: {old_path}")
        print(f"  New: {new_path}")
        return True

    except Exception as e:
        session.rollback()
        print(f"{Colors.FAIL}✗ Error updating '{game.name}': {e}{Colors.ENDC}")
        return False

def interactive_mode(session, invalid_games, dry_run=False):
    """
    Interactive mode - prompt user for each broken path.
    """
    updated_count = 0
    skipped_count = 0
    failed_count = 0

    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}Interactive Path Update Mode{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

    for idx, game in enumerate(invalid_games, 1):
        print(f"\n{Colors.BOLD}[{idx}/{len(invalid_games)}] Game: {game.name}{Colors.ENDC}")
        print(f"  Library: {game.library.name if game.library else 'Unknown'}")
        print(f"  Current path: {Colors.FAIL}{game.full_disk_path}{Colors.ENDC}")

        # Suggest a fix
        suggested_path, confidence = suggest_path_fix(game)

        if suggested_path:
            print(f"  Suggested path: {Colors.OKGREEN}{suggested_path}{Colors.ENDC}")
            print(f"  Confidence: {confidence:.0%}")

            while True:
                choice = input(f"\n  Update to suggested path? [y/n/s/q] (y=yes, n=no, s=skip all, q=quit): ").lower().strip()

                if choice == 'y':
                    if update_game_path(session, game, suggested_path, dry_run):
                        updated_count += 1
                    else:
                        failed_count += 1
                    break
                elif choice == 'n':
                    # Allow manual path entry
                    manual_path = input("  Enter new path (or press Enter to skip): ").strip()
                    if manual_path:
                        if os.path.exists(manual_path):
                            if update_game_path(session, game, manual_path, dry_run):
                                updated_count += 1
                            else:
                                failed_count += 1
                        else:
                            print(f"{Colors.WARNING}  Path does not exist. Skipping.{Colors.ENDC}")
                            skipped_count += 1
                    else:
                        skipped_count += 1
                    break
                elif choice == 's':
                    print(f"{Colors.WARNING}  Skipping all remaining games.{Colors.ENDC}")
                    skipped_count += len(invalid_games) - idx + 1
                    return updated_count, skipped_count, failed_count
                elif choice == 'q':
                    print(f"{Colors.WARNING}  Quitting.{Colors.ENDC}")
                    return updated_count, skipped_count, failed_count
                else:
                    print(f"{Colors.FAIL}  Invalid choice. Please enter y, n, s, or q.{Colors.ENDC}")
        else:
            print(f"  {Colors.WARNING}No automatic suggestion found.{Colors.ENDC}")
            manual_path = input("  Enter new path (or press Enter to skip): ").strip()

            if manual_path:
                if os.path.exists(manual_path):
                    if update_game_path(session, game, manual_path, dry_run):
                        updated_count += 1
                    else:
                        failed_count += 1
                else:
                    print(f"{Colors.WARNING}  Path does not exist. Skipping.{Colors.ENDC}")
                    skipped_count += 1
            else:
                skipped_count += 1

    return updated_count, skipped_count, failed_count

def auto_mode(session, invalid_games, dry_run=False, confidence_threshold=0.8):
    """
    Auto mode - automatically fix paths with high confidence.
    """
    updated_count = 0
    skipped_count = 0
    failed_count = 0

    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}Automatic Path Update Mode (confidence >= {confidence_threshold:.0%}){Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

    for game in invalid_games:
        suggested_path, confidence = suggest_path_fix(game)

        if suggested_path and confidence >= confidence_threshold:
            if update_game_path(session, game, suggested_path, dry_run):
                updated_count += 1
            else:
                failed_count += 1
        else:
            if suggested_path:
                print(f"{Colors.WARNING}⊘ Skipping '{game.name}' - confidence too low ({confidence:.0%}){Colors.ENDC}")
            else:
                print(f"{Colors.WARNING}⊘ Skipping '{game.name}' - no suggestion found{Colors.ENDC}")
            skipped_count += 1

    return updated_count, skipped_count, failed_count

def print_summary(valid_count, invalid_count, updated_count, skipped_count, failed_count, dry_run=False):
    """
    Print a summary of the validation and update process.
    """
    total = valid_count + invalid_count

    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}Summary{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

    print(f"  Total games checked: {total}")
    print(f"  {Colors.OKGREEN}Valid paths: {valid_count}{Colors.ENDC}")
    print(f"  {Colors.FAIL}Invalid paths: {invalid_count}{Colors.ENDC}")

    if invalid_count > 0:
        print(f"\n  Update Results:")
        if dry_run:
            print(f"    {Colors.OKCYAN}Would update: {updated_count}{Colors.ENDC}")
        else:
            print(f"    {Colors.OKGREEN}Updated: {updated_count}{Colors.ENDC}")
        print(f"    {Colors.WARNING}Skipped: {skipped_count}{Colors.ENDC}")
        if failed_count > 0:
            print(f"    {Colors.FAIL}Failed: {failed_count}{Colors.ENDC}")

    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

def main():
    parser = argparse.ArgumentParser(
        description="Update game paths in SharewareZ database after extracting or reorganizing files.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )

    parser.add_argument(
        "--auto",
        action="store_true",
        help="Automatically fix paths with high confidence (>= 80%%)"
    )

    parser.add_argument(
        "--library",
        type=str,
        help="Filter by library name (case insensitive, partial match)"
    )

    parser.add_argument(
        "--confidence",
        type=float,
        default=0.8,
        help="Minimum confidence threshold for auto mode (0.0-1.0, default: 0.8)"
    )

    args = parser.parse_args()

    # Validate confidence threshold
    if not 0.0 <= args.confidence <= 1.0:
        print(f"{Colors.FAIL}Error: Confidence threshold must be between 0.0 and 1.0{Colors.ENDC}")
        sys.exit(1)

    # Create database session
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Print header
        print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
        print(f"{Colors.HEADER}SharewareZ Game Path Update Script{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")

        if args.dry_run:
            print(f"{Colors.OKCYAN}Running in DRY RUN mode - no changes will be made{Colors.ENDC}\n")

        # Validate all game paths
        print("Validating game paths...")
        valid_games, invalid_games = validate_game_paths(session, args.library)

        print(f"\nFound {Colors.OKGREEN}{len(valid_games)}{Colors.ENDC} games with valid paths")
        print(f"Found {Colors.FAIL}{len(invalid_games)}{Colors.ENDC} games with invalid paths\n")

        if len(invalid_games) == 0:
            print(f"{Colors.OKGREEN}All game paths are valid! No updates needed.{Colors.ENDC}\n")
            return

        # Process invalid games
        if args.auto:
            updated, skipped, failed = auto_mode(
                session,
                invalid_games,
                dry_run=args.dry_run,
                confidence_threshold=args.confidence
            )
        else:
            updated, skipped, failed = interactive_mode(
                session,
                invalid_games,
                dry_run=args.dry_run
            )

        # Print summary
        print_summary(len(valid_games), len(invalid_games), updated, skipped, failed, args.dry_run)

        if args.dry_run:
            print(f"{Colors.OKCYAN}This was a dry run. Run without --dry-run to apply changes.{Colors.ENDC}\n")

    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Interrupted by user. Exiting.{Colors.ENDC}\n")
        sys.exit(1)

    except Exception as e:
        print(f"\n{Colors.FAIL}Error: {e}{Colors.ENDC}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        session.close()

if __name__ == "__main__":
    main()
