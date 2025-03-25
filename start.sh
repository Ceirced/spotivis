#!/bin/bash

# script to start the Flask server in development or production mode or to stop the server

# check if the ./logs/app and ./instance directory exist and create it if they don't.
# If they are not created, docker will create it with the wrong user and flask will not be able to write to it.
if [ ! -d "./logs/app" ]; then
    mkdir -p ./logs/app
fi
if [ ! -d "./instance" ]; then
    mkdir -p ./instance
fi



if [ "$1" = 'dev' ]; then
    echo "Starting Flask server in DEV..."
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
elif [ "$1" = 'prod' ]; then
    echo "Starting Flask server in PROD..."
    docker compose up -d --build
elif [ "$1" = 'stop' ]; then
    echo "Stopping Flask server..."
    docker compose down
else
    echo "Invalid argument. Please use 'dev' or 'prod' or 'stop'."
    exit 1
fi