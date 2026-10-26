#!/bin/sh
set -e

echo "==> [1/3] Menjalankan Database Migrations..."
python manage.py migrate --noinput

echo "==> [2/3] Mengumpulkan Static Files..."
python manage.py collectstatic --noinput --clear

echo "==> [3/3] Menjalankan Gunicorn WSGI Server pada port 8000 (Host: 8069)..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
