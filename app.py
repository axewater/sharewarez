# /app.py
import time
from modules import create_app
from modules.updateschema import DatabaseManager
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
from flask import current_app

app = create_app()


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
        if event.src_path.find('~') == -1:
            with app.app_context():
                from modules.utilities import discord_update
                from modules.models import GlobalSettings
                settings = GlobalSettings.query.first()
                if settings.enable_game_updates or settings.enable_game_extras:
                    print(f"Event: {event.src_path} was {event.event_type}")
                    discord_update(event.src_path, event.event_type)            
    def on_modified(self, event):
        global last_trigger_time
        global last_modified
        current_time = time.time()
        if not event.is_directory and last_modified != event.src_path:
            if event.src_path.find('~') == -1 and (current_time - last_trigger_time) > 1:  
                last_modified = event.src_path
                last_trigger_time = current_time
                with app.app_context():
                    from modules.utilities import discord_update
                    from modules.models import GlobalSettings
                    settings = GlobalSettings.query.first()
                    if settings.enable_main_game_updates:
                        print(f"Event: {event.src_path} was {event.event_type}")
                        discord_update(event.src_path, event.event_type) 
        
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
        print(f"Scanning Paths: {paths}")
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
    


    