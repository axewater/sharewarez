# /app.py
from modules import create_app
from modules.updateschema import DatabaseManager

app = create_app()

# Initialize and run the database schema update
db_manager = DatabaseManager()
db_manager.add_column_if_not_exists()

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5001)