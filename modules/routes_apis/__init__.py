from flask import Blueprint
from modules import cache
from modules.utils_processors import get_global_settings

apis_bp = Blueprint('apis', __name__, url_prefix='/api')

@apis_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()

# Import routes to register them with the blueprint
from . import browse, download, filters, game, igdb, library, scan, system, user
