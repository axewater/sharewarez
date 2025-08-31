# SharewareZ Unit Testing Guide

This guide provides comprehensive instructions for writing unit tests in the SharewareZ project. Follow these patterns and practices to maintain consistency and reliability across the test suite.

## Database Configuration

**CRITICAL**: All tests use the PostgreSQL test database, NOT the production database.

### Test Database Setup

1. **Environment Variables**: The test database is configured via `TEST_DATABASE_URL` in your `.env` file:
   ```
   TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sharewareztest
   ```

2. **Automatic Configuration**: 
   - Tests automatically load the `.env` file via `conftest.py`
   - The test database URL is enforced in fixtures to prevent accidental production DB usage
   - Safety checks ensure you're never testing against the production database

### Running Tests

**Always activate the virtual environment first:**
```bash
source venv/bin/activate
python -m pytest tests/
```

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

### 6. Handle Existing GlobalSettings

**IMPORTANT**: The GlobalSettings table is automatically populated during database initialization, which means your tests will often find existing GlobalSettings records rather than starting with an empty table.

**Problem**: Tests that create new GlobalSettings records may fail because the `get_smtp_settings()` function (and similar) returns the first record from the database, not necessarily the one your test created.

**Solution**: Update existing GlobalSettings instead of creating new ones:

```python
@pytest.fixture
def valid_smtp_settings():
    """Create or update GlobalSettings record with valid SMTP configuration."""
    def _create_settings(db_session, enabled=True):
        from sqlalchemy import select
        # Get existing settings or create new one
        settings = db_session.execute(select(GlobalSettings)).scalars().first()
        if not settings:
            settings = GlobalSettings()
            db_session.add(settings)
        
        # Update with test values
        settings.smtp_enabled = enabled
        settings.smtp_server = 'smtp.example.com'
        settings.smtp_port = 587
        settings.smtp_username = 'testuser@example.com'
        settings.smtp_password = 'testpass123'
        settings.smtp_use_tls = True
        settings.smtp_default_sender = 'noreply@example.com'
        
        db_session.commit()  # Use commit here since GlobalSettings is singleton-like
        return settings
    return _create_settings
```

**Why this happens**: 
- The application automatically creates GlobalSettings during startup/initialization
- Functions like `get_smtp_settings()` use `.first()` to get the primary settings record
- Creating additional GlobalSettings records doesn't affect which one gets returned

**Best practices for GlobalSettings testing**:
- Always check for existing records first with `select(GlobalSettings).scalars().first()`
- Update the existing record rather than creating new ones
- Use `db_session.commit()` for GlobalSettings changes since it's designed as a singleton
- Test both enabled and disabled states by toggling the same record

### 7. Test Both Positive and Negative Cases

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

#### 1a. GlobalSettings Already Exists

**Problem**: Test failures when creating GlobalSettings fixtures due to existing records from database initialization

**Symptoms**:
- Functions like `get_smtp_settings()` return `None` when you expect configured settings
- Tests fail with assertion errors about expected vs actual values
- Creating new GlobalSettings records doesn't affect what the application functions return

**Solution**: Update existing GlobalSettings instead of creating new ones:
```python
# Instead of this:
settings = GlobalSettings(smtp_enabled=True, smtp_server='test.com')
db_session.add(settings)

# Do this:
settings = db_session.execute(select(GlobalSettings)).scalars().first()
if not settings:
    settings = GlobalSettings()
    db_session.add(settings)
settings.smtp_enabled = True
settings.smtp_server = 'test.com'
db_session.commit()  # Use commit for GlobalSettings
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


#### 5. Flask App Context Issues

**Problem**: `RuntimeError: Working outside of application context`

**Solution**: Use the `app` fixture:
```python
def test_function_needs_context(app, db_session):
    with app.app_context():
        # Your test code here
```



This guide should provide everything needed to write comprehensive, maintainable unit tests for SharewareZ. Remember: test early, test often, and test thoroughly!