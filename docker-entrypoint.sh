#!/bin/sh
set -e
P="${PORT:-8080}"
echo "Listening on 0.0.0.0:$P (PORT from env)"
exec python -m gunicorn --bind "0.0.0.0:$P" --workers 1 --timeout 120 --access-logfile - --error-logfile - app:app
