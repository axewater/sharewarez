#!/bin/bash

# List the contents of the /app directory
echo "SharewareZ container strapping boots"
echo "(ignore erros about psql missing)"

# Function to check if PostgreSQL is ready
wait_for_postgres() {
    until psql -h "${DATABASE_HOST}" -U "${POSTGRES_USER}" -c '\q' &>/dev/null; do
        echo "Waiting for PostgreSQL to become available..."
        sleep 5
    done
    echo "PostgreSQL is now available."
}

# Wait for PostgreSQL to come online
wait_for_postgres

echo "Running the Sharewarez Docker container with uvicorn\n"
uvicorn asgi:asgi_app --host 0.0.0.0 --port 5006 --workers 4