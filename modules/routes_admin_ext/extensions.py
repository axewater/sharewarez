from flask import render_template
from flask_login import login_required
from modules.utils_auth import admin_required
from modules.models import AllowedFileType
from . import admin2_bp

@admin2_bp.route('/admin/extensions')
@login_required
@admin_required
def extensions():
    allowed_types = AllowedFileType.query.order_by(AllowedFileType.value.asc()).all()
    return render_template('admin/admin_manage_extensions.html', 
                         allowed_types=allowed_types)
