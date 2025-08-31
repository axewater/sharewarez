import pytest
from modules import create_app, db

@pytest.fixture(scope='function')
def app():
    """Create and configure a test app using the test database."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    
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