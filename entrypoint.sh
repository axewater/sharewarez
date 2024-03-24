#!/bin/bash

# List the contents of the /app directory
echo "SharewareZ container strapping boots"
# Function to check if PostgreSQL is ready
wait_for_postgres() {
    until psql -h <database_host> -U <database_user> -c '\q' &>/dev/null; do
        echo "Waiting for PostgreSQL to become available..."
        sleep 5
    done
    echo "PostgreSQL is now available."
}

# Wait for PostgreSQL to come online
wait_for_postgres

# Execute your Python scripts
python /app/docker_adduser.py
python /app/app.py
