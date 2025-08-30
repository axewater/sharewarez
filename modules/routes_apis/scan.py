# /modules/routes_apis/scan.py
from flask import jsonify
from flask_login import login_required
from modules import db
from modules.models import ScanJob, UnmatchedFolder, Library
from sqlalchemy import select
from modules.utils_auth import admin_required
from modules.utils_functions import PLATFORM_IDS
from . import apis_bp

@apis_bp.route('/scan_jobs_status', methods=['GET'])
@login_required
@admin_required
def scan_jobs_status():
    jobs = db.session.execute(select(ScanJob)).scalars().all()
    jobs_data = [{
        'id': job.id,
        'library_name': job.library.name if job.library else 'No Library Assigned',
        'folders': job.folders,
        'status': job.status,
        'total_folders': job.total_folders,
        'folders_success': job.folders_success,
        'folders_failed': job.folders_failed,
        'removed_count': job.removed_count,
        'scan_folder': job.scan_folder,
        'setting_remove': bool(job.setting_remove),
        'error_message': job.error_message,
        'last_run': job.last_run.strftime('%Y-%m-%d %H:%M:%S') if job.last_run else 'Not Available',
        'next_run': job.next_run.strftime('%Y-%m-%d %H:%M:%S') if job.next_run else 'Not Scheduled',
        'setting_filefolder': bool(job.setting_filefolder)
    } for job in jobs]
    return jsonify(jobs_data)

@apis_bp.route('/unmatched_folders', methods=['GET'])
@login_required
@admin_required
def unmatched_folders():
    unmatched = db.session.execute(
        select(UnmatchedFolder, Library.name.label('library_name'), Library.platform)
        .join(Library)
        .order_by(UnmatchedFolder.status.desc())
    ).all()
    
    unmatched_data = [{
        'id': folder.id,
        'folder_path': folder.folder_path,
        'status': folder.status,
        'library_name': library_name,
        'platform_name': platform.name if platform else '',
        'platform_id': PLATFORM_IDS.get(platform.name) if platform else None
    } for folder, library_name, platform in unmatched]
    
    return jsonify(unmatched_data)
