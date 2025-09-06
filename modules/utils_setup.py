# modules/utils_setup.py
from modules import db
from modules.models import User, GlobalSettings
from sqlalchemy import select
from datetime import datetime, timezone

def is_setup_required():
    """Check if setup is required (no users exist)"""
    return not db.session.execute(select(User)).scalars().first()

def get_or_create_global_settings():
    """Get existing global settings or create a new instance"""
    settings = db.session.execute(select(GlobalSettings)).scalars().first()
    if not settings:
        settings = GlobalSettings()
        db.session.add(settings)
        db.session.commit()
    return settings

def is_setup_in_progress():
    """Check if setup is currently in progress"""
    if is_setup_required():
        return True  # If no users exist, setup is required
    
    settings = get_or_create_global_settings()
    return settings.setup_in_progress and not settings.setup_completed

def get_current_setup_step():
    """Get the current setup step number"""
    if is_setup_required():
        return 1  # Always start with step 1 if no users exist
    
    settings = get_or_create_global_settings()
    if settings.setup_in_progress and not settings.setup_completed:
        return settings.setup_current_step
    return None  # Not in setup

def set_setup_step(step):
    """Update the current setup step and mark setup as in progress"""
    settings = get_or_create_global_settings()
    settings.setup_in_progress = True
    settings.setup_current_step = step
    settings.setup_completed = False
    settings.last_updated = datetime.now(timezone.utc)
    db.session.commit()

def mark_setup_complete():
    """Mark setup as fully completed"""
    settings = get_or_create_global_settings()
    settings.setup_in_progress = False
    settings.setup_completed = True
    settings.setup_current_step = 3  # Final step
    settings.last_updated = datetime.now(timezone.utc)
    db.session.commit()

def reset_setup_state():
    """Reset setup state (used for --force-setup)"""
    settings = get_or_create_global_settings()
    settings.setup_in_progress = True
    settings.setup_current_step = 1
    settings.setup_completed = False
    settings.last_updated = datetime.now(timezone.utc)
    db.session.commit()

def should_redirect_to_setup():
    """Check if requests should be redirected to setup"""
    return is_setup_required() or is_setup_in_progress()

def get_setup_redirect_url():
    """Get the appropriate setup URL for the current step"""
    if is_setup_required():
        return '/setup'
    
    current_step = get_current_setup_step()
    if current_step == 1:
        return '/setup'
    elif current_step == 2:
        return '/setup/smtp'
    elif current_step == 3:
        return '/setup/igdb'
    else:
        return '/setup'  # Default fallback