#!/bin/bash
# this script is used to boot a Docker container

# Function to start the Flask server
start_server() {
    if [ "$APP_SETTINGS" = "config.ProductionConfig" ]; then
        echo "Starting Flask server in production..."
        exec gunicorn --bind :5000 --access-logfile - --error-logfile - flask_app:app --workers 4
    else
        echo "Starting Flask server in dev..."
        python3 flask_app.py
    fi
}

# Check if APP_SETTINGS is set
if [ -z "$APP_SETTINGS" ]; then
    echo "Error: APP_SETTINGS variable is not set."
    exit 1
fi

while true; do
    flask db upgrade
    if [[ "$?" == "0" ]]; then
        break
    fi
    echo Deploy command failed, retrying in 5 secs...
    sleep 5
done


# Start the server
start_server
