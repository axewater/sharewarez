#!/bin/bash

# Docker-specific startup script for SharewareZ
# This script is designed to run inside the Docker container


# Parse arguments
FORCE_SETUP=false
if [[ "$1" == "--force-setup" || "$1" == "-fs" ]]; then
    FORCE_SETUP=true
fi

# We're already in /app directory in Docker, no need to cd

if [[ "$FORCE_SETUP" == "true" ]]; then
    echo "🔄 Force setup mode - resetting database..."

    # Load environment for standalone execution
    python3 -c "
from dotenv import load_dotenv
load_dotenv()

from modules import create_app, db
from modules.utils_setup import reset_setup_state

# Create app and reset database
app = create_app()
with app.app_context():
    print('Dropping all tables...')
    db.drop_all()
    print('Recreating all tables...')
    db.create_all()
    print('Database reset complete.')

    reset_setup_state()
    print('Setup state reset - setup wizard will run on next startup')

print('Database reset complete. Restart the container to start the server.')
"
    exit 0
fi

echo "Starting SharewareZ with uvicorn in Docker container..."

# Run complete startup initialization once before starting workers
python3 -c "
from modules.startup_init import run_complete_startup_initialization
import sys

print('🚀 Starting SharewareZ initialization...')
if not run_complete_startup_initialization():
    print('❌ Startup initialization failed!')
    sys.exit(1)
print('✅ Initialization completed - starting workers...')
"

# Ensure environment variables are set for worker processes
export SHAREWAREZ_MIGRATIONS_COMPLETE=true
export SHAREWAREZ_INITIALIZATION_COMPLETE=true

# Start uvicorn for Docker (bind to all interfaces, single worker for containers)
# Note: In Docker, we typically run single worker and scale with multiple containers
uvicorn asgi:asgi_app --host 0.0.0.0 --port 6006 --workers 1