import pytest
import os
from dotenv import load_dotenv

# Load .env file to ensure TEST_DATABASE_URL is available
load_dotenv()

# CRITICAL: Override DATABASE_URL with TEST_DATABASE_URL for all tests
# This prevents any accidental production database access
test_db_url = os.getenv('TEST_DATABASE_URL')
if test_db_url:
    # Additional safety: ensure we're not accidentally overriding with production DB
    if 'sharewarez' in test_db_url.lower() and 'test' not in test_db_url.lower():
        raise RuntimeError(
            f"CRITICAL: TEST_DATABASE_URL appears to point to production database: {test_db_url}. "
            "TEST_DATABASE_URL must contain 'test' in the database name for safety."
        )
    
    os.environ['DATABASE_URL'] = test_db_url
    print(f"PYTEST: Overriding DATABASE_URL with TEST_DATABASE_URL: {test_db_url}")
else:
    raise RuntimeError(
        "CRITICAL: TEST_DATABASE_URL environment variable not found. "
        "Tests cannot run without explicit test database configuration."
    )

from modules import create_app, db

@pytest.fixture(scope='function')
def app():
    """Create and configure a test app using the test database."""
    # Ensure we have TEST_DATABASE_URL environment variable
    test_db_url = os.getenv('TEST_DATABASE_URL')
    if not test_db_url:
        pytest.fail(
            "TEST_DATABASE_URL environment variable is not set. "
            "Please set it in your .env file to point to your test database."
        )
    
    # Enhanced safety checks: ensure we're not using production database
    production_indicators = ['sharewarez', 'prod', 'production']
    test_indicators = ['test', 'testing', 'sharewareztest']
    
    # Check if URL contains production indicators without test indicators
    contains_production = any(indicator in test_db_url.lower() for indicator in production_indicators)
    contains_test = any(indicator in test_db_url.lower() for indicator in test_indicators)
    
    if contains_production and not contains_test:
        pytest.fail(
            f"CRITICAL: TEST_DATABASE_URL appears to point to production database: {test_db_url}. "
            "Test database MUST contain 'test' in the name (e.g., 'sharewareztest'). "
            "Tests will NOT run against production database for safety."
        )
    
    # Additional check: ensure DATABASE_URL was properly overridden
    current_db_url = os.getenv('DATABASE_URL')
    if current_db_url != test_db_url:
        pytest.fail(
            f"CRITICAL: DATABASE_URL override failed. "
            f"DATABASE_URL={current_db_url}, TEST_DATABASE_URL={test_db_url}. "
            "This could result in tests running against production database."
        )
    
    # Create app - it will now use the overridden DATABASE_URL (which is TEST_DATABASE_URL)
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    
    # Double-check that the app is using test database
    actual_db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if actual_db_uri != test_db_url:
        pytest.fail(
            f"CRITICAL: App database URI mismatch. "
            f"Expected: {test_db_url}, Got: {actual_db_uri}. "
            "Tests cannot proceed with wrong database configuration."
        )
    
    print(f"✅ PYTEST: Safely using test database: {test_db_url}")
    
    yield app

@pytest.fixture(scope='function')  
def db_session(app):
    """Create a database session for testing with simple cleanup."""
    with app.app_context():
        yield db.session

@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()