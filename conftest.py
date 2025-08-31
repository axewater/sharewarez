import pytest
import os
from dotenv import load_dotenv

# Load .env file to ensure TEST_DATABASE_URL is available
load_dotenv()

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
    
    # Safety check: ensure we're not using production database
    if 'sharewarez' in test_db_url and 'sharewareztest' not in test_db_url:
        pytest.fail(
            f"TEST_DATABASE_URL appears to point to production database: {test_db_url}. "
            "Test database should contain 'test' in the name (e.g., 'sharewareztest')."
        )
    
    # Create app and explicitly set test database URI
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    app.config['SQLALCHEMY_DATABASE_URI'] = test_db_url
    
    print(f"Test using database: {test_db_url}")
    
    yield app

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

@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()