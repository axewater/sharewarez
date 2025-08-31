#!/bin/zsh

cd "$(dirname "$0")"

source venv/bin/activate

# Check if PRODUCTION environment variable is set
if [ "${PRODUCTION:-false}" = "true" ]; then
    echo "Starting SharewareZ in production mode with uvicorn..."
    uvicorn asgi:asgi_app --host 0.0.0.0 --port 5006 --workers 4
else
    echo "Starting SharewareZ in development mode..."
    python3 app.py
fi
