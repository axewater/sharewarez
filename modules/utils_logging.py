from modules import db
from modules.models import SystemEvents
from datetime import datetime
from typing import Optional, Union
from flask_login import current_user

def log_system_event(
    event_text: str,
    event_type: str = 'log',
    event_level: str = 'information',
    audit_user: Optional[Union[int, str]] = None
) -> bool:
    """
    Log a system event to the database.
    
    Args:
        event_text (str): The message to log (required, max 256 chars)
        event_type (str, optional): Type of event (default: 'log', max 32 chars)
        event_level (str, optional): Level of event (default: 'information', max 32 chars)
        audit_user (Union[int, str], optional): User ID or 'system' for system events
            If None, attempts to get current_user.id, falls back to 'system'
    
    Returns:
        bool: True if logging was successful, False otherwise
    """
    try:
        # Truncate strings if they exceed maximum lengths
        event_text = event_text[:256]
        event_type = event_type[:32]
        event_level = event_level[:32]
        
        # Handle audit_user logic
        if audit_user is None:
            # Try to get current user ID, fall back to 'system'
            audit_user = getattr(current_user, 'id', None)
        
        # Create new system event
        new_event = SystemEvents(
            event_text=event_text,
            event_type=event_type,
            event_level=event_level,
            audit_user=audit_user if audit_user != 'system' else None,
            timestamp=datetime.utcnow()
        )
        
        # Add and commit to database
        db.session.add(new_event)
        db.session.commit()
        
        return True
        
    except Exception as e:
        print(f"Error logging system event: {str(e)}")
        db.session.rollback()
        return False
