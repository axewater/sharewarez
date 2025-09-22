from flask import Blueprint
from modules import cache
from modules.utils_processors import get_global_settings

admin2_bp = Blueprint('admin2', __name__)

@admin2_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()

# Import routes to register them with the blueprint
from . import themes, libraries, discord, system, invites, filters, extensions, help, users, whitelist, newsletter, settings, igdb, images, access_management
