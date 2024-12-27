import os
import json
import zipfile
import shutil
from flask import current_app, flash
from werkzeug.utils import secure_filename
from modules.models import UserPreference
from modules import db

class ThemeManager:
    def __init__(self, app):
        self.app = app
        self.theme_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'modules/static/library/themes')

    def get_default_theme(self):
        default_theme_path = os.path.join(self.theme_folder, 'default', 'theme.json')
        try:
            with open(default_theme_path, 'r') as json_file:
                return json.load(json_file)
        except Exception as e:
            print(f"Error reading default theme: {str(e)}")
            return None

    def get_installed_themes(self):
        themes = []
        for theme_name in os.listdir(self.theme_folder):
            theme_path = os.path.join(self.theme_folder, theme_name)
            if os.path.isdir(theme_path):
                json_path = os.path.join(theme_path, 'theme.json')
                if os.path.exists(json_path):
                    try:
                        with open(json_path, 'r') as json_file:
                            theme_data = json.load(json_file)
                            themes.append({
                                'name': theme_data.get('name', theme_name),
                                'author': theme_data.get('author', 'Unknown'),
                                'release_date': theme_data.get('release_date', 'Unknown'),
                                'description': theme_data.get('description', 'No description available')
                            })
                    except Exception as e:
                        print(f"Error reading theme {theme_name}: {str(e)}")
        return themes

    def upload_theme(self, theme_zip):
        if not os.path.exists(self.app.config['UPLOAD_FOLDER']):
            flash('Error: Library folder does not exist.', 'error')
            return None

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
            with zipfile.ZipFile(theme_zip, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            theme_json_path = os.path.join(temp_dir, 'theme.json')
            if not os.path.exists(theme_json_path):
                raise ValueError("theme.json not found in the uploaded zip file")

            with open(theme_json_path, 'r') as json_file:
                theme_data = json.load(json_file)

            required_fields = ['name', 'description', 'author', 'release_date']
            for field in required_fields:
                if field not in theme_data:
                    raise ValueError(f"Missing required field '{field}' in theme.json")

            css_folder = os.path.join(temp_dir, 'css')
            if not os.path.exists(css_folder):
                raise ValueError("CSS folder not found in the uploaded theme")

            theme_name = secure_filename(theme_data['name'])
            theme_path = os.path.join(self.theme_folder, theme_name)
            if os.path.exists(theme_path):
                raise ValueError(f"Theme '{theme_name}' already exists")

            shutil.move(temp_dir, theme_path)

            return theme_data
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def validate_theme_structure(self, theme_path):
        required_folders = ['css']
        return all(os.path.exists(os.path.join(theme_path, folder)) for folder in required_folders)

    def delete_themefile(self, theme_name):
        if theme_name == 'Default':
            raise ValueError("Cannot delete the default theme.")

        theme_path = os.path.join(self.theme_folder, secure_filename(theme_name))
        if not os.path.exists(theme_path):
            raise ValueError(f"Theme '{theme_name}' does not exist.")

        try:
            shutil.rmtree(theme_path)
        except Exception as e:
            raise Exception(f"Error deleting theme: {str(e)}")

        UserPreference.query.filter_by(theme=theme_name).update({'theme': 'default'})
        db.session.commit()
