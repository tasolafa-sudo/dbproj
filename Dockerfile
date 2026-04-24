# Pin a stable Python; avoids Railpack + Python 3.13 edge cases with some packages.
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/docker-entrypoint.sh

# Railway sets PORT; 8080 is a sensible local default
EXPOSE 8080

CMD ["/app/docker-entrypoint.sh"]
