"""
Startup initialization wrapper for SharewareZ.
This module now delegates to the centralized InitializationManager
to eliminate duplication and provide a consistent initialization flow.
"""

from modules.init_manager import run_complete_initialization, mark_initialization_complete


def run_complete_startup_initialization():
    """
    Run complete startup initialization using the centralized manager.
    This is a thin wrapper for backward compatibility.
    """
    success = run_complete_initialization()

    if success:
        # Mark initialization as complete for other processes
        mark_initialization_complete()

    return success