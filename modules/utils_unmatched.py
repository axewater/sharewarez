from flask import flash, redirect, url_for, session, request
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from modules import db
from modules.models import UnmatchedFolder
from sqlalchemy import select, delete, func

def clear_only_unmatched_folders():
    print("Attempting to clear only unmatched folders")
    try:
        result = db.session.execute(delete(UnmatchedFolder).where(UnmatchedFolder.status == 'Unmatched')).rowcount
        print(f"Number of unmatched folders deleted: {result}")
        db.session.commit()
        flash(f'Successfully cleared {result} unmatched folders with status "Unmatched".', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        error_message = f"Database error while clearing unmatched folders: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
    except Exception as e:
        db.session.rollback()
        error_message = f"An unexpected error occurred while clearing unmatched folders: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
    
    print("Redirecting to scan management page")
    return redirect(url_for('main.scan_management'))


def handle_delete_unmatched(all):
    print(f"Route: /delete_unmatched - {current_user.name} - {current_user.role} method: {request.method} arguments: all={all}")
    try:
        if all:
            print(f"Clearing all unmatched folders: {db.session.execute(select(func.count(UnmatchedFolder.id))).scalar()}")
            db.session.execute(delete(UnmatchedFolder))
            flash('All unmatched folders cleared successfully.', 'success')
        else:
            count = db.session.execute(select(func.count(UnmatchedFolder.id)).where(UnmatchedFolder.status == 'Unmatched')).scalar()
            print(f"Clearing this number of unmatched folders: {count}")
            db.session.execute(delete(UnmatchedFolder).where(UnmatchedFolder.status == 'Unmatched'))
            flash('Unmatched folders with status "Unmatched" cleared successfully.', 'success')
        db.session.commit()
        session['active_tab'] = 'unmatched'
    except SQLAlchemyError as e:
        db.session.rollback()
        error_message = f"Database error while clearing unmatched folders: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
    except Exception as e:
        db.session.rollback()
        error_message = f"An unexpected error occurred while clearing unmatched folders: {str(e)}"
        print(error_message)
        flash(error_message, 'error')
    return redirect(url_for('main.scan_management'))



