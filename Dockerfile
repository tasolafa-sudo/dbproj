# Pin a stable Python; avoids Railpack + Python 3.13 edge cases with some packages.
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway sets PORT; 8080 is a sensible local default
EXPOSE 8080

# Print PORT once at boot, then run Gunicorn (logs go to stdout/stderr in Railway)
CMD ["sh", "-c", "echo \"PORT=${PORT:-8080}\" && exec python -m gunicorn --bind \"0.0.0.0:${PORT:-8080}\" --workers 1 --timeout 120 --access-logfile - --error-logfile - app:app"]
