from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_caching import Cache

# Initialize Flask extensions
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
cache = Cache(config={'CACHE_TYPE': 'simple'})

# Configure login manager
login_manager.login_view = 'main.login'

@login_manager.user_loader
def load_user(user_id):
    from modules.models import User
    return User.query.get(int(user_id))
