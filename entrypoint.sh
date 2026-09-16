#!/bin/bash

echo "🚀 SharewareZ container starting up..."


# Extract database connection info from DATABASE_URL if available
if [[ -n "$DATABASE_URL" ]]; then
    # Parse DATABASE_URL for connection details
    # Format: postgresql://user:password@host:port/database
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
else
    # No fallback to POSTGRES_USER/POSTGRES_PASSWORD. That path defaulted to the
    # postgres superuser, so a missing DATABASE_URL silently started the app with
    # rights over every database on the server instead of failing. config.py
    # refuses to start for the same reason; refuse here too, before the wait loop
    # spends five minutes reporting a connection problem that is really a
    # configuration one.
    echo "❌ DATABASE_URL is not set."
    echo "   Set it in your .env file, e.g."
    echo "   DATABASE_URL=postgresql://sharewarez_app:<password>@db:5432/sharewarez"
    echo "   Use a dedicated role that owns only this app's tables, never the postgres superuser."
    exit 1
fi

# Function to check if PostgreSQL is ready using Python
wait_for_postgres() {
    echo "🔄 Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."

    until python3 -c "
import psycopg2
import sys
import os
from urllib.parse import urlparse

try:
    # Use DATABASE_URL if available, otherwise construct from parts
    if os.environ.get('DATABASE_URL'):
        url = urlparse(os.environ['DATABASE_URL'])
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port,
            user=url.username,
            password=url.password,
            database=url.path[1:],
            connect_timeout=5
        )
    else:
        # Unreachable: the shell above exits when DATABASE_URL is unset. Kept as
        # an explicit failure so this never quietly grows a superuser fallback again.
        raise SystemExit('DATABASE_URL is required')
    conn.close()
    print('✅ PostgreSQL connection successful')
except Exception as e:
    print(f'❌ Connection failed: {e}')
    sys.exit(1)
" 2>/dev/null; do
        echo "⏳ PostgreSQL not ready yet, waiting 5 seconds..."
        sleep 5
    done
    echo "✅ PostgreSQL is now available!"
}

# Wait for PostgreSQL to come online
wait_for_postgres

echo "🎮 Starting SharewareZ Docker container..."

# Pass all arguments through to startweb-docker.sh
/app/startweb-docker.sh "$@"