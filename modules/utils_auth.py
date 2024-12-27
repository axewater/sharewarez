from datetime import datetime
from functools import wraps
from flask import request, redirect, url_for, flash
from urllib.parse import urlparse as url_parse
from flask_login import current_user, login_user
from sqlalchemy import func
from modules.models import User, db
from modules import login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def _authenticate_and_redirect(username, password):
    user = User.query.filter(func.lower(User.name) == func.lower(username)).first()
    
    if user and user.check_password(password):
        # If the password is correct and is using bcrypt, rehash it with Argon2
        if not user.password_hash.startswith('$argon2'):
            user.rehash_password(password)
            db.session.commit()

        user.lastlogin = datetime.utcnow()
        db.session.commit()
        login_user(user, remember=True)
        
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.discover')
        return redirect(next_page)
    else:
        flash('Invalid username or password', 'error')
        return redirect(url_for('main.login'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("You must be an admin to access this page.", "danger")
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function