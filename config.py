import os, secrets

class Config(object):
    # Set Database connection string here or in your .env file
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/sharewarez')
    
    # Set the path to the folder where the game files are stored (ie: use c:\gamez for windows or /gamez for linux)
    DATA_FOLDER_WAREZ = os.getenv('DATA_FOLDER_WAREZ', r'C:\gamez')
    
    # OS-specific base folder paths
    if os.name == 'nt':  # Windows
        BASE_FOLDER_WINDOWS = os.getenv('BASE_FOLDER_WINDOWS', r'C:/')
    else:  # POSIX (Linux, Unix, MacOS, etc.)
        BASE_FOLDER_POSIX = os.getenv('BASE_FOLDER_POSIX', '/storage')

    # YOU CAN LEAVE ALL THESE SETTINGS AT DEFAULT:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'modules/static/library')
    SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_hex(32)
    IMAGE_SAVE_PATH = os.path.join(os.path.dirname(__file__), 'modules/static/library/images')
    ZIP_SAVE_PATH = os.path.join(os.path.dirname(__file__), 'modules/static/library/zips')
    IGDB_API_ENDPOINT = os.getenv('IGDB_API_ENDPOINT', 'https://api.igdb.com/v4/games')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ALLOWED_FILE_TYPES = ['zip', 'rar', '7z', 'iso', 'nfo']
