#!/bin/zsh

cd "$(dirname "$0")"

source venv/bin/activate

# Check if PRODUCTION environment variable is set
if [ "${PRODUCTION:-false}" = "true" ]; then
    echo "Starting SharewareZ in production mode with uvicorn..."
    
    # Run database migrations and initialization once before starting workers
    echo "Running database migrations and initialization..."
    python3 -c "
import os
from modules.init_migrations import (
    run_database_migrations, mark_migrations_complete,
    run_database_initialization, mark_initialization_complete,
    cleanup_orphaned_scan_jobs
)
from modules import create_app

# Run migrations
if run_database_migrations():
    mark_migrations_complete()
    print('Migrations completed successfully')
else:
    print('Migration failed, but continuing...')

# Run initialization
app = create_app()
with app.app_context():
    if run_database_initialization():
        mark_initialization_complete()
        cleanup_orphaned_scan_jobs()
        print('Initialization completed successfully')
    else:
        print('Initialization failed, but continuing...')
"
    
    # Now start uvicorn with workers (migrations already complete)
    uvicorn asgi:asgi_app --host 0.0.0.0 --port 5006 --workers 4
else
    echo "Starting SharewareZ in development mode..."
    python3 app.py
fi
