#!/usr/bin/env bash
# start.sh — Start script for Render deployment

# Add local bin to PATH (for static FFmpeg)
export PATH="$PWD/bin:$PATH"

# Start the Flask application with Gunicorn
exec gunicorn \
    --bind 0.0.0.0:${PORT:-5000} \
    --workers 2 \
    --threads 4 \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    run:app
