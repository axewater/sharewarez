import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from flask import current_app
from modules.models import AllowedFileType, IgnoredFileType, GlobalSettings
import os
from modules.utilities import notifications_manager

class GameFileHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_trigger_time = time.time()
        self.last_modified = ""

    def on_created(self, event):
        self.last_modified = event.src_path
        if '~' not in event.src_path:
            with current_app.app_context():
                allowed_ext = [ext.value for ext in AllowedFileType.query.all()]
                ignore_ext = [ext.value for ext in IgnoredFileType.query.all()]
                
                file_name = event.src_path.split('\\' if os.name == "nt" else '/')[-1]
                file_ext = "None" if event.is_directory else file_name.split('.')[-1]
                
                if (file_ext not in ignore_ext and file_ext in allowed_ext) or file_ext == "None":
                    settings = GlobalSettings.query.first()
                    if settings.enable_game_updates or settings.enable_game_extras:
                        print(f"Event: {event.src_path} was {event.event_type} - Processing File Name: {file_name} with File Extension {file_ext}")
                        time.sleep(5)
                        notifications_manager(event.src_path, event.event_type)

    def on_modified(self, event):
        current_time = time.time()
        if not event.is_directory and self.last_modified != event.src_path:
            if '~' not in event.src_path and (current_time - self.last_trigger_time) > 1:
                self.last_modified = event.src_path
                self.last_trigger_time = current_time
                
                with current_app.app_context():
                    allowed_ext = [ext.value for ext in AllowedFileType.query.all()]
                    ignore_ext = [ext.value for ext in IgnoredFileType.query.all()]
                    file_name = event.src_path.split('/')[-1]
                    file_ext = file_name.split('.')[-1]
                    
                    if file_ext not in ignore_ext and file_ext in allowed_ext:
                        settings = GlobalSettings.query.first()
                        if settings.enable_main_game_updates:
                            print(f"Event: {event.src_path} was {event.event_type} - Processing File Name: {file_name} with File Extension {file_ext}")
                            time.sleep(5)
                            notifications_manager(event.src_path, event.event_type)

class FileMonitor:
    def __init__(self):
        self.observer = Observer()
        self.shutdown_event = threading.Event()

    def watch_directory(self, path):
        self.observer.schedule(GameFileHandler(), path, recursive=True)
        self.observer.start()
        
        while not self.shutdown_event.is_set():
            time.sleep(1)

        self.observer.stop()
        self.observer.join()

    def start_monitoring(self, paths):
        for path in paths:
            thread = threading.Thread(
                target=self.watch_directory,
                name=f"Watchdog-{path}",
                daemon=True,
                args=(path,)
            )
            try:
                thread.start()
            except KeyboardInterrupt:
                self.shutdown_event.set()

    def stop_monitoring(self):
        self.shutdown_event.set()
