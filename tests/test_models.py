import pytest
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func

from modules import create_app, db
from modules.models import (
    User, Game, Library, Genre, GameMode, Theme, Platform, 
    PlayerPerspective, Developer, Publisher, MultiplayerMode,
    Image, GameURL, GameUpdate, GameExtra, DownloadRequest,
    Whitelist, ReleaseGroup, Newsletter, ScanJob, UnmatchedFolder,
    UserPreference, GlobalSettings, DiscoverySection, InviteToken,
    AllowedFileType, IgnoredFileType, SystemEvents,
    JSONEncodedDict, Category, Status,
    user_favorites, game_genre_association
)
from modules.platform import LibraryPlatform


def safe_cleanup_database(db_session):
    """Completely clean up ALL test data - this is a test database, nuke everything!"""
    from sqlalchemy import text, delete
    from modules.models import (
        Game, User, Library, DownloadRequest, Newsletter, 
        SystemEvents, InviteToken, Image, GameURL, ScanJob,
        UnmatchedFolder, GameUpdate, GameExtra, GlobalSettings,
        AllowedFileType, IgnoredFileType, Genre, Platform, Developer,
        Publisher, Theme, GameMode, PlayerPerspective, MultiplayerMode
    )
    
    try:
        # First ensure the session is in good state
        if db_session.is_active:
            db_session.rollback()
        
        # Try the aggressive approach first
        db_session.execute(text("SET session_replication_role = replica;"))
        
        # Delete all junction table data first
        junction_tables = ['user_favorites', 'game_genre_association', 'game_platform_association', 
                          'game_game_mode_association', 'game_theme_association', 
                          'game_player_perspective_association', 'game_multiplayer_mode_association']
        
        for table in junction_tables:
            try:
                db_session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            except Exception:
                pass  # Table might not exist or be locked
        
        # Delete all main table data including the models that have unique constraints
        main_tables = ['game_updates', 'game_extras', 'images', 'game_urls', 'unmatched_folders', 
                      'scan_jobs', 'download_requests', 'newsletters', 'system_events', 
                      'invite_tokens', 'games', 'users', 'libraries', 'genres', 'platforms', 
                      'developers', 'publishers', 'themes', 'game_modes', 'player_perspectives',
                      'multiplayer_modes', 'global_settings', 'allowed_file_types', 'ignored_file_types']
        
        for table in main_tables:
            try:
                db_session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
            except Exception:
                pass  # Table might not exist
        
        # Re-enable foreign key checks
        db_session.execute(text("SET session_replication_role = DEFAULT;"))
        
        db_session.commit()
        print("✅ Nuked all test database data!")
        
    except Exception as e:
        db_session.rollback()
        print(f"❌ Error during aggressive cleanup: {e}")
        
        # Fallback: Use model-based deletes if truncate fails
        try:
            db_session.execute(text("SET session_replication_role = DEFAULT;"))
            
            # Delete in proper order to respect foreign key constraints
            db_session.execute(delete(SystemEvents))
            db_session.execute(delete(InviteToken))
            db_session.execute(delete(DownloadRequest))
            db_session.execute(delete(GameUpdate))
            db_session.execute(delete(GameExtra))
            db_session.execute(delete(Image))
            db_session.execute(delete(GameURL))
            db_session.execute(delete(Game))
            db_session.execute(delete(User))
            db_session.execute(delete(Library))
            db_session.execute(delete(Genre))
            db_session.execute(delete(Platform))
            db_session.execute(delete(Developer))
            db_session.execute(delete(Publisher))
            db_session.execute(delete(Theme))
            db_session.execute(delete(GameMode))
            db_session.execute(delete(PlayerPerspective))
            db_session.execute(delete(MultiplayerMode))
            db_session.execute(delete(ScanJob))
            db_session.execute(delete(UnmatchedFolder))
            db_session.execute(delete(Newsletter))
            db_session.execute(delete(GlobalSettings))
            db_session.execute(delete(AllowedFileType))
            db_session.execute(delete(IgnoredFileType))
            
            db_session.commit()
            print("✅ Cleaned database with model deletes")
            
        except Exception as e2:
            db_session.rollback()
            print(f"❌ Fallback cleanup also failed: {e2}")
            # Try one more time with explicit session handling
            try:
                db_session.close()
                db_session.begin()
                db_session.commit()
            except:
                pass


@pytest.fixture(autouse=True)
def cleanup_after_each_test(db_session):
    """Automatically clean up after each test - no test data should persist!"""
    yield  # Let the test run first
    safe_cleanup_database(db_session)  # Clean up after


def get_or_create_platform(db_session, name):
    """Get existing platform or create new one with unique name."""
    existing = db_session.query(Platform).filter_by(name=name).first()
    if existing:
        return existing
    
    platform = Platform(name=name)
    db_session.add(platform)
    db_session.flush()
    return platform


def get_or_create_genre(db_session, name):
    """Get existing genre or create new one with unique name.""" 
    existing = db_session.query(Genre).filter_by(name=name).first()
    if existing:
        return existing
    
    genre = Genre(name=name)
    db_session.add(genre)
    db_session.flush()
    return genre


def get_or_create_developer(db_session, name):
    """Get existing developer or create new one with unique name."""
    existing = db_session.query(Developer).filter_by(name=name).first()
    if existing:
        return existing
    
    developer = Developer(name=name)
    db_session.add(developer)
    db_session.flush()
    return developer




class TestJSONEncodedDict:
    """Test the custom JSONEncodedDict type decorator."""
    
    def test_process_bind_param_valid_dict(self):
        """Test serializing a valid dictionary."""
        json_type = JSONEncodedDict()
        test_dict = {"key": "value", "number": 42}
        result = json_type.process_bind_param(test_dict, None)
        assert result == '{"key": "value", "number": 42}'
    
    def test_process_bind_param_none(self):
        """Test serializing None value."""
        json_type = JSONEncodedDict()
        result = json_type.process_bind_param(None, None)
        assert result is None
    
    def test_process_bind_param_invalid_data(self):
        """Test serializing invalid data returns None."""
        json_type = JSONEncodedDict()
        # Create an object that can't be JSON serialized
        invalid_data = set([1, 2, 3])
        result = json_type.process_bind_param(invalid_data, None)
        assert result is None
    
    def test_process_result_value_valid_json(self):
        """Test deserializing valid JSON string."""
        json_type = JSONEncodedDict()
        json_string = '{"key": "value", "number": 42}'
        result = json_type.process_result_value(json_string, None)
        assert result == {"key": "value", "number": 42}
    
    def test_process_result_value_none(self):
        """Test deserializing None value."""
        json_type = JSONEncodedDict()
        result = json_type.process_result_value(None, None)
        assert result is None
    
    def test_process_result_value_invalid_json(self):
        """Test deserializing invalid JSON returns empty dict."""
        json_type = JSONEncodedDict()
        invalid_json = '{"invalid": json}'
        result = json_type.process_result_value(invalid_json, None)
        assert result == {}


class TestUserModel:
    """Test the User model."""
    
    def test_create_user(self, db_session):
        """Test creating a basic user."""
        user = User(
            name=f'testuser_{uuid4().hex[:8]}',
            email=f'test_{uuid4().hex[:8]}@example.com',
            role='user',
            user_id=str(uuid4())
        )
        user.set_password('password123')
        
        db_session.add(user)
        db_session.flush()
        
        assert user.id is not None
        assert user.name.startswith('testuser_')
        assert user.email.startswith('test_')
        assert user.role == 'user'
        assert user.state is True  # Default value
        assert user.is_email_verified is False  # Default value
        assert user.invite_quota == 0  # Default value
    
    def test_user_password_hashing_argon2(self, db_session):
        """Test password hashing with Argon2."""
        user = User(
            name=f'testuser_{uuid4().hex[:8]}',
            email=f'test_{uuid4().hex[:8]}@example.com', 
            role='user',
            user_id=str(uuid4())
        )
        user.set_password('password123')
        
        # Password should be hashed with Argon2
        assert user.password_hash.startswith('$argon2')
        assert user.check_password('password123') is True
        assert user.check_password('wrongpassword') is False
    
    def test_user_flask_login_properties(self, db_session):
        """Test Flask-Login required properties."""
        user = User(
            name=f'testuser_{uuid4().hex[:8]}',
            email=f'test_{uuid4().hex[:8]}@example.com',
            role='user',
            user_id=str(uuid4())
        )
        
        assert user.is_authenticated is True
        assert user.is_active is True
        assert user.is_anonymous is False
        # get_id() returns string 'None' when id is None
        assert user.get_id() == 'None'  # No ID until saved
        
        user.set_password('password123')
        db_session.add(user)
        db_session.flush()
        
        assert user.get_id() == str(user.id)
    
    def test_username_reserved_validation(self):
        """Test reserved username validation."""
        assert User.is_username_reserved('system') is True
        assert User.is_username_reserved('SYSTEM') is True
        assert User.is_username_reserved('admin') is False
        assert User.is_username_reserved('testuser') is False
    
    def test_user_unique_constraints(self, db_session):
        """Test unique constraints on user fields."""
        user1 = User(
            name=f'testuser_{uuid4().hex[:8]}',
            email=f'test_{uuid4().hex[:8]}@example.com',
            role='user',
            user_id=str(uuid4())
        )
        user1.set_password('password123')
        db_session.add(user1)
        db_session.flush()
        
        # Duplicate username should fail
        user2 = User(
            name=user1.name,  # Intentionally duplicate name for testing unique constraint
            email=f'other_{uuid4().hex[:8]}@example.com', 
            role='user',
            user_id=str(uuid4())
        )
        user2.set_password('password123')
        db_session.add(user2)
        
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestLibraryModel:
    """Test the Library model."""
    
    def test_create_library(self, db_session):
        """Test creating a library."""
        library = Library(
            name='Test Library',
            platform=LibraryPlatform.PCWIN,
            display_order=1
        )
        
        db_session.add(library)
        db_session.flush()
        
        assert library.uuid is not None
        assert library.name == 'Test Library'
        assert library.platform == LibraryPlatform.PCWIN
        assert library.display_order == 1
    
    def test_library_uuid_generation(self, db_session):
        """Test UUID generation for library."""
        library = Library(
            name='Test Library',
            platform=LibraryPlatform.PCWIN
        )
        
        db_session.add(library)
        db_session.flush()
        
        assert library.uuid is not None
        assert len(library.uuid) == 36  # UUID4 string length


class TestGameModel:
    """Test the Game model."""
    
    def test_create_game(self, db_session):
        """Test creating a game."""
        library = Library(
            name='Test Library',
            platform=LibraryPlatform.PCWIN
        )
        db_session.add(library)
        db_session.flush()
        
        game = Game(
            name='Test Game',
            library_uuid=library.uuid,
            full_disk_path='/path/to/game',
            size=1000000
        )
        
        db_session.add(game)
        db_session.flush()
        
        assert game.id is not None
        assert game.uuid is not None
        assert game.name == 'Test Game'
        assert game.library_uuid == library.uuid
        assert game.size == 1000000
        assert game.times_downloaded == 0  # Default value
        assert game.date_created is not None
    
    def test_game_library_relationship(self, db_session):
        """Test game-library relationship."""
        library = Library(
            name='Test Library',
            platform=LibraryPlatform.PCWIN
        )
        db_session.add(library)
        db_session.flush()
        
        game = Game(
            name='Test Game',
            library_uuid=library.uuid,
            full_disk_path='/path/to/game'
        )
        db_session.add(game)
        db_session.flush()
        
        # Test relationship
        assert game.library == library
        assert game in library.games
    
    def test_game_enums(self, db_session):
        """Test game enum fields."""
        library = Library(
            name='Test Library',
            platform=LibraryPlatform.PCWIN
        )
        db_session.add(library)
        db_session.flush()
        
        game = Game(
            name='Test Game',
            library_uuid=library.uuid,
            status=Status.RELEASED,
            category=Category.MAIN_GAME,
            full_disk_path='/path/to/game'
        )
        
        db_session.add(game)
        db_session.flush()
        
        assert game.status == Status.RELEASED
        assert game.category == Category.MAIN_GAME
    
    def test_game_uuid_uniqueness(self, db_session):
        """Test game UUID uniqueness."""
        library = Library(
            name='Test Library',
            platform=LibraryPlatform.PCWIN
        )
        db_session.add(library)
        db_session.flush()
        
        game1 = Game(
            name='Game 1',
            library_uuid=library.uuid,
            full_disk_path='/path/to/game1'
        )
        game2 = Game(
            name='Game 2', 
            library_uuid=library.uuid,
            full_disk_path='/path/to/game2'
        )
        
        db_session.add_all([game1, game2])
        db_session.flush()
        
        assert game1.uuid != game2.uuid


class TestGameRelationships:
    """Test game many-to-many relationships."""
    
    def test_game_genre_relationship(self, db_session):
        """Test game-genre many-to-many relationship."""
        library = Library(name='Test Library', platform=LibraryPlatform.PCWIN)
        db_session.add(library)
        db_session.flush()
        
        game = Game(
            name='Test Game',
            library_uuid=library.uuid,
            full_disk_path='/path/to/game'
        )
        # Use get_or_create pattern to avoid unique constraint violations
        # Use helper function to avoid unique constraint violations
        test_id = str(uuid4())[:8]
        genre1 = get_or_create_genre(db_session, f'Action_{test_id}')
        genre2 = get_or_create_genre(db_session, f'Adventure_{test_id}')
        
        db_session.flush()  # Ensure genres are committed before adding to game
        
        game.genres = [genre1, genre2]
        
        db_session.add(game)
        db_session.flush()
        
        assert len(game.genres) == 2
        assert genre1 in game.genres
        assert genre2 in game.genres
        assert game in genre1.games
        assert game in genre2.games
    
    def test_game_developer_relationship(self, db_session):
        """Test game-developer relationship."""
        library = Library(name='Test Library', platform=LibraryPlatform.PCWIN)
        db_session.add(library)
        db_session.flush()
        
        developer = get_or_create_developer(db_session, 'Test Developer')
        game = Game(
            name='Test Game',
            library_uuid=library.uuid,
            developer=developer,
            full_disk_path='/path/to/game'
        )
        
        db_session.add(game)
        db_session.flush()
        
        assert game.developer == developer
        assert game in developer.games
    
    def test_user_favorites_relationship(self, db_session):
        """Test user-game favorites relationship."""
        library = Library(name='Test Library', platform=LibraryPlatform.PCWIN)
        db_session.add(library)
        db_session.flush()
        
        user = User(
            name=f'testuser_{uuid4().hex[:8]}',
            email=f'test_{uuid4().hex[:8]}@example.com',
            role='user',
            user_id=str(uuid4())
        )
        user.set_password('password123')
        game = Game(
            name='Test Game',
            library_uuid=library.uuid,
            full_disk_path='/path/to/game'
        )
        
        user.favorites.append(game)
        
        db_session.add_all([user, game])
        db_session.flush()
        
        assert game in user.favorites
        assert user in game.favorited_by


class TestImageModel:
    """Test the Image model."""
    
    def test_create_image(self, db_session):
        """Test creating an image."""
        library = Library(name='Test Library', platform=LibraryPlatform.PCWIN)
        db_session.add(library)
        db_session.flush()
        
        game = Game(
            name='Test Game',
            library_uuid=library.uuid,
            full_disk_path='/path/to/game'
        )
        db_session.add(game)
        db_session.flush()
        
        image = Image(
            game_uuid=game.uuid,
            image_type='cover',
            url='/static/images/cover.jpg',
            igdb_image_id='12345'
        )
        
        db_session.add(image)
        db_session.flush()
        
        assert image.id is not None
        assert image.game_uuid == game.uuid
        assert image.image_type == 'cover'
        assert image.is_downloaded is False  # Default value
        assert image.created_at is not None


class TestDownloadRequestModel:
    """Test the DownloadRequest model."""
    
    def test_create_download_request(self, db_session):
        """Test creating a download request."""
        user = User(
            name=f'testuser_{uuid4().hex[:8]}',
            email=f'test_{uuid4().hex[:8]}@example.com',
            role='user',
            user_id=str(uuid4())
        )
        user.set_password('password123')
        library = Library(name='Test Library', platform=LibraryPlatform.PCWIN)
        db_session.add_all([user, library])
        db_session.flush()
        
        game = Game(
            name='Test Game',
            library_uuid=library.uuid,
            full_disk_path='/path/to/game'
        )
        db_session.add(game)
        db_session.flush()
        
        download_request = DownloadRequest(
            user_id=user.id,
            game_uuid=game.uuid,
            download_size=500.0
        )
        
        db_session.add(download_request)
        db_session.flush()
        
        assert download_request.id is not None
        assert download_request.status == 'pending'  # Default value
        assert download_request.download_size == 500.0
        assert download_request.request_time is not None


class TestGlobalSettingsModel:
    """Test the GlobalSettings model."""
    
    def test_create_global_settings(self, db_session):
        """Test creating global settings."""
        settings_data = {
            'site_name': 'SharewareZ',
            'max_downloads': 5
        }
        
        global_settings = GlobalSettings(
            settings=settings_data,
            discord_webhook_url='https://discord.com/webhook',
            smtp_enabled=True,
            # Set the setup-related fields to avoid database column errors
            setup_in_progress=False,
            setup_current_step=1,
            setup_completed=False
        )
        
        db_session.add(global_settings)
        db_session.flush()
        
        assert global_settings.id is not None
        assert global_settings.settings == settings_data
        assert global_settings.discord_webhook_url == 'https://discord.com/webhook'
        assert global_settings.smtp_enabled is True
        assert global_settings.last_updated is not None
        assert global_settings.setup_in_progress is False
        assert global_settings.setup_current_step == 1
        assert global_settings.setup_completed is False


class TestScanJobModel:
    """Test the ScanJob model."""
    
    def test_create_scan_job(self, db_session):
        """Test creating a scan job."""
        library = Library(name='Test Library', platform=LibraryPlatform.PCWIN)
        db_session.add(library)
        db_session.flush()
        
        folders_data = ['/path/to/games1', '/path/to/games2']
        
        scan_job = ScanJob(
            folders=folders_data,
            content_type='Games',
            schedule='24_hours',
            library_uuid=library.uuid,
            scan_folder='/path/to/scan'
        )
        
        db_session.add(scan_job)
        db_session.flush()
        
        assert scan_job.id is not None
        assert scan_job.folders == folders_data
        assert scan_job.content_type == 'Games'
        assert scan_job.schedule == '24_hours'
        assert scan_job.is_enabled is True  # Default value
        assert scan_job.total_folders == 0  # Default value


class TestInviteTokenModel:
    """Test the InviteToken model."""
    
    def test_create_invite_token(self, db_session):
        """Test creating an invite token."""
        creator = User(
            name='creator',
            email='creator@example.com',
            role='admin',
            user_id=str(uuid4())
        )
        creator.set_password('password123')
        db_session.add(creator)
        db_session.flush()
        
        invite_token = InviteToken(
            token='abc123def456',
            creator_user_id=creator.user_id,
            recipient_email='newuser@example.com'
        )
        
        db_session.add(invite_token)
        db_session.flush()
        
        assert invite_token.id is not None
        assert invite_token.token == 'abc123def456'
        assert invite_token.creator_user_id == creator.user_id
        assert invite_token.used is False  # Default value
        assert invite_token.expires_at > datetime.now(timezone.utc)
        
        # Test relationship
        assert invite_token.creator == creator


class TestSystemEventsModel:
    """Test the SystemEvents model."""
    
    def test_create_system_event(self, db_session):
        """Test creating a system event."""
        user = User(
            name=f'testuser_{uuid4().hex[:8]}',
            email=f'test_{uuid4().hex[:8]}@example.com',
            role='admin',
            user_id=str(uuid4())
        )
        user.set_password('password123')
        db_session.add(user)
        db_session.flush()
        
        event = SystemEvents(
            event_type='login',
            event_text='User logged in successfully',
            event_level='information',
            audit_user=user.id
        )
        
        db_session.add(event)
        db_session.flush()
        
        assert event.id is not None
        assert event.event_type == 'login'
        assert event.event_text == 'User logged in successfully'
        assert event.event_level == 'information'
        assert event.timestamp is not None
        
        # Test relationship
        assert event.user == user


class TestEnums:
    """Test enum classes."""
    
    def test_category_enum(self):
        """Test Category enum values."""
        assert Category.MAIN_GAME.value == "Main Game"
        assert Category.DLC_ADDON.value == "DLC/Add-on"
        assert Category.EXPANSION.value == "Expansion"
        assert Category.REMAKE.value == "Remake"
    
    def test_status_enum(self):
        """Test Status enum values."""
        assert Status.RELEASED.value == "Released"
        assert Status.ALPHA.value == "Alpha"
        assert Status.BETA.value == "Beta"
        assert Status.CANCELLED.value == "Cancelled"


class TestModelChoiceFunctions:
    """Test model choice functions for forms."""
    
    def test_genre_choices(self, db_session):
        """Test genre_choices function."""
        from modules.models import genre_choices
        
        # Use get_or_create pattern to avoid unique constraint violations
        # Use helper function to avoid unique constraint violations
        test_id = str(uuid4())[:8]
        genre1 = get_or_create_genre(db_session, f'Action_{test_id}')
        genre2 = get_or_create_genre(db_session, f'Adventure_{test_id}')
        
        db_session.flush()
        
        choices = genre_choices()
        assert len(choices) >= 2  # At least our test genres should be there
        genre_names = [genre.name for genre in choices]
        assert genre1.name in genre_names
        assert genre2.name in genre_names
    
    def test_platform_choices(self, db_session):
        """Test platform_choices function."""
        from modules.models import platform_choices
        
        # Use helper functions to avoid unique constraint violations
        test_id = str(uuid4())[:8]
        platform1 = get_or_create_platform(db_session, f'PC_{test_id}')
        platform2 = get_or_create_platform(db_session, f'PlayStation_{test_id}')
        
        choices = platform_choices()
        # Verify our platforms are in the choices (there may be others from previous tests)
        platform_names = [p.name for p in choices]
        assert platform1.name in platform_names
        assert platform2.name in platform_names
        assert len(choices) >= 2