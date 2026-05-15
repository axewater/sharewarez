import os, sys

def _load_secret_key():
    """Load SECRET_KEY from env. Fail loudly if unset outside of test runs."""
    key = os.getenv('SECRET_KEY')
    if key and key != 'put_your_own_secret_string_here_32617432':
        return key
    # Allow pytest runs to proceed with a generated key; never silently used in prod.
    if 'pytest' in sys.modules or 'PYTEST_CURRENT_TEST' in os.environ:
        import secrets
        return secrets.token_urlsafe(64)
    raise RuntimeError(
        "SECRET_KEY environment variable is not set (or still has the example value). "
        "Generate a strong random value (e.g. `python -c 'import secrets; print(secrets.token_urlsafe(64))'`) "
        "and set it in your .env file before starting the application."
    )

class Config(object):
    # Set Database connection string here or in your .env file, when using docker set the hostname to 'db'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/sharewarez')

    # Set the path to the folder where the game files are stored (ie: use c:\gamez for windows or /gamez for linux)
    DATA_FOLDER_WAREZ = os.getenv('DATA_FOLDER_WAREZ', r'Z:\gamez')

    # OS-specific base folder paths
    if os.name == 'nt':  # Windows
        BASE_FOLDER_WINDOWS = os.getenv('BASE_FOLDER_WINDOWS', 'Z:\\')
    else:  # POSIX (Linux, Unix, MacOS, etc.)
        BASE_FOLDER_POSIX = os.getenv('BASE_FOLDER_POSIX', '/storage')

    # YOU CAN LEAVE ALL THESE SETTINGS AT DEFAULT:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'sharewarez/static/library')
    SECRET_KEY = _load_secret_key()
    IMAGE_SAVE_PATH = os.path.join(os.path.dirname(__file__), 'sharewarez/static/library/images')
    IGDB_API_ENDPOINT = os.getenv('IGDB_API_ENDPOINT', 'https://api.igdb.com/v4/games')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session/remember-me cookie hardening. Defaults are safe for HTTPS deployments;
    # set SESSION_COOKIE_SECURE=false in .env for local HTTP development only.
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'true').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    REMEMBER_COOKIE_SECURE = os.getenv('REMEMBER_COOKIE_SECURE', 'true').lower() == 'true'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = os.getenv('REMEMBER_COOKIE_SAMESITE', 'Lax')
    
    # Zipstream configuration for streaming ZIP downloads
    ZIPSTREAM_CHUNK_SIZE = int(os.getenv('ZIPSTREAM_CHUNK_SIZE', 65536))  # 64KB chunks for memory efficiency
    ZIPSTREAM_COMPRESSION_LEVEL = int(os.getenv('ZIPSTREAM_COMPRESSION_LEVEL', 0))  # ZIP_STORED for compatibility
    ZIPSTREAM_ENABLE_ZIP64 = os.getenv('ZIPSTREAM_ENABLE_ZIP64', 'True').lower() == 'true'  # Support large games

    # Development mode - forces theme files to be recopied on startup (helpful for theme development)
    DEV_MODE = os.getenv('DEV_MODE', 'false').lower() == 'true'
