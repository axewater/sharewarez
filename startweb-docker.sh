#!/bin/bash

cd "$(dirname "$0")"

echo "Starting SharewareZ with uvicorn..."

# Run complete startup initialization with retry logic
MAX_RETRIES=10
RETRY_COUNT=0
RETRY_DELAY=5

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    echo "Attempting database initialization (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)..."
    
    python3 -c "
from modules.startup_init import run_complete_startup_initialization
import sys

if not run_complete_startup_initialization():
    print('Startup initialization failed, retrying...')
    sys.exit(1)
"
    
    if [ $? -eq 0 ]; then
        echo "Database initialization successful!"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo "Retrying in $RETRY_DELAY seconds..."
            sleep $RETRY_DELAY
        else
            echo "Database initialization failed after $MAX_RETRIES attempts. Exiting."
            exit 1
        fi
    fi
done

# Ensure environment variables are set for worker processes
export SHAREWAREZ_MIGRATIONS_COMPLETE=true
export SHAREWAREZ_INITIALIZATION_COMPLETE=true

# Start uvicorn with workers (migrations already complete)
uvicorn asgi:asgi_app --host 0.0.0.0 --port 5006 --workers 4