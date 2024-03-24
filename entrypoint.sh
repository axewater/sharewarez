#!/bin/bash

# List the contents of the /app directory
echo "SharewareZ container strapping boots"


# Execute your Python scripts
python /app/docker_adduser.py
python /app/app.py
