#!/bin/bash


# Parse arguments
FORCE_SETUP=false
if [[ "$1" == "--force-setup" || "$1" == "-fs" ]]; then
    FORCE_SETUP=true
fi

cd "$(dirname "$0")"

source venv/bin/activate

# Load .env file and export variables to shell environment
if [ -f .env ]; then
    echo "📌 Loading environment variables from .env..."
    set -a  # automatically export all variables
    source .env
    set +a  # turn off automatic export

    # Debug: Verify DATABASE_URL is loaded
    if [ -n "$DATABASE_URL" ]; then
        echo "✅ DATABASE_URL loaded from .env"
    else
        echo "❌ WARNING: DATABASE_URL not found in environment!"
    fi
else
    echo "⚠️  Warning: .env file not found in $(pwd)"
fi

if [[ "$FORCE_SETUP" == "true" ]]; then
    echo "🔄 Force setup mode - resetting database..."

    # Environment variables are already loaded from .env file above
    python3 -c "
from sharewarez import create_app, db
from sharewarez.utils.setup import reset_setup_state

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

print('Database reset complete. Run ./startweb.sh to start the server.')
"
    exit 0
fi

echo "Starting SharewareZ with uvicorn..."

# Run complete startup initialization once before starting workers
python3 -c "
from sharewarez.init_manager import run_complete_startup_initialization
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

# Set port for uvicorn (default 5006, can be overridden by PORT env var)
export PORT=${PORT:-5006}

# Start uvicorn with workers (migrations already complete)
uvicorn asgi:asgi_app --host 0.0.0.0 --port $PORT --workers 4
