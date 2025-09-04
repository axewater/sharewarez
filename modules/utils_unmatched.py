import logging
from flask import flash, redirect, url_for, session, request
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from modules import db
from modules.models import UnmatchedFolder
from modules.utils_logging import log_system_event
from sqlalchemy import select, delete, func

# Configure logger for this module
logger = logging.getLogger(__name__)

def handle_delete_unmatched(all):
    """Handle deletion of unmatched folders with proper logging and audit trail.
    
    Args:
        all (bool): If True, delete all unmatched folders. If False, delete only 'Unmatched' status folders.
    """
    user_info = f"{current_user.name} ({current_user.role})" if current_user.is_authenticated else "Unknown"
    operation_type = "all unmatched folders" if all else "unmatched folders with status 'Unmatched'"
    
    logger.info(f"Delete operation initiated by {user_info} - Method: {request.method} - Type: {operation_type}")
    
    try:
        if all:
            # Count before deletion for logging
            total_count = db.session.execute(select(func.count(UnmatchedFolder.id))).scalar()
            logger.info(f"Attempting to clear all {total_count} unmatched folders")
            
            # Delete all unmatched folders
            db.session.execute(delete(UnmatchedFolder))
            
            # Audit log the operation
            log_system_event(
                event_text=f"Deleted all {total_count} unmatched folders",
                event_type="delete_operation",
                event_level="warning"
            )
            
            flash('All unmatched folders cleared successfully.', 'success')
            logger.info(f"Successfully deleted all {total_count} unmatched folders")
            
        else:
            # Count folders with 'Unmatched' status before deletion
            count = db.session.execute(select(func.count(UnmatchedFolder.id)).where(UnmatchedFolder.status == 'Unmatched')).scalar()
            logger.info(f"Attempting to clear {count} unmatched folders with 'Unmatched' status")
            
            # Delete only folders with 'Unmatched' status
            db.session.execute(delete(UnmatchedFolder).where(UnmatchedFolder.status == 'Unmatched'))
            
            # Audit log the operation
            log_system_event(
                event_text=f"Deleted {count} unmatched folders with 'Unmatched' status",
                event_type="delete_operation",
                event_level="information"
            )
            
            flash('Unmatched folders with status "Unmatched" cleared successfully.', 'success')
            logger.info(f"Successfully deleted {count} unmatched folders with 'Unmatched' status")
        
        db.session.commit()
        session['active_tab'] = 'unmatched'
        
    except SQLAlchemyError as e:
        db.session.rollback()
        error_msg = f"Database error during unmatched folder deletion: {str(e)}"
        logger.error(error_msg)
        
        # Log audit event for failed operation
        log_system_event(
            event_text=f"Failed to delete {operation_type} - Database error",
            event_type="delete_operation",
            event_level="error"
        )
        
        flash("Database error occurred while clearing folders. Please try again.", 'error')
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Unexpected error during unmatched folder deletion: {str(e)}"
        logger.error(error_msg)
        
        # Log audit event for failed operation
        log_system_event(
            event_text=f"Failed to delete {operation_type} - Unexpected error",
            event_type="delete_operation",
            event_level="error"
        )
        
        flash("An unexpected error occurred while clearing folders. Please try again.", 'error')
    
    logger.info("Redirecting to scan management page")
    return redirect(url_for('main.scan_management'))



