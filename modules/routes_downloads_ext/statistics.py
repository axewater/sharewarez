from flask import render_template, jsonify
from flask_login import login_required
from modules.utils_statistics import get_download_statistics
from modules.utils_auth import admin_required
from . import download_bp

@download_bp.route('/admin/statistics')
@login_required
@admin_required
def statistics():
    """Display the statistics page"""
    return render_template('admin/admin_statistics.html')

@download_bp.route('/admin/statistics/data')
@login_required
@admin_required
def statistics_data():
    """Return JSON data for the statistics charts"""
    stats = get_download_statistics()
    return jsonify(stats)
