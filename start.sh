#!/bin/bash

# script to start the Flask server in development or production mode or to stop the server

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