from flask import render_template
from flask_login import login_required
from modules.utils_auth import admin_required
from . import admin2_bp

@admin2_bp.route('/admin/help')
@login_required
@admin_required
def admin_help():
    """Display the administrator help page"""
    return render_template('admin/admin_help.html')
