#!/bin/bash
# this script is used to boot a Docker container

# Function to start the Flask server
start_server() {
    echo "Starting Flask server..."
    if [ "$APP_SETTINGS" = "config.DevelopmentConfig" ]; then
        exec gunicorn --bind :5000 --access-logfile - --error-logfile - template_app:app --workers 4 --reload --log-level debug
    else
        exec gunicorn --bind :5000 --access-logfile - --error-logfile - template_app:app --workers 4
    fi
}

# Check if APP_SETTINGS is set
if [ -z "$APP_SETTINGS" ]; then
    echo "Error: APP_SETTINGS variable is not set."
    exit 1
fi

# Start the server
start_server
