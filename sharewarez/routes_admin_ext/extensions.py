from flask import render_template
from flask_login import login_required
from sharewarez.utils.auth import admin_required
from sharewarez.models import AllowedFileType
from sharewarez import db
from sqlalchemy import select
from . import admin2_bp

@admin2_bp.route('/admin/extensions')
@login_required
@admin_required
def extensions():
    allowed_types = db.session.execute(select(AllowedFileType).order_by(AllowedFileType.value.asc())).scalars().all()
    return render_template('admin/admin_manage_extensions.html', 
                         allowed_types=allowed_types)
