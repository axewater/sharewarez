from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_app(app):
    """Initialize database with the Flask app"""
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
    """
    Checks if the PostgreSQL port is open by attempting to create a socket connection.
    
    Args:
        host: The hostname or IP address of the PostgreSQL server.
        port: The port number of the PostgreSQL server.
        retries: Maximum number of retries.
        delay: Delay in seconds between retries.
    Returns:
        bool: True if the port is open, False otherwise.
    """
    for attempt in range(retries):
        try:
            with socket.create_connection((host, port), timeout=10):
                print(f"Connection to PostgreSQL on port {port} successful.")
                return True
        except (socket.timeout, ConnectionRefusedError):
            print(f"Connection to PostgreSQL on port {port} failed. Attempt {attempt + 1} of {retries}.")
            time.sleep(delay)
    return False

def init_db(app):
    """Initialize database with the Flask app"""
    parsed_url = urlparse(app.config['SQLALCHEMY_DATABASE_URI'])
    check_postgres_port_open(parsed_url.hostname, 5432, 60, 2)
    db.init_app(app)
