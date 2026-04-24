web: /bin/sh -c 'P="${PORT:-8080}"; exec python -m gunicorn --bind "0.0.0.0:$P" --workers 1 --timeout 120 --access-logfile - --error-logfile - app:app'
