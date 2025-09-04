#!/bin/zsh

cd "$(dirname "$0")"

source venv/bin/activate

echo "Starting SharewareZ with uvicorn..."

# Run complete startup initialization once before starting workers
python3 -c "
from modules.startup_init import run_complete_startup_initialization
import sys

if not run_complete_startup_initialization():
    print('Startup initialization failed, but continuing...')
    sys.exit(1)
"

# Ensure environment variables are set for worker processes
export SHAREWAREZ_MIGRATIONS_COMPLETE=true
export SHAREWAREZ_INITIALIZATION_COMPLETE=true

# Start uvicorn with workers (migrations already complete)
uvicorn asgi:asgi_app --host 0.0.0.0 --port 5006 --workers 4
