#!/bin/bash

ls -l /app

python /app/docker_adduser.py
python /app/app.py