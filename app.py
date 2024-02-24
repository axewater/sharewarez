# /app.py
from modules import create_app
# dsads
app = create_app()
if __name__ == '__main__':
    app.run(debug=True)