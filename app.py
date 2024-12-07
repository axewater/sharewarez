# /app.py
import time
from modules import create_app
from modules.updateschema import DatabaseManager
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
from flask import current_app
import os
import zipfile
import shutil

app = create_app()

def initialize_library_folders():
    """Initialize the required folders and theme files for the application."""
    library_path = os.path.join('modules', 'static', 'library')
    themes_path = os.path.join(library_path, 'themes')
    images_path = os.path.join(library_path, 'images')
    zips_path = os.path.join(library_path, 'zips')
    
    # Check if default theme exists
    if not os.path.exists(os.path.join(themes_path, 'default', 'theme.json')):
        print("Default theme not found. Initializing from themes.zip...")
        
        # Extract themes.zip
        themes_zip = os.path.join('modules', 'setup', 'themes.zip')
        if os.path.exists(themes_zip):
            with zipfile.ZipFile(themes_zip, 'r') as zip_ref:
                zip_ref.extractall(library_path)
            print("Themes extracted successfully")
        else:
            print("Warning: themes.zip not found in modules/setup/")

    # Create images folder if it doesn't exist
    if not os.path.exists(images_path):
        os.makedirs(images_path)
        print("Created images folder")

    # Create zips folder if it doesn't exist
    if not os.path.exists(zips_path):
        os.makedirs(zips_path)
        print("Created zips folder")

# Initialize library folders before creating the app
initialize_library_folders()


# Initialize and run the database schema update
db_manager = DatabaseManager()
db_manager.add_column_if_not_exists()

global last_trigger_time
last_trigger_time = time.time()
global last_modified
last_modified = ""

shutdown_event = threading.Event()

class MyHandler(FileSystemEventHandler):  
    global last_trigger_time
    last_trigger_time = time.time()

    def on_created(self, event):
        global last_modified
        last_modified = event.src_path
        if event.src_path.find('~') == -1:
            with app.app_context():
                allowed_ext = current_app.config['ALLOWED_FILE_TYPES'] # List of allowed extensions.
                ignore_ext = current_app.config['MONITOR_IGNORE_EXT']  # List of extensions to ignore.
                if os.name == "nt":
                    file_name = event.src_path.split('\\')[-1]
                else:
                    file_name = event.src_path.split('/')[-1]
                if not event.is_directory:
                    file_ext = file_name.split('.')[-1]
                else:
                    file_ext = "None"
                if (file_ext not in ignore_ext and file_ext in allowed_ext) or file_ext == "None":
                    from modules.utilities import notifications_manager
                    from modules.models import GlobalSettings
                    settings = GlobalSettings.query.first()
                    if settings.enable_game_updates or settings.enable_game_extras:
                        print(f"Event: {event.src_path} was {event.event_type} - Processing File Name: {file_name} with File Extension {file_ext}")
                        time.sleep(5)
                        notifications_manager(event.src_path, event.event_type)            
    def on_modified(self, event):
        global last_trigger_time
        global last_modified
        current_time = time.time()
        if not event.is_directory and last_modified != event.src_path:
            if event.src_path.find('~') == -1 and (current_time - last_trigger_time) > 1:  
                last_modified = event.src_path
                last_trigger_time = current_time
                with app.app_context():
                    allowed_ext = current_app.config['ALLOWED_FILE_TYPES'] # List of allowed extensions.
                    ignore_ext = current_app.config['MONITOR_IGNORE_EXT']  # List of extensions to ignore.
                    file_name = event.src_path.split('/')[-1]
                    file_ext = file_name.split('.')[-1]
                    if file_ext not in ignore_ext and file_ext in allowed_ext:
                        from modules.utilities import notifications_manager
                        from modules.models import GlobalSettings
                        settings = GlobalSettings.query.first()
                        if settings.enable_main_game_updates:
                            print(f"Event: {event.src_path} was {event.event_type} - Processing File Name: {file_name} with File Extension {file_ext}")
                            time.sleep(5)
                            notifications_manager(event.src_path, event.event_type) 
        
def watch_directory(path):
    observer = Observer()
    observer.schedule(MyHandler(), path, recursive=True)
    observer.start()
    
    while not shutdown_event.is_set():
        time.sleep(1)

    observer.stop()
    observer.join()

if __name__ == "__main__":
    with app.app_context():
        config_path = current_app.config['MONITOR_PATHS']  # Replace with the directory you want to watch
        paths = config_path
        for p in paths:
            targetPath = str(p)
            # configure a watchdog thread
            thread = threading.Thread(target=watch_directory, name="Watchdog", daemon=True, args=(targetPath,))
            # start the watchdog thread
            try:
                thread.start()
            except KeyboardInterrupt:
                shutdown_event.set()

    app.run(host="0.0.0.0", debug=True, use_reloader=False, port=5001)
    


    
