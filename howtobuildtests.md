# SharewareZ Unit Testing Guide

This guide provides comprehensive instructions for writing unit tests in the SharewareZ project. Follow these patterns and practices to maintain consistency and reliability across the test suite.

## Table of Contents

1. [Database Configuration](#database-configuration)
2. [Testing Philosophy](#testing-philosophy)
3. [Project Structure](#project-structure)
4. [Database Testing Patterns](#database-testing-patterns)
5. [Fixtures and Test Data](#fixtures-and-test-data)
6. [Mocking and Patching](#mocking-and-patching)
7. [Common Patterns](#common-patterns)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

## Database Configuration

**CRITICAL**: All tests use the PostgreSQL test database, NOT the production database.

### Test Database Setup

1. **Environment Variables**: The test database is configured via `TEST_DATABASE_URL` in your `.env` file:
   ```
   TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sharewareztest
   ```

2. **Database Creation**: Ensure the test database exists:
   ```bash
   psql -U postgres -c "CREATE DATABASE sharewareztest;"
   ```

3. **Automatic Configuration**: 
   - Tests automatically load the `.env` file via `conftest.py`
   - The test database URL is enforced in fixtures to prevent accidental production DB usage
   - Safety checks ensure you're never testing against the production database

### Running Tests

**Always activate the virtual environment first:**
```bash
source venv/bin/activate
python -m pytest tests/
```

**Important**: Tests will FAIL if:
- `TEST_DATABASE_URL` is not set in `.env`
- The test database doesn't exist
- The TEST_DATABASE_URL points to the production database (safety check)

## Testing Philosophy

SharewareZ uses **real PostgreSQL database testing** - we do NOT use in-memory SQLite databases or mock databases. All tests run against the actual PostgreSQL instance to ensure true integration testing.

### Key Principles:
- **Real Database Testing**: Always use the actual PostgreSQL database configured in the project
- **Transaction Isolation**: Each test runs in its own transaction that gets rolled back
- **Comprehensive Coverage**: Test both success and failure scenarios
- **Realistic Data**: Use fixtures that mirror real-world data structures
- **Clear Naming**: Test names should clearly describe what is being tested

## Project Structure

```
tests/
├── conftest.py                    # Global fixtures and configuration
├── test_models.py                 # Database model tests
├── test_routes*.py                # Flask route tests
├── test_utils*.py                 # Utility function tests
└── test_forms.py                  # Form validation tests
```

### File Naming Convention:
- `test_models.py` - Database model tests
- `test_routes_[blueprint].py` - Route tests for specific blueprints
- `test_utils_[module].py` - Utility function tests for specific modules
- `test_[specific_feature].py` - Feature-specific tests

## Database Testing Patterns

### Core Fixtures (conftest.py)

Every test file uses these core fixtures:

```python
def test_example(app, db_session):
    """Example test using core fixtures."""
    # app: Flask application instance with testing config
    # db_session: Database session with automatic rollback
```

### Transaction Isolation

The `db_session` fixture automatically handles database cleanup:

```python
@pytest.fixture(scope='function')  
def db_session(app):
    """Create a database session for testing with transaction rollback."""
    with app.app_context():
        # Start a transaction that will be rolled back after each test
        connection = db.engine.connect()
        transaction = connection.begin()
        
        # Configure the session to use this connection
        db.session.configure(bind=connection, binds={})
        
        yield db.session
        
        # Rollback the transaction to clean up after each test
        transaction.rollback()
        connection.close()
```

### Handling Unique Constraints

When creating test data that might conflict with other tests, use "get or create" patterns:

```python
def get_or_create_developer(db_session, name):
    """Get existing developer or create new one with unique name."""
    existing = db_session.query(Developer).filter_by(name=name).first()
    if existing:
        return existing
    
    developer = Developer(name=name)
    db_session.add(developer)
    db_session.flush()
    return developer
```

## Fixtures and Test Data

### Custom Fixtures

Create reusable test data with fixtures:

```python
@pytest.fixture
def sample_library(db_session):
    """Create a sample library for testing."""
    library = Library(
        uuid=str(uuid4()),
        name='Test Library',
        platform=LibraryPlatform.PCWIN
    )
    db_session.add(library)
    db_session.flush()
    return library

@pytest.fixture
def sample_game(db_session, sample_library, sample_global_settings):
    """Create a sample game for testing."""
    import random
    unique_id = random.randint(100000, 999999)
    game = Game(
        uuid=str(uuid4()),
        library_uuid=sample_library.uuid,
        igdb_id=unique_id,
        name='Test Game',
        full_disk_path=f'/test/game/path/{unique_id}',
        size=1024000,
        date_created=datetime.now(UTC),
        date_identified=datetime.now(UTC)
    )
    db_session.add(game)
    db_session.flush()
    return game
```

### Mock Data Fixtures

For API responses and external data:

```python
@pytest.fixture
def mock_igdb_response():
    """Mock IGDB API response data."""
    return [
        {
            'id': 12345,
            'name': 'Test Game',
            'summary': 'A test game',
            'genres': [{'id': 1, 'name': 'Action'}],
            'platforms': [{'id': 6, 'name': 'PC'}]
        }
    ]

@pytest.fixture
def mock_company_response():
    """Mock IGDB company response data."""
    return [
        {'company': {'name': 'Test Developer'}, 'developer': True, 'publisher': False, 'game': 12345},
        {'company': {'name': 'Test Publisher'}, 'developer': False, 'publisher': True, 'game': 12345}
    ]
```

## Mocking and Patching

### External API Calls

Always mock external API calls to avoid dependencies:

```python
@patch('modules.utils_game_core.make_igdb_api_request')
def test_retrieve_game_data(mock_api, db_session, mock_igdb_response):
    """Test game data retrieval from IGDB."""
    mock_api.return_value = mock_igdb_response
    
    result = retrieve_game_data(12345)
    
    mock_api.assert_called_once_with('games', 12345)
    assert result['name'] == 'Test Game'
```

### File System Operations

Mock file system operations to avoid creating actual files:

```python
@patch('builtins.open', new_callable=mock_open, read_data='test file content')
@patch('os.path.exists', return_value=True)
def test_file_processing(mock_exists, mock_file, db_session):
    """Test file processing without actual files."""
    result = process_file('/fake/path/file.txt')
    
    mock_exists.assert_called_once_with('/fake/path/file.txt')
    mock_file.assert_called_once_with('/fake/path/file.txt', 'r')
    assert result == 'processed content'
```

### Multiple Patches

Use multiple patches for complex scenarios:

```python
@patch('modules.utils_game_core.discord_webhook')
@patch('modules.utils_game_core.smart_process_images_for_game')
@patch('modules.utils_game_core.make_igdb_api_request')
def test_complex_game_processing(mock_api, mock_images, mock_discord, 
                               db_session, sample_library, mock_igdb_response):
    """Test complete game processing workflow."""
    mock_api.return_value = mock_igdb_response
    mock_images.return_value = {'success': True, 'count': 3}
    
    result = process_complete_game('Test Game', '/path', sample_library.uuid)
    
    mock_api.assert_called_once()
    mock_images.assert_called_once()
    mock_discord.assert_called_once()
    assert result['success'] is True
```

## Common Patterns

### Testing Success and Failure Scenarios

Always test both success and failure cases:

```python
def test_create_user_success(self, db_session):
    """Test successful user creation."""
    user = User(username='testuser', email='test@example.com')
    user.set_password('password123')
    
    db_session.add(user)
    db_session.flush()
    
    assert user.id is not None
    assert user.username == 'testuser'
    assert user.check_password('password123')

def test_create_user_duplicate_username(self, db_session):
    """Test user creation with duplicate username fails."""
    user1 = User(username='testuser', email='test1@example.com')
    user2 = User(username='testuser', email='test2@example.com')
    
    db_session.add(user1)
    db_session.flush()
    
    db_session.add(user2)
    
    with pytest.raises(IntegrityError):
        db_session.flush()
```

### Testing Relationships

Test database relationships thoroughly:

```python
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
    
    # Test both sides of the relationship
    assert game.developer == developer
    assert game in developer.games
```

### Testing Error Handling

Test error conditions and edge cases:

```python
@patch('modules.utils_game_core.make_igdb_api_request')
def test_api_failure_handling(self, mock_api, db_session):
    """Test handling of API failures."""
    mock_api.return_value = {'error': 'API Error'}
    
    with patch('builtins.print'):  # Suppress error output
        result = fetch_game_data(12345)
    
    assert result is None
    mock_api.assert_called_once()
```

### Testing Background Processing

For functions that handle background tasks:

```python
@patch('modules.utils_game_core.download_images_for_game_turbo')
@patch('modules.utils_game_core.download_images_for_game')
def test_image_processing_modes(self, mock_download, mock_download_turbo,
                              db_session, sample_game, sample_global_settings):
    """Test image processing in different modes."""
    # Test turbo mode
    sample_global_settings.use_turbo_image_downloads = True
    db_session.commit()
    
    smart_process_images_for_game(sample_game, [], [])
    mock_download_turbo.assert_called_once()
    mock_download.assert_not_called()
    
    # Reset mocks
    mock_download_turbo.reset_mock()
    mock_download.reset_mock()
    
    # Test single-thread mode
    sample_global_settings.use_turbo_image_downloads = False
    db_session.commit()
    
    smart_process_images_for_game(sample_game, [], [])
    mock_download.assert_called_once()
    mock_download_turbo.assert_not_called()
```

## Best Practices

### 1. Clear Test Names

Use descriptive test names that explain what is being tested:

```python
# Good
def test_create_game_with_valid_data_succeeds(self):
def test_create_game_with_duplicate_igdb_id_fails(self):
def test_scan_folder_with_no_games_returns_empty_list(self):

# Bad  
def test_create_game(self):
def test_game_duplicate(self):
def test_scan(self):
```

### 2. Test Organization

Organize tests into logical classes:

```python
class TestUserModel:
    """Tests for User model functionality."""
    
    def test_create_user(self):
    def test_user_password_hashing(self):
    def test_user_unique_constraints(self):

class TestGameRelationships:
    """Tests for Game model relationships."""
    
    def test_game_genre_relationship(self):
    def test_game_developer_relationship(self):
    def test_user_favorites_relationship(self):
```

### 3. Use Fixtures Appropriately

Create fixtures for commonly used test data:

```python
@pytest.fixture
def sample_global_settings(db_session):
    """Create default global settings for testing."""
    settings = GlobalSettings(
        use_turbo_image_downloads=False,
        max_concurrent_downloads=5,
        image_download_timeout=30
    )
    db_session.add(settings)
    db_session.flush()
    return settings
```

### 4. Mock External Dependencies

Always mock external services and file system operations:

```python
# Mock external APIs
@patch('modules.utils_game_core.make_igdb_api_request')

# Mock file operations
@patch('builtins.open', new_callable=mock_open)
@patch('os.path.exists', return_value=True)

# Mock network requests
@patch('requests.get')

# Mock Discord webhooks
@patch('modules.utils_game_core.discord_webhook')
```

### 5. Handle Database Constraints

Use helper functions to avoid unique constraint violations:

```python
def get_or_create_platform(db_session, name):
    """Get existing platform or create new one with unique name."""
    existing = db_session.query(Platform).filter_by(name=name).first()
    if existing:
        return existing
    
    platform = Platform(name=name)
    db_session.add(platform)
    db_session.flush()
    return platform
```

### 6. Test Both Positive and Negative Cases

```python
def test_valid_input_succeeds(self):
    """Test function with valid input."""
    # Test success case

def test_invalid_input_fails(self):
    """Test function with invalid input."""
    # Test failure case
    with pytest.raises(ValueError):
        # Call function with bad data
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Unique Constraint Violations

**Problem**: `IntegrityError: duplicate key value violates unique constraint`

**Solution**: Use "get or create" helper functions:
```python
developer = get_or_create_developer(db_session, 'Test Developer')
```

#### 2. Foreign Key Constraint Violations

**Problem**: `IntegrityError: foreign key constraint fails`

**Solution**: Ensure proper order of database operations:
```python
# Create parent first
library = Library(name='Test Library', platform=LibraryPlatform.PCWIN)
db_session.add(library)
db_session.flush()  # Get the library.uuid

# Then create child
game = Game(library_uuid=library.uuid, name='Test Game')
```

#### 3. Transaction Rollback Issues

**Problem**: Data persists between tests

**Solution**: Use `db_session.flush()` instead of `db_session.commit()`:
```python
# Good - allows rollback
db_session.add(user)
db_session.flush()

# Bad - commits transaction
db_session.add(user)  
db_session.commit()
```

#### 4. Mock Not Called Issues

**Problem**: `AssertionError: Expected call not found`

**Solution**: Check the full import path:
```python
# If the function is imported as:
from modules.utils_game_core import make_api_request

# Mock it as:
@patch('modules.utils_game_core.make_api_request')

# NOT as:
@patch('some.other.module.make_api_request')
```

#### 5. Flask App Context Issues

**Problem**: `RuntimeError: Working outside of application context`

**Solution**: Use the `app` fixture:
```python
def test_function_needs_context(app, db_session):
    with app.app_context():
        # Your test code here
```

### Debugging Tests

#### Run Single Test
```bash
python -m pytest tests/test_models.py::TestUserModel::test_create_user -v
```

#### Run with Debugging Output
```bash
python -m pytest tests/test_models.py -v -s --tb=short
```

#### Run with Coverage
```bash
python -m pytest tests/ --cov=modules --cov-report=term-missing
```

## Example Test File Structure

```python
import pytest
from unittest.mock import patch, MagicMock
from modules import create_app, db
from modules.models import Game, Library, Developer
from modules.utils_game_core import some_function

# Helper functions (if needed)
def get_or_create_developer(db_session, name):
    existing = db_session.query(Developer).filter_by(name=name).first()
    if existing:
        return existing
    developer = Developer(name=name)
    db_session.add(developer)
    db_session.flush()
    return developer

# Fixtures
@pytest.fixture
def sample_data(db_session):
    """Create sample data for tests."""
    # Setup test data
    return data

# Test Classes
class TestSomeFeature:
    """Test some specific feature."""
    
    def test_success_case(self, db_session, sample_data):
        """Test successful operation."""
        # Test implementation
        assert result == expected
    
    @patch('module.external_function')
    def test_with_mocking(self, mock_func, db_session):
        """Test with external dependencies mocked."""
        mock_func.return_value = 'mocked result'
        # Test implementation
        assert mock_func.called
    
    def test_error_case(self, db_session):
        """Test error handling."""
        with pytest.raises(SomeException):
            # Code that should raise exception
```

This guide should provide everything needed to write comprehensive, maintainable unit tests for SharewareZ. Remember: test early, test often, and test thoroughly!