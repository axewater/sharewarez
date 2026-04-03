from flask import Blueprint
from sharewarez import cache
from sharewarez.utils.processors import get_global_settings

download_bp = Blueprint('download', __name__)

@download_bp.context_processor
@cache.cached(timeout=500, key_prefix='global_settings')
def inject_settings():
    """Context processor to inject global settings into templates"""
    return get_global_settings()

# Import routes to register them with the blueprint
from . import user, initiate, serve, admin, statistics, play
