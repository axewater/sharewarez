import os
import json
import zipfile
import shutil
from flask import current_app, flash
from werkzeug.utils import secure_filename

class ThemeManager:
    def __init__(self, app):
        self.app = app
        self.theme_folder = app.config['THEME_FILES']

    def upload_theme(self, theme_zip):
        # Check if the library folder exists
        if not os.path.exists(self.app.config['UPLOAD_FOLDER']):
            flash('Error: Library folder does not exist.', 'error')
            return None

        # Check if the themes folder exists, create it if not
        if not os.path.exists(self.theme_folder):
            try:
                os.makedirs(self.theme_folder)
                flash('Themes folder created successfully.', 'info')
            except Exception as e:
                flash(f'Error creating themes folder: {str(e)}', 'error')
                return None

        temp_dir = os.path.join(self.app.config['UPLOAD_FOLDER'], 'temp_theme')
        os.makedirs(temp_dir, exist_ok=True)

        try:
            # Extract zip to temp folder
            with zipfile.ZipFile(theme_zip, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Validate theme.json
            theme_json_path = os.path.join(temp_dir, 'theme.json')
            if not os.path.exists(theme_json_path):
                raise ValueError("theme.json not found in the uploaded zip file")

            with open(theme_json_path, 'r') as json_file:
                theme_data = json.load(json_file)

            required_fields = ['name', 'description', 'author', 'release_date']
            for field in required_fields:
                if field not in theme_data:
                    raise ValueError(f"Missing required field '{field}' in theme.json")

            # Validate theme structure
            css_folder = os.path.join(temp_dir, 'css')
            if not os.path.exists(css_folder):
                raise ValueError("CSS folder not found in the uploaded theme")

            # Create theme folder and move files
            theme_name = secure_filename(theme_data['name'])
            theme_path = os.path.join(self.theme_folder, theme_name)
            if os.path.exists(theme_path):
                raise ValueError(f"Theme '{theme_name}' already exists")

            shutil.move(temp_dir, theme_path)

            return theme_data
        finally:
            # Clean up temp folder
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def get_installed_themes(self):
        themes = []
        for theme_name in os.listdir(self.theme_folder):
            theme_path = os.path.join(self.theme_folder, theme_name)
            if os.path.isdir(theme_path):
                json_path = os.path.join(theme_path, 'theme.json')
                if os.path.exists(json_path):
                    with open(json_path, 'r') as json_file:
                        theme_data = json.load(json_file)
                        themes.append({
                            'name': theme_data['name'],
                            'author': theme_data['author'],
                            'release_date': theme_data['release_date'],
                            'description': theme_data['description'][:32] + '...' if len(theme_data['description']) > 32 else theme_data['description']
                        })
        return themes

    def validate_theme_structure(self, theme_path):
        required_folders = ['css']
        for folder in required_folders:
            if not os.path.exists(os.path.join(theme_path, folder)):
                return False
        return True
