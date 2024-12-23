import os, secrets

class Config(object):
    # Set DB connection string here or in your .env file
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:!Piratingin2024!@db:5432/sharewarez_dev')
    
    # Set the path to the folder where the game files are stored
    DATA_FOLDER_WAREZ = os.getenv('DATA_FOLDER_WAREZ', '/gamez')
    
    # Set the path where the application saves it files
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'modules/static/library')
    
    # You can probably leave all the settings below at their defaults
    SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_hex(32)
    IMAGE_SAVE_PATH = os.path.join(os.path.dirname(__file__), 'modules/static/library/images')
    ZIP_SAVE_PATH = os.path.join(os.path.dirname(__file__), 'modules/static/library/zips')
    IGDB_API_ENDPOINT = os.getenv('IGDB_API_ENDPOINT', 'https://api.igdb.com/v4/games')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ALLOWED_FILE_TYPES = ['zip', 'rar', '7z', 'iso', 'nfo', 'nes', 'sfc', 'smc', 'sms', '32x', 'gen', 'gg', 'gba', 'gb', 'gbc', 'prg', 'dat', 'tap', 'z64', 'd64', 'dsk', 'img', 'bin', 'st', 'stx', 'j64', 'jag', 'lnx', 'adf', 'ngc', 'gz', 'm2v', 'ogg', 'fpt', 'fpl', 'vec', 'pce', 'rom']
    MONITOR_IGNORE_EXT = os.getenv('MONITOR_IGNORE_EXT', ['txt', 'nfo']) # BETA option for monitoring updates
    
    # OS-specific base folder paths
    if os.name == 'nt':  # Windows
        BASE_FOLDER_WINDOWS = os.getenv('BASE_FOLDER_WINDOWS', 'C:/')
    else:  # POSIX (Linux, Unix, MacOS, etc.)
        BASE_FOLDER_POSIX = os.getenv('BASE_FOLDER_POSIX', '/storage')
    
    if os.name == 'nt':  # BETA option for monitoring updates
        MONITOR_PATHS = os.getenv('MONITOR_PATHS', ['Z:\\Gamez\\PC'])
    else:
        MONITOR_PATHS = os.getenv('MONITOR_PATHS', ['/storage'])