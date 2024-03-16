#!/bin/bash

ls -l /app

#/wait
sleep 10

python /app/docker_adduser.py
python /app/app.py